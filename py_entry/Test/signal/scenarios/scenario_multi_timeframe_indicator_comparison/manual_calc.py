"""场景: 多时间周期指标比较 - 手写计算

手写模拟多时间周期指标比较计算
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
    Enter Long:
      (15m EMA > 1h EMA > 4h EMA)
      AND
      (15m RSI > 1h RSI > 4h RSI)
      AND
      (15m Close > 1h EMA)
      AND
      (15m Close > 1h BB Middle)
    """
    # 1. EMA多时间周期比较
    ema_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_0")
    ema_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "ema_0")

    # 15分钟EMA > 1小时EMA > 4小时EMA
    ema_cond_1 = compare_series(ema_15m, ema_1h, ">", offset_left=0)
    ema_cond_2 = compare_series(ema_1h, ema_4h, ">", offset_left=0)

    # 2. RSI多时间周期比较
    rsi_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")
    rsi_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "rsi_0")
    rsi_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "rsi_0")

    # 15分钟RSI > 1小时RSI > 4小时RSI
    rsi_cond_1 = compare_series(rsi_15m, rsi_1h, ">", offset_left=0)
    rsi_cond_2 = compare_series(rsi_1h, rsi_4h, ">", offset_left=0)

    # 3. 价格与多时间周期指标比较
    close_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    bb_middle_1h = get_mapped_indicator(
        mapped_backtest_summary, "ohlcv_1h", "bbands_0_middle"
    )

    # 15分钟收盘价 > 1小时EMA
    price_ema_cond = compare_series(close_15m, ema_1h, ">", offset_left=0)
    # 15分钟收盘价 > 1小时布林带中轨
    price_bb_cond = compare_series(close_15m, bb_middle_1h, ">", offset_left=0)

    # 组合所有条件 (AND)
    # fill_null(False) 很重要，因为开始阶段可能没有高周期数据
    final_cond = (
        ema_cond_1
        & ema_cond_2.fill_null(False)
        & rsi_cond_1
        & rsi_cond_2.fill_null(False)
        & price_ema_cond.fill_null(False)
        & price_bb_cond.fill_null(False)
    )

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
      (15m EMA < 1h EMA)
      OR
      (15m RSI < 50)
    """
    # 1. EMA多时间周期趋势反转
    ema_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_0")
    ema_cond = compare_series(ema_15m, ema_1h, "<", offset_left=0)

    # 2. RSI多时间周期动量反转
    rsi_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")
    rsi_threshold = signal_params["rsi_midline"].value
    rsi_cond = compare_series(rsi_15m, rsi_threshold, "<", offset_left=0)

    # 组合条件 (OR)
    final_cond = ema_cond | rsi_cond

    return final_cond


def calculate_entry_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    Enter Short:
      (15m EMA < 1h EMA < 4h EMA)
      AND
      (15m RSI < 1h RSI < 4h RSI)
      AND
      (15m Close < 1h EMA)
      AND
      (15m Close < 1h BB Middle)
    """
    # 1. EMA多时间周期比较
    ema_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_0")
    ema_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "ema_0")

    # 15分钟EMA < 1小时EMA < 4小时EMA
    ema_cond_1 = compare_series(ema_15m, ema_1h, "<", offset_left=0)
    ema_cond_2 = compare_series(ema_1h, ema_4h, "<", offset_left=0)

    # 2. RSI多时间周期比较
    rsi_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")
    rsi_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "rsi_0")
    rsi_4h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_4h", "rsi_0")

    # 15分钟RSI < 1小时RSI < 4小时RSI
    rsi_cond_1 = compare_series(rsi_15m, rsi_1h, "<", offset_left=0)
    rsi_cond_2 = compare_series(rsi_1h, rsi_4h, "<", offset_left=0)

    # 3. 价格与多时间周期指标比较
    close_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    bb_middle_1h = get_mapped_indicator(
        mapped_backtest_summary, "ohlcv_1h", "bbands_0_middle"
    )

    # 15分钟收盘价 < 1小时EMA
    price_ema_cond = compare_series(close_15m, ema_1h, "<", offset_left=0)
    # 15分钟收盘价 < 1小时布林带中轨
    price_bb_cond = compare_series(close_15m, bb_middle_1h, "<", offset_left=0)

    # 组合所有条件 (AND)
    # fill_null(False) 很重要，因为开始阶段可能没有高周期数据
    final_cond = (
        ema_cond_1
        & ema_cond_2.fill_null(False)
        & rsi_cond_1
        & rsi_cond_2.fill_null(False)
        & price_ema_cond.fill_null(False)
        & price_bb_cond.fill_null(False)
    )

    return final_cond


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    Exit Short:
      (15m EMA > 1h EMA)
      OR
      (15m RSI > 50)
    """
    # 1. EMA多时间周期趋势反转
    ema_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_0")
    ema_cond = compare_series(ema_15m, ema_1h, ">", offset_left=0)

    # 2. RSI多时间周期动量反转
    rsi_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")
    rsi_threshold = signal_params["rsi_midline"].value
    rsi_cond = compare_series(rsi_15m, rsi_threshold, ">", offset_left=0)

    # 组合条件 (OR)
    final_cond = ema_cond | rsi_cond

    return final_cond


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
