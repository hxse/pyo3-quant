"""
OHLCV 数据生成工具

从 pyo3-quant 的数据生成器中提取 OHLCV 数据，供 backtesting.py 使用
"""

import pandas as pd
from py_entry.data_conversion.data_generator import (
    DataGenerationParams,
    generate_data_dict,
)
from py_entry.Test.backtest.correlation_analysis.config import CommonConfig


def generate_ohlcv_for_backtestingpy(
    config: CommonConfig,
) -> pd.DataFrame:
    """
    生成适用于 backtesting.py 的 OHLCV 数据

    Args:
        config: 公共配置

    Returns:
        Pandas DataFrame with columns: Open, High, Low, Close, Volume
    """
    # 使用 DataGenerationParams 生成数据
    data_config = DataGenerationParams(
        timeframes=[config.timeframe],
        start_time=config.start_time,
        num_bars=config.bars,
        fixed_seed=config.seed,
        BaseDataKey=f"ohlcv_{config.timeframe}",
        allow_gaps=config.allow_gaps,  # 使用统一配置
    )

    data_dict = generate_data_dict(data_config)

    base_key = f"ohlcv_{config.timeframe}"
    # 提取 Polars DataFrame（使用 .source 字典）
    ohlcv_pl = data_dict.source[base_key]

    # 转换为 Pandas DataFrame 并重命名列
    ohlcv_pd = ohlcv_pl.to_pandas()

    # backtesting.py 需要的列名（首字母大写）
    ohlcv_pd = ohlcv_pd.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )

    # 设置时间索引
    ohlcv_pd["time"] = pd.to_datetime(ohlcv_pd["time"], unit="ms")
    ohlcv_pd = ohlcv_pd.set_index("time")

    # 只保留必要列
    return ohlcv_pd[["Open", "High", "Low", "Close", "Volume"]]
