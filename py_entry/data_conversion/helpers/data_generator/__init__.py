"""
数据生成器模块
"""

import polars as pl
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .time_utils import parse_timeframe, time_format, fixed_cols
from .ohlcv_generator import generate_multi_timeframe_ohlcv, generate_ohlcv
from .heikin_ashi_generator import generate_ha, calculate_heikin_ashi
from .renko_generator import generate_renko, calculate_renko
from .time_mapping import generate_time_mapping, is_natural_sequence
from py_entry.data_conversion.input import DataContainer
from py_entry.data_conversion.file_utils.data_client import (
    get_ohlcv_data,
    convert_to_ohlcv_dataframe,
    OhlcvDataConfig,
)

if TYPE_CHECKING:
    from py_entry.data_conversion.file_utils.types import RequestConfig


@dataclass
class DataGenerationParams:
    """数据生成参数配置类"""

    timeframes: list[str]
    start_time: int | None = None
    num_bars: int = 1000
    fixed_seed: bool = False


@dataclass
class OtherParams:
    """其他参数配置类，用于存放不太重要的参数"""

    brick_size: float = 2.0
    ha_enable: bool = True
    renko_enable: bool = True


@dataclass
class OhlcvDataFetchConfig:
    """OHLCV数据获取配置类"""

    config: "RequestConfig"  # 使用字符串避免循环导入
    timeframes: list[str]
    start_time: int
    count: int = 10
    enable_cache: bool = True


def generate_data_dict(
    simulated_data_config: DataGenerationParams | None = None,
    ohlcv_data_config: OhlcvDataFetchConfig | None = None,
    predefined_ohlcv_dfs: list[pl.DataFrame] | None = None,
    other_params: OtherParams | None = None,
) -> DataContainer:
    """
    生成完整的数据字典

    Args:
        simulated_data_config: 模拟数据生成参数配置对象
        ohlcv_data_config: OHLCV数据获取配置对象,如果提供此参数则从服务器获取数据
        other_params: 其他参数配置对象,如果为None则使用默认值
        predefined_ohlcv_dfs: 预定义的OHLCV DataFrame列表,如果提供此参数则跳过generate_multi_timeframe_ohlcv计算

    Returns:
        包含以下键的字典:
    """
    if simulated_data_config is not None:
        # 使用 simulated_data_config 参数生成数据
        if simulated_data_config.start_time is None:
            # 默认从当前时间往前推 num_bars * 最小时间周期
            min_timeframe_ms = parse_timeframe(simulated_data_config.timeframes[0])
            start_time = (
                int(datetime.now().timestamp() * 1000)
                - simulated_data_config.num_bars * min_timeframe_ms
            )
        else:
            start_time = simulated_data_config.start_time
        ohlcv_dfs = generate_multi_timeframe_ohlcv(
            simulated_data_config.timeframes,
            start_time,
            simulated_data_config.num_bars,
            simulated_data_config.fixed_seed,
        )
    elif ohlcv_data_config is not None:
        # 从服务器获取OHLCV数据，需要为每个时间周期获取数据
        ohlcv_dfs: list[pl.DataFrame] = []
        for timeframe in ohlcv_data_config.timeframes:
            # 为每个时间周期创建单独的配置对象
            single_ohlcv_config = OhlcvDataConfig(
                config=ohlcv_data_config.config,
                exchange_name="binance",  # 默认值，可以从配置中获取
                symbol="BTC/USDT",  # 默认值，可以从配置中获取
                period=timeframe,
                start_time=ohlcv_data_config.start_time,
                count=ohlcv_data_config.count,
                enable_cache=ohlcv_data_config.enable_cache,
            )
            result = get_ohlcv_data(single_ohlcv_config)
            ohlcv_df = convert_to_ohlcv_dataframe(result)
            if ohlcv_df is not None:
                ohlcv_dfs.append(ohlcv_df)
            else:
                raise ValueError(f"无法从服务器获取时间周期 {timeframe} 的OHLCV数据")
    elif predefined_ohlcv_dfs is not None:
        # 使用预定义的OHLCV数据，跳过generate_multi_timeframe_ohlcv计算
        ohlcv_dfs = predefined_ohlcv_dfs
    else:
        raise ValueError(
            "必须提供 simulated_data_config、ohlcv_data_config 或 predefined_ohlcv_dfs 中的一个参数"
        )

    # 初始化变量
    ha_dfs = None
    renko_dfs = None

    # 根据参数决定是否生成 HA 和 Renko 数据，并构建源数据字典
    source_dict = {"ohlcv": ohlcv_dfs}

    # 只有启用的数据类型才会生成并添加到源数据字典
    if other_params and other_params.ha_enable:
        ha_dfs = generate_ha(ohlcv_dfs)
        source_dict["ha"] = ha_dfs

    if other_params and other_params.renko_enable:
        renko_dfs = generate_renko(ohlcv_dfs, other_params.brick_size)
        source_dict["renko"] = renko_dfs

    mapping_df, skip_mapping = generate_time_mapping(ohlcv_dfs, ha_dfs, renko_dfs)

    # skip_mask 占位,暂时全为 False
    skip_mask_series = pl.Series("skip", np.zeros(len(ohlcv_dfs[0])), dtype=pl.Boolean)

    return DataContainer(
        mapping=mapping_df,
        skip_mask=skip_mask_series,
        skip_mapping=skip_mapping,
        source=source_dict,
    )


# 导出所有主要函数，以便兼容原有导入方式
__all__ = [
    "DataGenerationParams",
    "OtherParams",
    "OhlcvDataFetchConfig",
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
    "time_format",
    "fixed_cols",
]
