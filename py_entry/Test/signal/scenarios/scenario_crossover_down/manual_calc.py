"""场景: 向下交叉 - 手写计算"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
    get_data_length,
    create_false_series,
    compare_crossover,
    create_signal_dataframe,
)


def calculate_entry_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_exit_long(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_entry_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    """
    条件：close, ohlcv_15m, 0 x< sma_0, ohlcv_15m, 0

    逻辑：
    - x< 表示向下跌破
    - 即：当前 close < sma AND 前一个 close >= sma
    """
    # 从映射后的数据中提取
    close = get_mapped_ohlcv(mapped_data_pack, "ohlcv_15m", "close")
    sma = get_mapped_indicator(mapped_result_pack, "ohlcv_15m", "sma_0")

    # 使用交叉比较工具函数
    return compare_crossover(close, sma, "<")


def calculate_exit_short(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.Series:
    length = get_data_length(mapped_data_pack)
    return create_false_series(length)


def calculate_signals(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.DataFrame:
    """计算所有信号"""
    return create_signal_dataframe(
        calculate_entry_long(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
        calculate_exit_long(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
        calculate_entry_short(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
        calculate_exit_short(
            signal_params,
            data_pack,
            result_pack,
            mapped_data_pack,
            mapped_result_pack,
        ),
    )
