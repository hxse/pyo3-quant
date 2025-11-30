"""场景: 参数引用 - 手写计算

手写模拟信号计算逻辑，验证参数引用是否正确
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
    enter_long: rsi_14 < $rsi_buy_threshold
    """
    # 提取数据
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")

    # 提取参数
    # signal_params 是 Dict[str, Param]
    threshold = signal_params["rsi_buy_threshold"].value

    # 计算条件
    # compare_series 支持标量作为 right_operand
    return compare_series(rsi, threshold, "<", offset_left=0)


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_long: rsi_14 > $rsi_sell_threshold
    """
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_sell_threshold"].value
    return compare_series(rsi, threshold, ">", offset_left=0)


def calculate_enter_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    enter_short: rsi_14 > $rsi_sell_threshold
    """
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_sell_threshold"].value
    return compare_series(rsi, threshold, ">", offset_left=0)


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_short: rsi_14 < $rsi_buy_threshold
    """
    rsi = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_14")
    threshold = signal_params["rsi_buy_threshold"].value
    return compare_series(rsi, threshold, "<", offset_left=0)


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
