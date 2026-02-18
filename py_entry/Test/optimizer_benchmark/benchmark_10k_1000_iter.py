import time
import sys
import os
from loguru import logger
import pytest  # keeps data generation happy if it relies on fixtures, but we'll try to use raw classes

# Ensure python path is correct
sys.path.append(os.getcwd())

from py_entry.types import (
    OptunaConfig,
    OptimizerConfig,
    OptimizeMetric,
    Param,
    ExecutionStage,
    PerformanceParams,
    PerformanceMetric,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.Test.shared import (
    make_backtest_params,
    make_backtest_runner,
    make_engine_settings,
    make_ma_cross_template,
)


def run_benchmark():
    logger.info("=========================================================")
    logger.info("Benchmark: 10,000 Bars, 1,000 Iterations (Rust vs Optuna)")
    logger.info("=========================================================")

    # 1. Configuration
    N_BARS = 10000
    N_ITERATIONS = 1000
    SEED = 42

    # 2. Data Setup
    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=N_BARS,
        fixed_seed=SEED,
        base_data_key="ohlcv_15m",
    )

    # 3. Indicator Params (Standard Setup)
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param(20, min=10, max=100, step=5, optimize=True),
            },
            "sma_slow": {
                "period": Param(50, min=20, max=200, step=10, optimize=True),
            },
        }
    }

    # 4. Signal Template (SMA Crossover)
    signal_template = make_ma_cross_template(
        fast_name="sma_fast",
        slow_name="sma_slow",
        source_key="ohlcv_15m",
    )

    # 5. Backtest Params
    backtest_params = make_backtest_params(
        fee_fixed=0.0,
        fee_pct=0.0005,
        sl_pct=Param(0.02, min=0.01, max=0.05, optimize=True),
        tp_pct=Param(0.04, min=0.02, max=0.10, optimize=True),
        # Risk management
        sl_atr=Param(2.0, min=1.0, max=5.0, step=0.5, optimize=True),
        tsl_atr=Param(3.0, min=1.0, max=5.0, step=0.5, optimize=True),
        atr_period=Param(14),
        # Default flags
        sl_exit_in_bar=True,
        tp_exit_in_bar=True,
        sl_trigger_mode=True,
        tp_trigger_mode=True,
        tsl_trigger_mode=True,
    )

    # 6. Performance Params
    performance_params = PerformanceParams(
        metrics=[
            PerformanceMetric.CalmarRatio,
            PerformanceMetric.TotalReturn,
            PerformanceMetric.MaxDrawdown,
        ]
    )

    # 7. Engine Settings
    engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Performance,
        return_only_final=True,
    )

    # 8. Init Backtest
    bt = make_backtest_runner(
        enable_timing=False,  # Disable internal timing to reduce noise
        data_source=data_config,
        indicators=indicators_params,
        backtest=backtest_params,
        performance=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        signal={},
    )

    logger.info(f"Data ready. Starting optimization with {N_ITERATIONS} iterations...")

    # -------------------------------------------------------------------------
    # ROUND 1: Rust Optimizer
    # -------------------------------------------------------------------------
    logger.info("---------------------------------------------------------")
    logger.info("[Rust Optimizer] Starting...")

    # Rust optimizer 使用 10 轮 * 100 样本，总样本与 Optuna 对齐。
    rust_config = OptimizerConfig(
        max_samples=N_ITERATIONS,
        samples_per_round=100,
        max_rounds=10,
        stop_patience=10,  # Don't stop early
        min_samples=N_ITERATIONS,  # Force it to run at least this many
        optimize_metric=OptimizeMetric.CalmarRatioRaw,
    )

    t0_rust = time.perf_counter()
    rust_result = bt.optimize(rust_config)
    t_rust = time.perf_counter() - t0_rust

    logger.info(f"[Rust Optimizer] Done. Time: {t_rust:.4f}s")
    logger.info(f"[Rust Optimizer] Best Calmar: {rust_result.optimize_value:.4f}")

    # -------------------------------------------------------------------------
    # ROUND 2: Optuna
    # -------------------------------------------------------------------------
    logger.info("---------------------------------------------------------")
    logger.info("[Optuna] Starting...")

    optuna_config = OptunaConfig(
        n_trials=N_ITERATIONS,
        batch_size=100,  # Match samples per round roughly
        seed=SEED + 1,
        metric=OptimizeMetric.CalmarRatioRaw,
        show_progress_bar=True,
    )

    t0_optuns = time.perf_counter()
    optuna_result = bt.optimize_with_optuna(optuna_config)
    t_optuna = time.perf_counter() - t0_optuns

    logger.info(f"[Optuna] Done. Time: {t_optuna:.4f}s")
    logger.info(f"[Optuna] Best Calmar: {optuna_result.best_value:.4f}")

    # -------------------------------------------------------------------------
    # Comparison
    # -------------------------------------------------------------------------
    logger.info("=========================================================")
    logger.info("                   FINAL RESULTS                         ")
    logger.info("=========================================================")
    logger.info(
        f"{'Optimizer':<15} | {'Time (s)':<10} | {'Speed (it/s)':<12} | {'Qual (Calmar)':<12}"
    )
    logger.info("-" * 55)

    speed_rust = N_ITERATIONS / t_rust
    speed_optuna = N_ITERATIONS / t_optuna

    logger.info(
        f"{'Rust':<15} | {t_rust:<10.3f} | {speed_rust:<12.1f} | {rust_result.optimize_value:<12.4f}"
    )
    logger.info(
        f"{'Optuna':<15} | {t_optuna:<10.3f} | {speed_optuna:<12.1f} | {optuna_result.best_value:<12.4f}"
    )
    logger.info("-" * 55)

    speed_up = t_optuna / t_rust
    logger.info(f"Speedup: Rust is {speed_up:.1f}x faster than Optuna")
    logger.info("=========================================================")


if __name__ == "__main__":
    run_benchmark()
