"""场景: 简化语法 - 手写计算

验证简化语法解析是否正确映射到默认数据源和偏移量
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
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
    entry_long: close > sma_10
    Implies: close, ohlcv_15m, 0 > sma_10, ohlcv_15m, 0 (assuming base_data_key is ohlcv_15m)
    """
    # base_data_key is usually ohlcv_15m in tests
    base_key = data_container.base_data_key

    close = get_mapped_ohlcv(mapped_data_container, base_key, "close")
    sma = get_mapped_indicator(mapped_backtest_summary, base_key, "sma_10")

    return compare_series(close, sma, ">", offset_left=0, offset_right=0)


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_long: close, , > sma_10, ,
    Implies: close, ohlcv_15m, 0 > sma_10, ohlcv_15m, 0
    """
    base_key = data_container.base_data_key

    close = get_mapped_ohlcv(mapped_data_container, base_key, "close")
    sma = get_mapped_indicator(mapped_backtest_summary, base_key, "sma_10")

    return compare_series(close, sma, ">", offset_left=0, offset_right=0)


def calculate_entry_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    entry_short: close, , 1 > sma_10
    Implies: close, ohlcv_15m, 1 > sma_10, ohlcv_15m, 0
    """
    base_key = data_container.base_data_key

    close = get_mapped_ohlcv(mapped_data_container, base_key, "close")
    sma = get_mapped_indicator(mapped_backtest_summary, base_key, "sma_10")

    return compare_series(close, sma, ">", offset_left=1, offset_right=0)


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_short: close > sma_10, , 1
    Implies: close, ohlcv_15m, 0 > sma_10, ohlcv_15m, 1
    """
    base_key = data_container.base_data_key

    close = get_mapped_ohlcv(mapped_data_container, base_key, "close")
    sma = get_mapped_indicator(mapped_backtest_summary, base_key, "sma_10")

    return compare_series(close, sma, ">", offset_left=0, offset_right=1)


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
