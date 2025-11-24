"""
数据生成器核心逻辑
"""

import polars as pl
import numpy as np
from datetime import datetime
from typing import cast

from .config import DataGenerationParams, OhlcvDataFetchConfig, OtherParams
from .type_guards import (
    DataSourceConfig,
    is_simulated_data,
    is_fetched_data,
    is_predefined_data,
)
from .time_utils import parse_timeframe
from .ohlcv_generator import generate_multi_timeframe_ohlcv
from .heikin_ashi_generator import generate_ha
from .renko_generator import generate_renko
from .time_mapping import generate_time_mapping
from py_entry.data_conversion.types import DataContainer
from py_entry.data_conversion.file_utils import (
    get_ohlcv_data,
    convert_to_ohlcv_dataframe,
    OhlcvDataConfig,
)


def generate_data_dict(
    data_source: DataSourceConfig,
    other_params: OtherParams | None = None,
) -> DataContainer:
    """
    生成完整的数据字典

    Args:
        data_source: 数据源配置，可以是三种类型之一：
            - DataGenerationParams: 模拟数据生成参数
            - OhlcvDataFetchConfig: OHLCV数据获取配置
            - list[pl.DataFrame]: 预定义的OHLCV DataFrame列表
        other_params: 其他参数配置对象,如果为None则使用默认值

    Returns:
        包含以下键的字典:
    """
    if is_simulated_data(data_source):
        # 使用模拟数据配置生成数据
        simulated_data_config = cast(DataGenerationParams, data_source)  # 类型断言
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
    elif is_fetched_data(data_source):
        # 从服务器获取OHLCV数据
        ohlcv_data_config = cast(OhlcvDataFetchConfig, data_source)  # 类型断言
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
    elif is_predefined_data(data_source):
        # 使用预定义的OHLCV数据
        ohlcv_dfs = cast(list[pl.DataFrame], data_source)  # 类型断言
    else:
        raise ValueError("不支持的数据源类型")

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
