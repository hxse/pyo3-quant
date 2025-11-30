"""场景: OR逻辑组合 - 手写计算

手写模拟 OR 逻辑组合计算
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
    get_data_length,
    create_false_series,
    compare_series,
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
    enter_long: (close > sma_20) OR (rsi_14 > 70)
    """
    # 从映射后的数据中提取
    close = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    sma = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "sma_20")
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_threshold"].value

    # 条件1: close > sma
    cond1 = compare_series(close, sma, ">", offset_left=0)

    # 条件2: rsi > 70
    cond2 = compare_series(rsi, threshold, ">", offset_left=0)

    # 组合: OR
    return cond1 | cond2


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
    """
    计算所有信号并返回DataFrame
    """
    enter_long = calculate_enter_long(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )
    exit_long = calculate_exit_long(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )
    enter_short = calculate_enter_short(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )
    exit_short = calculate_exit_short(
        signal_params,
        data_container,
        backtest_summary,
        mapped_data_container,
        mapped_backtest_summary,
    )

    return create_signal_dataframe(enter_long, exit_long, enter_short, exit_short)
