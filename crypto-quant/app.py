"""Streamlit 儀表板：K 線＋指標、策略回測。

啟動：streamlit run app.py
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from quant import backtest as bt
from quant import config, db
from quant import indicators as ind
from quant.fetcher import fetch_and_store, make_exchange

st.set_page_config(page_title="Crypto Quant", layout="wide")


@st.cache_data(ttl=300)
def load(exchange: str, symbol: str, timeframe: str) -> pd.DataFrame:
    conn = db.connect(config.DB_PATH)
    try:
        return db.load_candles(conn, exchange, symbol, timeframe)
    finally:
        conn.close()


def available_series() -> pd.DataFrame:
    conn = db.connect(config.DB_PATH)
    try:
        return db.list_series(conn)
    finally:
        conn.close()


# ---------------- 側邊欄 ----------------
st.sidebar.title("Crypto Quant")

with st.sidebar.expander("更新資料", expanded=False):
    ex_id = st.text_input("交易所", config.EXCHANGE)
    syms = st.text_input("交易對", ",".join(config.SYMBOLS))
    tf_new = st.selectbox("週期", list(config.TIMEFRAME_MS), index=list(config.TIMEFRAME_MS).index(config.TIMEFRAME))
    days = st.number_input("首次抓取天數", 30, 3650, config.HISTORY_DAYS, step=30)
    if st.button("開始抓取"):
        exchange = make_exchange(ex_id)
        conn = db.connect(config.DB_PATH)
        try:
            for s in [x.strip() for x in syms.split(",") if x.strip()]:
                with st.spinner(f"抓取 {s} …"):
                    try:
                        n = fetch_and_store(conn, exchange, s, tf_new, int(days), log=lambda *_: None)
                        st.success(f"{s}：新增 {n} 根")
                    except Exception as e:
                        st.error(f"{s} 失敗：{type(e).__name__}: {e}")
        finally:
            conn.close()
        load.clear()

series = available_series()
if series.empty:
    st.info("資料庫目前沒有資料。請在左側「更新資料」抓取，或執行 `python scripts/update_data.py`。")
    st.stop()

series["label"] = series["exchange"] + " · " + series["symbol"] + " · " + series["timeframe"]
choice = st.sidebar.selectbox("資料", series["label"])
row = series[series["label"] == choice].iloc[0]
df_all = load(row.exchange, row.symbol, row.timeframe)

start, end = df_all.index[0].date(), df_all.index[-1].date()
date_range = st.sidebar.date_input("區間", (start, end), min_value=start, max_value=end)
if isinstance(date_range, tuple) and len(date_range) == 2:
    lo = pd.Timestamp(date_range[0], tz="UTC")
    hi = pd.Timestamp(date_range[1], tz="UTC") + pd.Timedelta(days=1)
    df = df_all[(df_all.index >= lo) & (df_all.index < hi)]
else:
    df = df_all

if len(df) < 60:
    st.warning("區間內資料太少（少於 60 根），請擴大區間。")
    st.stop()

tab_chart, tab_bt = st.tabs(["圖表", "回測"])

# ---------------- 圖表 ----------------
with tab_chart:
    c1, c2, c3 = st.columns(3)
    ma_opts = c1.multiselect("均線", ["EMA 20", "EMA 50", "SMA 200"], default=["EMA 20", "EMA 50"])
    show_bb = c2.checkbox("布林通道", value=False)
    lower = c3.radio("副圖", ["RSI", "MACD", "成交量"], horizontal=True)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df.open, high=df.high, low=df.low, close=df.close,
                                 name=row.symbol), row=1, col=1)
    for m in ma_opts:
        kind, n = m.split()
        line = (ind.ema if kind == "EMA" else ind.sma)(df.close, int(n))
        fig.add_trace(go.Scatter(x=df.index, y=line, name=m, line=dict(width=1.2)), row=1, col=1)
    if show_bb:
        b = ind.bollinger(df.close)
        for col in ["upper", "lower"]:
            fig.add_trace(go.Scatter(x=df.index, y=b[col], name=f"BB {col}",
                                     line=dict(width=1, dash="dot", color="gray")), row=1, col=1)

    if lower == "RSI":
        fig.add_trace(go.Scatter(x=df.index, y=ind.rsi(df.close), name="RSI 14"), row=2, col=1)
        for lvl in (30, 70):
            fig.add_hline(y=lvl, line_dash="dash", line_color="gray", row=2, col=1)
    elif lower == "MACD":
        m = ind.macd(df.close)
        fig.add_trace(go.Bar(x=df.index, y=m.hist, name="Hist"), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=m.macd, name="MACD"), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=m.signal, name="Signal"), row=2, col=1)
    else:
        fig.add_trace(go.Bar(x=df.index, y=df.volume, name="Volume"), row=2, col=1)

    fig.update_layout(height=720, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

    last = df.iloc[-1]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("最新收盤", f"{last.close:,.2f}", f"{df.close.pct_change().iloc[-1]:.2%}")
    k2.metric("RSI 14", f"{ind.rsi(df.close).iloc[-1]:.1f}")
    k3.metric("ATR 14", f"{ind.atr(df).iloc[-1]:,.2f}")
    k4.metric("資料筆數", f"{len(df):,}")

# ---------------- 回測 ----------------
with tab_bt:
    strat = st.selectbox("策略", list(bt.STRATEGIES))
    p1, p2, p3, p4 = st.columns(4)
    if strat == "均線交叉":
        kind = p1.selectbox("均線類型", ["ema", "sma"])
        fast = p2.number_input("快線", 2, 400, 20)
        slow = p3.number_input("慢線", 3, 800, 50)
        params = dict(fast=int(fast), slow=int(slow), kind=kind)
    elif strat == "RSI 均值回歸":
        n = p1.number_input("RSI 週期", 2, 100, 14)
        lo_ = p2.number_input("進場（低於）", 1, 50, 30)
        hi_ = p3.number_input("出場（高於）", 50, 99, 70)
        params = dict(n=int(n), low=float(lo_), high=float(hi_))
    else:
        entry = p1.number_input("突破週期", 2, 400, 20)
        exit_ = p2.number_input("出場週期", 2, 400, 10)
        params = dict(entry=int(entry), exit=int(exit_))
    fee = p4.number_input("單邊手續費＋滑價 (%)", 0.0, 1.0, 0.15, step=0.01) / 100

    if strat == "均線交叉" and params["fast"] >= params["slow"]:
        st.warning("快線週期應小於慢線週期。")

    sig = bt.STRATEGIES[strat](df, **params)
    res = bt.run_backtest(df, sig, config.bars_per_year(row.timeframe), fee=fee, slippage=0.0)
    s = res.stats

    def pct(x):
        return "—" if pd.isna(x) else f"{x:.2%}"

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("總報酬率", pct(s["總報酬率"]))
    m2.metric("年化報酬率", pct(s["年化報酬率"]))
    m3.metric("最大回撤", pct(s["最大回撤"]))
    m4.metric("夏普比率", "—" if pd.isna(s["夏普比率"]) else f"{s['夏普比率']:.2f}")
    m5.metric("交易次數／勝率", f"{s['交易次數']} / {pct(s['勝率'])}")
    st.caption(f"對照買入持有：總報酬率 {pct(s['買入持有報酬率'])}，最大回撤 {pct(s['買入持有最大回撤'])}；"
               f"持倉時間比例 {pct(s['持倉時間比例'])}")

    eq = go.Figure()
    eq.add_trace(go.Scatter(x=res.equity.index, y=res.equity, name="策略"))
    eq.add_trace(go.Scatter(x=res.benchmark.index, y=res.benchmark, name="買入持有", line=dict(dash="dot")))
    eq.update_layout(height=420, title="權益曲線（起始 = 1）", margin=dict(l=10, r=10, t=70, b=10),
                     legend=dict(orientation="h", y=1.0, yanchor="bottom"))
    st.plotly_chart(eq, use_container_width=True)

    dd = res.equity / res.equity.cummax() - 1
    ddf = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", name="回撤", line=dict(color="#d62728")))
    ddf.update_layout(height=220, title="回撤", yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(ddf, use_container_width=True)

    st.subheader("交易明細")
    if res.trades.empty:
        st.write("此區間沒有交易。")
    else:
        st.dataframe(res.trades.style.format({"報酬率": "{:.2%}", "進場價": "{:,.2f}", "出場價": "{:,.2f}"}),
                     use_container_width=True)

    st.caption("訊號在 K 線收盤時產生，下一根才持有部位。手續費在每次進出場時扣除。過去績效不代表未來表現。")
