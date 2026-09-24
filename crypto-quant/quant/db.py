"""SQLite 儲存層：K 線的寫入（upsert）與讀取。"""
import sqlite3
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    exchange  TEXT    NOT NULL,
    symbol    TEXT    NOT NULL,
    timeframe TEXT    NOT NULL,
    ts        INTEGER NOT NULL,  -- K 線開盤時間（UTC 毫秒）
    open      REAL    NOT NULL,
    high      REAL    NOT NULL,
    low       REAL    NOT NULL,
    close     REAL    NOT NULL,
    volume    REAL    NOT NULL,
    PRIMARY KEY (exchange, symbol, timeframe, ts)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    return conn


def upsert_candles(conn, exchange: str, symbol: str, timeframe: str, rows) -> int:
    """rows 為 ccxt 格式：[[ts, open, high, low, close, volume], ...]。重複的 ts 會被覆寫。"""
    data = [(exchange, symbol, timeframe, int(r[0]), *map(float, r[1:6])) for r in rows]
    conn.executemany(
        "INSERT OR REPLACE INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", data
    )
    conn.commit()
    return len(data)


def last_timestamp(conn, exchange: str, symbol: str, timeframe: str):
    row = conn.execute(
        "SELECT MAX(ts) FROM candles WHERE exchange=? AND symbol=? AND timeframe=?",
        (exchange, symbol, timeframe),
    ).fetchone()
    return row[0]


def load_candles(conn, exchange: str, symbol: str, timeframe: str) -> pd.DataFrame:
    """回傳以 UTC 時間為索引的 OHLCV DataFrame。"""
    df = pd.read_sql_query(
        "SELECT ts, open, high, low, close, volume FROM candles "
        "WHERE exchange=? AND symbol=? AND timeframe=? ORDER BY ts",
        conn,
        params=(exchange, symbol, timeframe),
    )
    df.index = pd.to_datetime(df.pop("ts"), unit="ms", utc=True)
    df.index.name = "time"
    return df


def list_series(conn) -> pd.DataFrame:
    """列出資料庫中已有的 (exchange, symbol, timeframe) 組合與資料範圍。"""
    return pd.read_sql_query(
        "SELECT exchange, symbol, timeframe, COUNT(*) AS bars, MIN(ts) AS first_ts, MAX(ts) AS last_ts "
        "FROM candles GROUP BY exchange, symbol, timeframe ORDER BY exchange, symbol, timeframe",
        conn,
    )
