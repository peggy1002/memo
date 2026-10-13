# Crypto Quant：個人虛擬貨幣量化分析工具（第一階段）

用 Python + ccxt + SQLite + Streamlit 做的個人量化分析儀表板。

- **資料**：透過 ccxt 從交易所增量抓 K 線（預設 Binance.US 的 BTC/USDT、ETH/USDT，1 小時線，往回一年），存在本地 SQLite。開啟儀表板時每 10 分鐘自動補抓最新資料。
- **圖表**：K 線，可疊加 EMA／SMA、布林通道，副圖可選 RSI、MACD、成交量。
- **回測**：均線交叉、RSI 均值回歸、通道突破三種策略，可調參數和手續費；輸出總報酬、年化報酬、最大回撤、夏普比率、勝率，以及權益曲線、回撤圖和交易明細，並和買入持有對照。

## 安裝

```bash
cd crypto-quant
python -m venv .venv
source .venv/bin/activate        # Windows：.venv\Scripts\activate
pip install -r requirements-dev.txt   # 含測試工具；只想執行可用 requirements.txt
```

## 使用

```bash
# 1. 抓資料（第一次會抓約一年的小時線，大約 1～2 分鐘）
python scripts/update_data.py

# 2. 開啟儀表板（瀏覽器會自動打開 http://localhost:8501）
streamlit run app.py
```

也可以在儀表板左側「更新資料」直接抓取。

### 常用參數

```bash
# 其他交易對、週期與天數
python scripts/update_data.py --symbols BTC/USDT,ETH/USDT,SOL/USDT --timeframe 4h --days 1095

# 換交易所（任何 ccxt 支援的 id，例如 okx、bybit）
python scripts/update_data.py --exchange okx

# 持續執行，每小時自動更新
python scripts/update_data.py --loop 3600
```

預設值也可以用環境變數設定：`CQ_EXCHANGE`、`CQ_SYMBOLS`、`CQ_TIMEFRAME`、`CQ_HISTORY_DAYS`、`CQ_DB_PATH`。

預設交易所是 `binanceus`，因為部署用的 Streamlit Cloud 主機在美國，Binance 主站會擋美國的連線。在台灣自己的電腦上執行時，可以設 `CQ_EXCHANGE=binance` 改用 Binance 主站。

## 部署到 Streamlit Community Cloud（免費）

1. 到 <https://share.streamlit.io>，用 GitHub 帳號登入並授權。
2. 點 **Create app** → **Deploy a public app from GitHub**。
3. 填入：
   - Repository：`peggy1002/memo`
   - Branch：`claude/claim-credit-endpoint-yj6in0`
   - Main file path：`crypto-quant/app.py`
   - App URL：自訂一個好記的名稱
4. 點 **Deploy**，等幾分鐘安裝套件。第一次開啟時會自動抓一年的資料，大約需要 1 分鐘。

之後只要 push 新的程式碼到這個分支，網站就會自動更新。

注意事項：

- 免費主機重新啟動或休眠後，資料庫會清空；下次開啟時會自動重新抓取。
- 一段時間沒人使用，網站會進入休眠，再開啟時按畫面上的按鈕喚醒即可。
- 想改設定（交易所、交易對、週期等）時，在 App 的 **Settings → Secrets** 填入例如：

  ```toml
  CQ_SYMBOLS = "BTC/USDT,ETH/USDT,SOL/USDT"
  CQ_TIMEFRAME = "4h"
  ```

## 回測規則

- 第 t 根 K 線**收盤**產生訊號，第 t+1 根才持有部位，避免前視偏差。
- 只做多、全倉進出；每次進場和出場各扣一次「手續費＋滑價」（預設單邊 0.15%）。
- 只存已收盤的 K 線，不會寫入進行中的那一根。
- 年化和夏普比率以一年 365 天、全天候交易計算。

過去績效不代表未來表現。回測結果只是驗證想法的工具。

## 專案結構

```
crypto-quant/
├── app.py                 Streamlit 儀表板
├── scripts/update_data.py 抓資料 CLI
├── quant/
│   ├── config.py          設定
│   ├── db.py              SQLite 讀寫
│   ├── fetcher.py         ccxt 增量抓取
│   ├── indicators.py      技術指標
│   └── backtest.py        策略訊號與回測引擎
├── tests/                 pytest 單元測試
└── data/                  SQLite 資料庫（不進版控）
```

## 測試

```bash
pytest -q
```

## 下一步（第二階段）

- 訊號通知（Telegram Bot）
- 多幣種篩選器、相關性矩陣
- 資金費率、未平倉量等衍生品資料
- 參數最佳化與 Walk-forward 驗證
