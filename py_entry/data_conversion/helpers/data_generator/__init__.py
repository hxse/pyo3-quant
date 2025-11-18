"""
数据生成器模块
"""

import polars as pl
import numpy as np
from datetime import datetime

from .time_utils import parse_timeframe
from .ohlcv_generator import generate_multi_timeframe_ohlcv
from .heikin_ashi_generator import generate_ha
from .renko_generator import generate_renko
from .time_mapping import generate_time_mapping
from py_entry.data_conversion.input import DataContainer

# 导入所有函数以便直接访问
from .time_utils import time_format, fixed_cols
from .ohlcv_generator import generate_ohlcv
from .heikin_ashi_generator import calculate_heikin_ashi
from .renko_generator import calculate_renko
from .time_mapping import is_natural_sequence, _process_dataframe_mapping


def generate_data_dict(
    timeframes: list[str],
    start_time: int,
    num_bars: int = 1000,
    brick_size: float = 2.0,
    predefined_ohlcv_dfs: list[pl.DataFrame] | None = None,
    fixed_seed: bool = False,
) -> DataContainer:
    """
    生成完整的数据字典

    Args:
        timeframes: 时间周期列表,默认 ["15m", "1h", "4h"]
        start_time: 起始时间(毫秒级时间戳),如果为 None 则使用当前时间减去合理偏移
        num_bars: 最小周期的k线数量,默认1000
        brick_size: Renko砖块大小,默认2.0
        predefined_ohlcv_dfs: 预定义的OHLCV DataFrame列表,如果提供此参数则跳过generate_multi_timeframe_ohlcv计算
        fixed_seed: 是否使用固定种子,如果为True则生成的OHLCV数据是固定的,默认False

    Returns:
        包含以下键的字典:
    """
    if predefined_ohlcv_dfs is not None:
        # 使用预定义的OHLCV数据，跳过generate_multi_timeframe_ohlcv计算
        ohlcv_dfs = predefined_ohlcv_dfs
    else:
        if start_time is None:
            # 默认从当前时间往前推 num_bars * 最小时间周期
            min_timeframe_ms = parse_timeframe(timeframes[0])
            start_time = (
                int(datetime.now().timestamp() * 1000) - num_bars * min_timeframe_ms
            )
        ohlcv_dfs = generate_multi_timeframe_ohlcv(
            timeframes, start_time, num_bars, fixed_seed
        )

    ha_dfs = generate_ha(ohlcv_dfs)
    renko_dfs = generate_renko(ohlcv_dfs, brick_size)

    mapping_df, skip_mapping = generate_time_mapping(ohlcv_dfs, ha_dfs, renko_dfs)

    # skip_mask 占位,暂时全为 False
    skip_mask_series = pl.Series("skip", np.zeros(len(ohlcv_dfs[0])), dtype=pl.Boolean)

    return DataContainer(
        mapping=mapping_df,
        skip_mask=skip_mask_series,
        skip_mapping=skip_mapping,
        source={
            "ohlcv": ohlcv_dfs,
            "ha": ha_dfs,
            "renko": renko_dfs,
        },
    )


# 导出所有主要函数，以便兼容原有导入方式
__all__ = [
    "parse_timeframe",
    "generate_data_dict",
    "generate_ohlcv",
    "generate_multi_timeframe_ohlcv",
    "generate_ha",
    "calculate_heikin_ashi",
    "generate_renko",
    "calculate_renko",
    "generate_time_mapping",
    "is_natural_sequence",
    "_process_dataframe_mapping",
    "time_format",
    "fixed_cols",
]
