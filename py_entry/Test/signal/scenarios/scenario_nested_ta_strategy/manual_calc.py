"""场景: 复杂嵌套TA策略 - 手写计算

手写模拟复杂嵌套TA策略的信号计算
"""

import polars as pl
from py_entry.Test.signal.utils import (
    get_mapped_indicator,
    get_mapped_ohlcv,
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
    enter_long:
    (ADX > 25 AND 趋势策略) OR (ADX < 25 AND 震荡策略)

    趋势策略:
    1. adx > 25
    2. ema_0 (15m) > ema_1 (15m)
    3. close (15m) > ema_0 (1h)
    4. (close > close[2]) OR (close > high[1])

    震荡策略:
    1. adx < 25
    2. rsi < 30
    """
    # 提取数据
    close_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    high_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "high")

    ema_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_1")
    rsi_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")
    adx_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "adx_0_adx")

    # 1h数据已在test层面映射到基准周期
    ema_0_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_0")

    # 参数
    adx_threshold = signal_params["adx_threshold"].value
    rsi_oversold = signal_params["rsi_oversold"].value

    # --- 趋势策略 ---
    # 1. adx > 25
    trend_cond1 = compare_series(adx_0_15m, adx_threshold, ">", offset_left=0)

    # 2. ema_0 (15m) > ema_1 (15m)
    trend_cond2 = compare_series(ema_0_15m, ema_1_15m, ">", offset_left=0)

    # 3. close (15m) > ema_0 (1h) - 现在ema_0_1h已经映射到500行
    trend_cond3 = compare_series(close_15m, ema_0_1h, ">", offset_left=0)

    # 4. (close > close[1] AND close > close[2]) OR (close > high[1])
    # &1/2 表示 AND范围：close[0] > close[1] AND close[0] > close[2]
    price_cond1_a = compare_series(
        close_15m, close_15m, ">", offset_left=0, offset_right=1
    )
    price_cond1_b = compare_series(
        close_15m, close_15m, ">", offset_left=0, offset_right=2
    )
    price_cond1 = price_cond1_a & price_cond1_b  # AND范围

    price_cond2 = compare_series(
        close_15m, high_15m, ">", offset_left=0, offset_right=1
    )
    trend_cond4 = price_cond1 | price_cond2

    trend_strategy = trend_cond1 & trend_cond2 & trend_cond3 & trend_cond4

    # --- 震荡策略 ---
    # 1. adx < 25
    range_cond1 = compare_series(adx_0_15m, adx_threshold, "<", offset_left=0)

    # 2. rsi < 30
    range_cond2 = compare_series(rsi_0_15m, rsi_oversold, "<", offset_left=0)

    range_strategy = range_cond1 & range_cond2

    return trend_strategy | range_strategy


def calculate_exit_long(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_long:
    趋势反转 OR 止损
    1. ema_0 (15m) < ema_1 (15m)
    2. rsi > 70
    """
    ema_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_1")
    rsi_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")

    rsi_overbought = signal_params["rsi_overbought"].value

    # 1. 趋势反转
    cond1 = compare_series(ema_0_15m, ema_1_15m, "<", offset_left=0)

    # 2. 止损 (RSI超买)
    cond2 = compare_series(rsi_0_15m, rsi_overbought, ">", offset_left=0)

    return cond1 | cond2


def calculate_enter_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    enter_short:
    (ADX > 25 AND 趋势策略) OR (ADX < 25 AND 震荡策略)

    趋势策略:
    1. adx > 25
    2. ema_0 (15m) < ema_1 (15m)
    3. close (15m) < ema_0 (1h)
    4. (close < close[2]) OR (close < low[1])

    震荡策略:
    1. adx < 25
    2. rsi > 70
    """
    # 提取数据
    close_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "close")
    low_15m = get_mapped_ohlcv(mapped_data_container, "ohlcv_15m", "low")

    ema_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_1")
    rsi_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")
    adx_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "adx_0_adx")

    # 1h数据已在test层面映射到基准周期
    ema_0_1h = get_mapped_indicator(mapped_backtest_summary, "ohlcv_1h", "ema_0")

    # 参数
    adx_threshold = signal_params["adx_threshold"].value
    rsi_overbought = signal_params["rsi_overbought"].value

    # --- 趋势策略 ---
    # 1. adx > 25
    trend_cond1 = compare_series(adx_0_15m, adx_threshold, ">", offset_left=0)

    # 2. ema_0 (15m) < ema_1 (15m)
    trend_cond2 = compare_series(ema_0_15m, ema_1_15m, "<", offset_left=0)

    # 3. close (15m) < ema_0 (1h) - 现在ema_0_1h已经映射到500行
    trend_cond3 = compare_series(close_15m, ema_0_1h, "<", offset_left=0)

    # 4. (close < close[1] AND close < close[2]) OR (close < low[1])
    # &1/2 表示 AND范围：close[0] < close[1] AND close[0] < close[2]
    price_cond1_a = compare_series(
        close_15m, close_15m, "<", offset_left=0, offset_right=1
    )
    price_cond1_b = compare_series(
        close_15m, close_15m, "<", offset_left=0, offset_right=2
    )
    price_cond1 = price_cond1_a & price_cond1_b  # AND范围

    price_cond2 = compare_series(close_15m, low_15m, "<", offset_left=0, offset_right=1)
    trend_cond4 = price_cond1 | price_cond2

    trend_strategy = trend_cond1 & trend_cond2 & trend_cond3 & trend_cond4

    # --- 震荡策略 ---
    # 1. adx < 25
    range_cond1 = compare_series(adx_0_15m, adx_threshold, "<", offset_left=0)

    # 2. rsi > 70
    range_cond2 = compare_series(rsi_0_15m, rsi_overbought, ">", offset_left=0)

    range_strategy = range_cond1 & range_cond2

    return trend_strategy | range_strategy


def calculate_exit_short(
    signal_params,
    data_container,
    backtest_summary,
    mapped_data_container,
    mapped_backtest_summary,
) -> pl.Series:
    """
    exit_short:
    趋势反转 OR 止损
    1. ema_0 (15m) > ema_1 (15m)
    2. rsi < 30
    """
    ema_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_0")
    ema_1_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "ema_1")
    rsi_0_15m = get_mapped_indicator(mapped_backtest_summary, "ohlcv_15m", "rsi_0")

    rsi_oversold = signal_params["rsi_oversold"].value

    # 1. 趋势反转
    cond1 = compare_series(ema_0_15m, ema_1_15m, ">", offset_left=0)

    # 2. 止损 (RSI超卖)
    cond2 = compare_series(rsi_0_15m, rsi_oversold, "<", offset_left=0)

    return cond1 | cond2


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
