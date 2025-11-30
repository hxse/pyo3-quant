"""场景: AND列表偏移 - 手写计算"""

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


def calculate_enter_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    条件：close, ohlcv_15m, &0/1/5 > sma_0, ohlcv_15m, 0

    逻辑：
    - &0/1/5 表示 offset 0, 1, 5 都必须满足（AND逻辑）
    - 即：close[0] > sma[0] AND close[1] > sma[0] AND close[5] > sma[0]
    """
    close = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    sma = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "sma_0")

    cond_0 = compare_series(close, sma, ">", offset_left=0)
    cond_1 = compare_series(close, sma, ">", offset_left=1)
    cond_5 = compare_series(close, sma, ">", offset_left=5)

    # AND逻辑：所有条件都必须满足
    return combine_and(cond_0, cond_1, cond_5)


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    length = get_data_length(mapped_data_container)
    return create_false_series(length)


def calculate_enter_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    length = get_data_length(mapped_data_container)
    return create_false_series(length)


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    length = get_data_length(mapped_data_container)
    return create_false_series(length)


def calculate_signals(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.DataFrame:
    """计算所有信号"""
    return create_signal_dataframe(
        calculate_enter_long(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
        calculate_exit_long(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
        calculate_enter_short(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
        calculate_exit_short(
            signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        ),
    )
