import numpy as np
import pandas as pd

from quant import backtest as bt


def _df(prices):
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="D", tz="UTC")
    p = pd.Series(prices, index=idx, dtype=float)
    return pd.DataFrame({"open": p, "high": p, "low": p, "close": p, "volume": 1.0})


def test_always_long_equals_buy_and_hold_minus_entry_fee():
    df = _df([100, 110, 121, 133.1])
    sig = pd.Series(1.0, index=df.index)
    res = bt.run_backtest(df, sig, 365, fee=0.001, slippage=0)
    # 第 0 根收盤產生訊號，第 1 根起持有：報酬 = 1.331 - 進場費
    assert np.isclose(res.equity.iloc[-1], (1 - 0.001) * 1.1 * 1.1 * 1.1)
    assert res.stats["交易次數"] == 1
    assert res.trades["未平倉"].iloc[0]


def test_signal_is_shifted_no_lookahead():
    df = _df([100, 200, 100])
    sig = pd.Series([0.0, 1.0, 0.0], index=df.index)  # 在暴漲那根才出訊號
    res = bt.run_backtest(df, sig, 365, fee=0, slippage=0)
    # 第 1 根才出訊號 → 第 2 根持有 → 吃到 -50%，不能吃到 +100%
    assert np.isclose(res.equity.iloc[-1], 0.5)
    t = res.trades.iloc[0]
    assert t["進場價"] == 200 and t["出場價"] == 100 and np.isclose(t["報酬率"], -0.5)


def test_flat_signal_no_trades():
    df = _df([100, 90, 80, 120])
    res = bt.run_backtest(df, pd.Series(0.0, index=df.index), 365)
    assert res.stats["交易次數"] == 0 and res.equity.iloc[-1] == 1.0
    assert np.isnan(res.stats["勝率"])


def test_all_strategies_run(ohlcv):
    for name, f in bt.STRATEGIES.items():
        sig = f(ohlcv)
        assert set(sig.unique()) <= {0.0, 1.0}, name
        res = bt.run_backtest(ohlcv, sig, 24 * 365)
        assert len(res.equity) == len(ohlcv)
        assert res.stats["最大回撤"] <= 0
