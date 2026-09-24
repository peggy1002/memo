"""透過 ccxt 從交易所增量抓取 K 線。"""
import time

import ccxt

from . import db
from .config import TIMEFRAME_MS


def make_exchange(exchange_id: str):
    cls = getattr(ccxt, exchange_id)
    return cls({"enableRateLimit": True})


def fetch_and_store(conn, exchange, symbol: str, timeframe: str, history_days: int,
                    limit: int = 1000, log=print) -> int:
    """從資料庫最後一根 K 線接著抓；沒有資料時往回抓 history_days 天。

    最後一根尚未收盤的 K 線不會寫入，避免用到未完成的資料。
    """
    step = TIMEFRAME_MS[timeframe]
    now = exchange.milliseconds()
    last = db.last_timestamp(conn, exchange.id, symbol, timeframe)
    since = last + step if last is not None else now - history_days * 86_400_000

    total = 0
    while since < now:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not batch:
            break
        closed = [r for r in batch if r[0] + step <= now]
        if closed:
            total += db.upsert_candles(conn, exchange.id, symbol, timeframe, closed)
        next_since = batch[-1][0] + step
        if next_since <= since:  # 防止交易所回傳重複資料時無限迴圈
            break
        since = next_since
        if len(batch) < limit:
            break
        time.sleep(exchange.rateLimit / 1000)

    log(f"[{exchange.id}] {symbol} {timeframe}: 新增 {total} 根 K 線")
    return total
