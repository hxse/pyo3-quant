"""场景: 当前值位于区间内 - 手写计算"""

import math
import polars as pl
from py_entry.Test.signal.utils import (
    create_false_series,
    create_signal_dataframe,
    get_data_length,
    get_mapped_indicator,
)


def calculate_entry_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """条件：rsi, ohlcv_15m, 0 in 30..70"""
    rsi_s = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi")
    low = min(30.0, 70.0)
    high = max(30.0, 70.0)

    result = []
    for val in rsi_s.to_list():
        if val is None or math.isnan(val):
            result.append(False)
            continue
        result.append(low <= val <= high)

    return pl.Series("entry_long", result, dtype=pl.Boolean)


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    return create_false_series(get_data_length(mapped_data_container))


def calculate_entry_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    return create_false_series(get_data_length(mapped_data_container))


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    return create_false_series(get_data_length(mapped_data_container))


def calculate_signals(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.DataFrame:
    return create_signal_dataframe(
        calculate_entry_long(
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
        calculate_entry_short(
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
