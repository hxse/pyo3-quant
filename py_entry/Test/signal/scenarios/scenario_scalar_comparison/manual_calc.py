"""场景: 数值字面量比较 - 手写计算

手写模拟信号计算逻辑，验证数值字面量比较是否正确
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    compare_series,
    create_signal_dataframe,
)


def calculate_entry_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    entry_long: rsi_14 < 30.0
    """
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    return compare_series(rsi, 30.0, "<", offset_left=0)


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_long: rsi_14 > 70
    """
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    return compare_series(rsi, 70.0, ">", offset_left=0)


def calculate_entry_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    entry_short: rsi_14 > 70.0
    """
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    return compare_series(rsi, 70.0, ">", offset_left=0)


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_short: rsi_14 < 30
    """
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    return compare_series(rsi, 30.0, "<", offset_left=0)


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
    entry_long = calculate_entry_long(
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
    entry_short = calculate_entry_short(
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

    return create_signal_dataframe(entry_long, exit_long, entry_short, exit_short)
