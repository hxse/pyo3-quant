"""场景: 综合场景 - 手写计算

手写模拟综合场景计算
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
    Enter Long:
      (15m Close > 15m BB Upper)
      AND
      (1h RSI > 50)
      AND
      (4h SMA_10 > 4h SMA_30)
    """
    # 15m 条件
    close_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    bb_upper = get_mapped_indicator(
        mapped_backtest_summary, "ohlcv_15m", "bbands_20_upper"
    )
    cond_15m = compare_series(close_15m, bb_upper, ">", offset_left=0)

    # 1h 条件 (数据已经在 prepare_mapped_data 中对齐到 15m 时间轴)

    # 1h RSI
    rsi_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "rsi_14")
    rsi_threshold = signal_params["rsi_midline"].value
    cond_1h_raw = compare_series(rsi_1h, rsi_threshold, ">", offset_left=0)

    # 4h SMA
    sma_10_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "sma_10")
    sma_30_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "sma_30")
    cond_4h_raw = compare_series(sma_10_4h, sma_30_4h, ">", offset_left=0)

    # 数据已经在 prepare_mapped_data 中对齐到 15m 时间轴，无需再使用 join_asof
    # 直接组合条件
    # fill_null(False) 很重要，因为开始阶段可能没有高周期数据
    final_cond = cond_15m & cond_1h_raw.fill_null(False) & cond_4h_raw.fill_null(False)

    return final_cond


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    Exit Long:
      (15m Close < 15m BB Lower)
      OR
      (1h RSI < 30)
    """
    # 15m 条件
    close_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    bb_lower = get_mapped_indicator(
        mapped_backtest_summary, "ohlcv_15m", "bbands_20_lower"
    )
    cond_15m = compare_series(close_15m, bb_lower, "<", offset_left=0)

    # 1h 条件
    rsi_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "rsi_14")
    rsi_oversold = signal_params["rsi_oversold"].value
    cond_1h_raw = compare_series(rsi_1h, rsi_oversold, "<", offset_left=0)

    # 数据已经在 prepare_mapped_data 中对齐到 15m 时间轴，无需再使用 join_asof
    # 直接组合条件 (OR)
    final_cond = cond_15m | cond_1h_raw.fill_null(False)

    return final_cond


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
