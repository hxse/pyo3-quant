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
    DirectDataConfig,
)
from .time_utils import parse_timeframe
from .ohlcv_generator import generate_multi_timeframe_ohlcv
from .heikin_ashi_generator import calculate_heikin_ashi
from .renko_generator import calculate_renko
from .time_mapping import generate_time_mapping
from py_entry.types import DataContainer
from py_entry.io import (
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
            - DirectDataConfig: 直接数据配置
        other_params: 其他参数配置对象,如果为None则使用默认值

    Returns:
        包含以下键的字典:
    """
    source_dict: dict[str, pl.DataFrame] = {}
    base_data_key: str = ""

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
            volatility=simulated_data_config.volatility,
            trend=simulated_data_config.trend,
            gap_factor=simulated_data_config.gap_factor,
            extreme_prob=simulated_data_config.extreme_prob,
            extreme_mult=simulated_data_config.extreme_mult,
            allow_gaps=simulated_data_config.allow_gaps,
        )

        # 将列表转换为字典
        for tf, df in zip(simulated_data_config.timeframes, ohlcv_dfs):
            source_dict[f"ohlcv_{tf}"] = df

        base_data_key = simulated_data_config.base_data_key

    elif is_fetched_data(data_source):
        # 从服务器获取OHLCV数据
        ohlcv_data_config = cast(OhlcvDataFetchConfig, data_source)  # 类型断言

        for timeframe in ohlcv_data_config.timeframes:
            # 为每个时间周期创建单独的配置对象
            single_ohlcv_config = OhlcvDataConfig(
                config=ohlcv_data_config.config,
                exchange_name=ohlcv_data_config.exchange_name,
                symbol=ohlcv_data_config.symbol,
                period=timeframe,
                start_time=ohlcv_data_config.start_time,
                count=ohlcv_data_config.count,
                enable_cache=ohlcv_data_config.enable_cache,
                enable_test=ohlcv_data_config.enable_test,
                sandbox=ohlcv_data_config.sandbox,
                file_type=ohlcv_data_config.file_type,
                cache_size=ohlcv_data_config.cache_size,
                page_size=ohlcv_data_config.page_size,
            )
            result = get_ohlcv_data(single_ohlcv_config)
            ohlcv_df = convert_to_ohlcv_dataframe(result)
            if ohlcv_df is not None:
                source_dict[f"ohlcv_{timeframe}"] = ohlcv_df
            else:
                raise ValueError(f"无法从服务器获取时间周期 {timeframe} 的OHLCV数据")

        base_data_key = ohlcv_data_config.base_data_key

    elif is_predefined_data(data_source):
        # 使用预定义的OHLCV数据
        config = cast(DirectDataConfig, data_source)  # 类型断言
        source_dict = config.data
        base_data_key = config.base_data_key
    else:
        raise ValueError("不支持的数据源类型")

    # 只有启用的数据类型才会生成并添加到源数据字典
    # 注意：这里我们假设 source_dict 中以 "ohlcv_" 开头的都是 OHLCV 数据
    # 并且我们为每个 OHLCV 数据生成对应的 HA 和 Renko 数据

    if other_params and other_params.ha_timeframes:
        for timeframe in other_params.ha_timeframes:
            ohlcv_key = f"ohlcv_{timeframe}"
            if ohlcv_key not in source_dict:
                raise ValueError(
                    f"无法生成 HA 数据：找不到对应的 OHLCV 数据 {ohlcv_key}"
                )

            source_dict[f"ha_{timeframe}"] = calculate_heikin_ashi(
                source_dict[ohlcv_key]
            )

    if other_params and other_params.renko_timeframes:
        for timeframe in other_params.renko_timeframes:
            ohlcv_key = f"ohlcv_{timeframe}"
            if ohlcv_key not in source_dict:
                raise ValueError(
                    f"无法生成 Renko 数据：找不到对应的 OHLCV 数据 {ohlcv_key}"
                )

            source_dict[f"renko_{timeframe}"] = calculate_renko(
                source_dict[ohlcv_key], other_params.brick_size
            )

    mapping_df, skip_mapping = generate_time_mapping(source_dict, base_data_key)

    # skip_mask 占位,暂时全为 False
    # 使用基准数据的长度
    base_len = len(source_dict[base_data_key])
    skip_mask_df = pl.DataFrame(
        {"skip": pl.Series("skip", np.zeros(base_len), dtype=pl.Boolean)}
    )

    return DataContainer(
        mapping=mapping_df,
        skip_mask=skip_mask_df,
        skip_mapping=skip_mapping,
        source=source_dict,
        base_data_key=base_data_key,
    )
