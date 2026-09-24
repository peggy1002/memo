"""向量化回測（只做多、全倉進出）。

規則：第 t 根 K 線收盤時產生訊號，第 t+1 根才持有部位，避免前視偏差。
每次部位變動（進場或出場）都扣一次手續費加滑價。
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind


@dataclass
class BacktestResult:
    equity: pd.Series          # 策略淨值（起始為 1）
    benchmark: pd.Series       # 買入持有淨值
    position: pd.Series        # 每根 K 線實際持有的部位（0 或 1）
    trades: pd.DataFrame       # 每筆交易的進出場時間、價格與報酬
    stats: dict


# ---------- 策略：輸出「目標部位」訊號（1 = 持有，0 = 空手） ----------

def signal_ma_cross(df: pd.DataFrame, fast: int = 20, slow: int = 50, kind: str = "ema") -> pd.Series:
    f = ind.ema if kind == "ema" else ind.sma
    fast_ma, slow_ma = f(df["close"], fast), f(df["close"], slow)
    return (fast_ma > slow_ma).astype(float).where(slow_ma.notna(), 0.0)


def signal_rsi_reversion(df: pd.DataFrame, n: int = 14, low: float = 30, high: float = 70) -> pd.Series:
    """RSI 跌破 low 進場，漲破 high 出場。"""
    r = ind.rsi(df["close"], n)
    sig = pd.Series(np.nan, index=df.index)
    sig[r < low] = 1.0
    sig[r > high] = 0.0
    return sig.ffill().fillna(0.0)


def signal_breakout(df: pd.DataFrame, entry: int = 20, exit: int = 10) -> pd.Series:
    """唐奇安通道：收盤突破前 entry 根最高價進場，跌破前 exit 根最低價出場。"""
    upper = df["high"].rolling(entry).max().shift(1)
    lower = df["low"].rolling(exit).min().shift(1)
    sig = pd.Series(np.nan, index=df.index)
    sig[df["close"] > upper] = 1.0
    sig[df["close"] < lower] = 0.0
    return sig.ffill().fillna(0.0)


STRATEGIES = {
    "均線交叉": signal_ma_cross,
    "RSI 均值回歸": signal_rsi_reversion,
    "通道突破": signal_breakout,
}


# ---------- 回測 ----------

def run_backtest(df: pd.DataFrame, signal: pd.Series, bars_per_year: float,
                 fee: float = 0.001, slippage: float = 0.0005) -> BacktestResult:
    """fee、slippage 皆為單邊比例，例如 0.001 = 0.1%。"""
    close = df["close"]
    ret = close.pct_change().fillna(0.0)
    position = signal.shift(1).fillna(0.0)
    turnover = position.diff().abs().fillna(position.iloc[0])
    strat_ret = (1 + position * ret) * (1 - turnover * (fee + slippage)) - 1

    equity = (1 + strat_ret).cumprod()
    benchmark = close / close.iloc[0]
    trades = _extract_trades(close, position, fee + slippage)
    stats = _stats(strat_ret, equity, benchmark, trades, position, bars_per_year)
    return BacktestResult(equity, benchmark, position, trades, stats)


def _extract_trades(close: pd.Series, position: pd.Series, cost: float) -> pd.DataFrame:
    """部位在第 t 根變為 1，代表以第 t-1 根收盤價進場；變為 0 代表以第 t-1 根收盤價出場。"""
    change = position.diff().fillna(position.iloc[0])
    idx = close.index
    rows, entry_i = [], None
    for i in np.flatnonzero(change.values != 0):
        fill_i = max(i - 1, 0)
        if change.iloc[i] > 0:
            entry_i = fill_i
        elif entry_i is not None:
            rows.append((entry_i, fill_i, False))
            entry_i = None
    if entry_i is not None:  # 回測結束時仍持倉，以最後收盤價計算未實現損益
        rows.append((entry_i, len(close) - 1, True))

    records = []
    for e, x, is_open in rows:
        gross = close.iloc[x] / close.iloc[e]
        net = gross * (1 - cost) ** (1 if is_open else 2) - 1
        records.append({
            "進場時間": idx[e], "進場價": close.iloc[e],
            "出場時間": idx[x], "出場價": close.iloc[x],
            "報酬率": net, "持有K線數": x - e, "未平倉": is_open,
        })
    return pd.DataFrame(records)


def _max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def _stats(strat_ret, equity, benchmark, trades, position, bars_per_year) -> dict:
    n = len(equity)
    years = n / bars_per_year
    total = float(equity.iloc[-1] - 1)
    std = strat_ret.std()
    closed = trades[~trades["未平倉"]] if len(trades) else trades
    return {
        "總報酬率": total,
        "年化報酬率": float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 and equity.iloc[-1] > 0 else np.nan,
        "最大回撤": _max_drawdown(equity),
        "夏普比率": float(strat_ret.mean() / std * np.sqrt(bars_per_year)) if std > 0 else np.nan,
        "交易次數": int(len(trades)),
        "勝率": float((closed["報酬率"] > 0).mean()) if len(closed) else np.nan,
        "持倉時間比例": float(position.mean()),
        "買入持有報酬率": float(benchmark.iloc[-1] - 1),
        "買入持有最大回撤": _max_drawdown(benchmark),
    }
