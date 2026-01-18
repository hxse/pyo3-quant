import numpy as np
import pandas as pd
import polars as pl


def generate_ohlcv(num_bars: int, seed: int = 42) -> tuple[pl.DataFrame, pd.DataFrame]:
    """
    生成模拟 OHLCV 数据，同时返回 Polars DataFrame (用于 pyo3-quant) 和 Pandas DataFrame (用于 VectorBT)。
    保证两份数据内容完全一致。
    """
    np.random.seed(seed)

    # 随机游走生成价格
    price = 100 + np.cumsum(np.random.randn(num_bars) * 0.5)

    # 构建数据字典
    # pyo3-quant 的 Rust 引擎 expectation: "time", "open", "high", "low", "close", "volume"
    data = {
        "time": np.arange(num_bars) * 900000,  # 15m = 900000ms
        "open": price,
        "high": price + np.abs(np.random.randn(num_bars)) * 0.5,
        "low": price - np.abs(np.random.randn(num_bars)) * 0.5,
        "close": price + np.random.randn(num_bars) * 0.2,
        "volume": np.random.randint(1000, 10000, size=num_bars).astype(float),
    }

    # 创建 Pandas DataFrame
    pd_df = pd.DataFrame(data)

    # 创建 Polars DataFrame (直接从 dict 创建效率高)
    pl_df = pl.DataFrame(data)

    # 确保列类型符合预期 (pyo3-quant 可能期待 float64)
    # 这一步通常自动处理，但为了保险可以手动转换

    return pl_df, pd_df
