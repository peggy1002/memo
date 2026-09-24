from quant import db
from quant.fetcher import fetch_and_store

H = 3_600_000


class FakeExchange:
    """模擬 ccxt：從 0 開始每小時一根，現在時間在第 25 根中間（第 25 根尚未收盤）。"""
    id = "fake"
    rateLimit = 0

    def milliseconds(self):
        return 25 * H + H // 2

    def fetch_ohlcv(self, symbol, timeframe, since, limit):
        start = max(since, 0)
        ts = range(start - start % H, self.milliseconds(), H)
        return [[t, 1, 2, 0.5, 1.5, 10] for t in ts][:limit]


def test_incremental_fetch(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    ex = FakeExchange()
    n1 = fetch_and_store(conn, ex, "X/USDT", "1h", history_days=10, limit=10, log=lambda *_: None)
    assert n1 == 25  # 第 0~24 根，未收盤的第 25 根不寫入
    n2 = fetch_and_store(conn, ex, "X/USDT", "1h", history_days=10, limit=10, log=lambda *_: None)
    assert n2 == 0
    df = db.load_candles(conn, "fake", "X/USDT", "1h")
    assert len(df) == 25 and df.index.is_monotonic_increasing
    assert db.list_series(conn).iloc[0]["bars"] == 25
