"""抓取並更新 K 線資料。

用法：
    python scripts/update_data.py                 # 更新一次
    python scripts/update_data.py --loop 3600     # 每小時更新一次，持續執行
    python scripts/update_data.py --symbols SOL/USDT --timeframe 4h --days 730
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant import config, db  # noqa: E402
from quant.fetcher import fetch_and_store, make_exchange  # noqa: E402


def update_all(exchange_id, symbols, timeframe, days, db_path):
    exchange = make_exchange(exchange_id)
    conn = db.connect(db_path)
    try:
        for symbol in symbols:
            try:
                fetch_and_store(conn, exchange, symbol, timeframe, days)
            except Exception as e:  # 單一交易對失敗不影響其他
                print(f"[{exchange_id}] {symbol} 抓取失敗：{type(e).__name__}: {e}", file=sys.stderr)
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser(description="更新加密貨幣 K 線資料")
    p.add_argument("--exchange", default=config.EXCHANGE)
    p.add_argument("--symbols", default=",".join(config.SYMBOLS), help="以逗號分隔，例如 BTC/USDT,ETH/USDT")
    p.add_argument("--timeframe", default=config.TIMEFRAME, choices=list(config.TIMEFRAME_MS))
    p.add_argument("--days", type=int, default=config.HISTORY_DAYS, help="首次抓取往回幾天")
    p.add_argument("--db", default=str(config.DB_PATH))
    p.add_argument("--loop", type=int, default=0, help="每隔幾秒重複更新；0 表示只跑一次")
    args = p.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    while True:
        update_all(args.exchange, symbols, args.timeframe, args.days, args.db)
        if args.loop <= 0:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
