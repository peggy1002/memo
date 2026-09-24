import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def ohlcv():
    rng = np.random.default_rng(0)
    n = 500
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({
        "open": close * (1 + rng.normal(0, 0.002, n)),
        "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": rng.uniform(1, 10, n),
    }, index=idx)
