"""全域設定。可用環境變數覆寫。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 交易所（ccxt 的 id，例如 binance、okx、bybit）
EXCHANGE = os.getenv("CQ_EXCHANGE", "binance")

# 追蹤的交易對，以逗號分隔
SYMBOLS = [s.strip() for s in os.getenv("CQ_SYMBOLS", "BTC/USDT,ETH/USDT").split(",") if s.strip()]

# K 線週期
TIMEFRAME = os.getenv("CQ_TIMEFRAME", "1h")

# 第一次抓取時往回抓幾天
HISTORY_DAYS = int(os.getenv("CQ_HISTORY_DAYS", "365"))

# SQLite 資料庫位置
DB_PATH = Path(os.getenv("CQ_DB_PATH", ROOT / "data" / "market.db"))

# 每根 K 線的毫秒數，用來計算分頁與年化
TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


def bars_per_year(timeframe: str) -> float:
    """加密貨幣 24/7 交易，一年以 365 天計。"""
    return 365 * 86_400_000 / TIMEFRAME_MS[timeframe]
