import numpy as np
import pandas as pd

from quant import indicators as ind


def test_sma_matches_manual():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert ind.sma(s, 3).tolist()[2:] == [2.0, 3.0, 4.0]
    assert ind.sma(s, 3).isna().sum() == 2


def test_rsi_bounds_and_monotonic_up():
    up = pd.Series(np.arange(1, 50, dtype=float))
    assert (ind.rsi(up).dropna() == 100).all()
    rng = np.random.default_rng(1)
    r = ind.rsi(pd.Series(100 + rng.normal(0, 1, 300).cumsum())).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_indicators_have_no_lookahead(ohlcv):
    """把未來資料截掉，過去的指標值不應改變。"""
    cut = ohlcv.iloc[:300]
    for f in (lambda d: ind.rsi(d.close), lambda d: ind.macd(d.close).macd,
              lambda d: ind.bollinger(d.close).upper, ind.atr):
        pd.testing.assert_series_equal(f(ohlcv).iloc[:300], f(cut), check_names=False)
