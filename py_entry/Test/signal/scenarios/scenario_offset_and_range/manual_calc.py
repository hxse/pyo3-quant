"""场景: AND范围偏移 - 手写计算

手写模拟信号计算逻辑
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
    get_data_length,
    create_false_series,
    compare_series,
    combine_and,
    create_signal_dataframe,
)


def calculate_entry_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """
    手写模拟 entry_long 信号计算

    条件：close, ohlcv_15m, &0-2 > sma_0, ohlcv_15m, 0

    逻辑：
    - &0-2 表示 offset 0, 1, 2（最近3根K线）
    - 都必须满足条件（AND逻辑）
    - 即：close[0] > sma[0] AND close[1] > sma[0] AND close[2] > sma[0]
    """
    # 提取数据
    close = get_mapped_ohlcv(mapped_data_pack, "ohlcv_15m", "close")
    sma = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "sma_0")

    # 计算每个offset的条件
    cond_0 = compare_series(close, sma, ">", offset_left=0)  # 当前K线
    cond_1 = compare_series(close, sma, ">", offset_left=1)  # 前1根K线
    cond_2 = compare_series(close, sma, ">", offset_left=2)  # 前2根K线

    # AND逻辑：所有条件都必须满足
    return combine_and(cond_0, cond_1, cond_2)


def calculate_exit_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """exit_long 为 None，返回全 False"""
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_entry_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """entry_short 为 None，返回全 False"""
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_exit_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """exit_short 为 None，返回全 False"""
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_signals(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.DataFrame:
    """
    计算所有信号并返回DataFrame

    这是场景的统一接口函数
    """
    entry_long = calculate_entry_long(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )
    exit_long = calculate_exit_long(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )
    entry_short = calculate_entry_short(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )
    exit_short = calculate_exit_short(
        signal_params,
        data_pack,
        result_pack,
        mapped_data_pack,
        mapped_result_pack,
    )

    return create_signal_dataframe(entry_long, exit_long, entry_short, exit_short)
