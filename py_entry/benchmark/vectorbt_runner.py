import time
import numpy as np
import pandas as pd
import vectorbt as vbt  # type: ignore
from .config import STRATEGY_A_PARAMS, STRATEGY_B_PARAMS, STRATEGY_C_PARAMS


def run_single_backtest(df: pd.DataFrame, strategy: str = "A") -> float:
    """单次回测，返回耗时"""
    close = df["close"]

    start = time.perf_counter()

    if strategy == "A":
        # 策略 A: SMA + TSL (with crossover)
        sma_fast = vbt.MA.run(close, window=20).ma
        sma_slow = vbt.MA.run(close, window=60).ma

        # Crossover: 当前 > AND 前值 <=
        entries = (sma_fast > sma_slow) & (sma_fast.shift(1) <= sma_slow.shift(1))
        exits = (sma_fast < sma_slow) & (sma_fast.shift(1) >= sma_slow.shift(1))

        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            init_cash=10000.0,
            sl_stop=0.02,
            sl_trail=True,
            freq="15m",
        )
    elif strategy == "B":
        # 策略 B: EMA + RSI + TSL (with crossover)
        ema_fast = vbt.MA.run(close, window=12, ewm=True).ma
        ema_slow = vbt.MA.run(close, window=26, ewm=True).ma
        rsi = vbt.RSI.run(close, window=14).rsi

        # EMA crossover + RSI filter
        ema_cross_up = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        ema_cross_down = (ema_fast < ema_slow) & (
            ema_fast.shift(1) >= ema_slow.shift(1)
        )

        entries = ema_cross_up & (rsi < 50.0)
        exits = ema_cross_down | (rsi > 80.0)

        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            init_cash=10000.0,
            sl_stop=0.02,
            sl_trail=True,
            freq="15m",
        )
    elif strategy == "C":
        # 策略 C: 无指标 - 仅价格比较 (close > prev_close)
        # 双方都使用相同的简单策略，纯回测引擎对比
        entries = close > close.shift(1)
        exits = close < close.shift(1)

        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            init_cash=10000.0,
            sl_stop=0.02,
            sl_trail=True,
            freq="15m",
        )

    # Access metrics to force computation
    _ = pf.total_return()

    return time.perf_counter() - start


def run_optimization(df: pd.DataFrame, samples: int, strategy: str = "A") -> float:
    """随机采样优化，返回耗时"""
    if strategy == "A":
        params = STRATEGY_A_PARAMS
    elif strategy == "B":
        params = STRATEGY_B_PARAMS
    else:
        params = STRATEGY_C_PARAMS
    close = df["close"]

    start = time.perf_counter()

    # 固定随机种子
    np.random.seed(42)

    if strategy == "A":
        # 策略 A: SMA + TSL
        p_sma_fast = np.random.randint(
            int(params["sma_fast"][0]), int(params["sma_fast"][1]) + 1, samples
        )
        p_sma_slow = np.random.randint(
            int(params["sma_slow"][0]), int(params["sma_slow"][1]) + 1, samples
        )
        p_tsl = np.random.uniform(params["tsl_pct"][0], params["tsl_pct"][1], samples)

        unique_fast = np.unique(p_sma_fast)
        unique_slow = np.unique(p_sma_slow)

        mas_fast = vbt.MA.run(close, window=unique_fast).ma
        mas_slow = vbt.MA.run(close, window=unique_slow).ma

        fast_ma_large = mas_fast[p_sma_fast]
        slow_ma_large = mas_slow[p_sma_slow]

        first_fast = fast_ma_large.values
        first_slow = slow_ma_large.values
        prev_fast = np.roll(first_fast, 1, axis=0)
        prev_slow = np.roll(first_slow, 1, axis=0)
        prev_fast[0, :] = np.nan
        prev_slow[0, :] = np.nan

        # Crossover
        entries = (first_fast > first_slow) & (prev_fast <= prev_slow)
        exits = (first_fast < first_slow) & (prev_fast >= prev_slow)

        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            init_cash=10000.0,
            sl_stop=p_tsl,
            sl_trail=True,
            freq="15m",
        )
    elif strategy == "B":
        # 策略 B: EMA + RSI + TSL
        p_ema_fast = np.random.randint(
            int(params["ema_fast"][0]), int(params["ema_fast"][1]) + 1, samples
        )
        p_ema_slow = np.random.randint(
            int(params["ema_slow"][0]), int(params["ema_slow"][1]) + 1, samples
        )
        p_rsi_period = np.random.randint(
            int(params["rsi_period"][0]), int(params["rsi_period"][1]) + 1, samples
        )
        p_tsl = np.random.uniform(params["tsl_pct"][0], params["tsl_pct"][1], samples)

        unique_fast = np.unique(p_ema_fast)
        unique_slow = np.unique(p_ema_slow)
        unique_rsi = np.unique(p_rsi_period)

        emas_fast = vbt.MA.run(close, window=unique_fast, ewm=True).ma
        emas_slow = vbt.MA.run(close, window=unique_slow, ewm=True).ma
        rsis = vbt.RSI.run(close, window=unique_rsi).rsi

        fast_ma_large = emas_fast[p_ema_fast]
        slow_ma_large = emas_slow[p_ema_slow]
        rsi_large = rsis[p_rsi_period]

        first_fast = fast_ma_large.values
        first_slow = slow_ma_large.values
        rsi_vals = rsi_large.values
        prev_fast = np.roll(first_fast, 1, axis=0)
        prev_slow = np.roll(first_slow, 1, axis=0)
        prev_fast[0, :] = np.nan
        prev_slow[0, :] = np.nan

        # EMA crossover + RSI filter
        ema_cross_up = (first_fast > first_slow) & (prev_fast <= prev_slow)
        ema_cross_down = (first_fast < first_slow) & (prev_fast >= prev_slow)

        entries = ema_cross_up & (rsi_vals < 50.0)
        exits = ema_cross_down | (rsi_vals > 80.0)

        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            init_cash=10000.0,
            sl_stop=p_tsl,
            sl_trail=True,
            freq="15m",
        )
    else:
        # 策略 C: 无指标 - 仅价格比较 (close > prev_close)
        # 双方都使用相同的简单策略，纯回测引擎对比
        p_tsl = np.random.uniform(params["tsl_pct"][0], params["tsl_pct"][1], samples)

        close_arr = close.values
        prev_close_arr = np.roll(close_arr, 1)
        prev_close_arr[0] = np.nan

        # 构建 (num_bars, num_samples) 的信号矩阵
        entries = np.tile(close_arr > prev_close_arr, (samples, 1)).T
        exits = np.tile(close_arr < prev_close_arr, (samples, 1)).T

        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            init_cash=10000.0,
            sl_stop=p_tsl,
            sl_trail=True,
            freq="15m",
        )

    _ = pf.total_return()

    return time.perf_counter() - start
