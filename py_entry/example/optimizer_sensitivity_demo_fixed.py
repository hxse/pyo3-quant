import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from loguru import logger
from py_entry.runner.backtest import Backtest
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.types import (
    SensitivityConfig,
    OptimizeMetric,
    Param,
    BacktestParams,
    SettingContainer,
    ExecutionStage,
    SignalTemplate,
    SignalGroup,
    LogicOp,
)


def run_sensitivity_demo():
    logger.info("Starting Sensitivity Analysis Demo...")

    # 1. Setup Data Source (Simulated)
    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=1000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 2. Define Params (similar to optimizer demo but simpler)
    indicators = {
        "ohlcv_15m": {
            "sma": {"period": Param(value=14, optimize=True, min=5, max=50, step=1)}
        }
    }

    signal_params = {}

    backtest_params = BacktestParams(
        initial_capital=10000.0, fee_fixed=0, fee_pct=0.0005
    )

    # Signal Template (SMA crossover logic for demo)
    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND, comparisons=["close,ohlcv_15m,0 x> sma,ohlcv_15m,0"]
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND, comparisons=["close,ohlcv_15m,0 x< sma,ohlcv_15m,0"]
        ),
    )

    # Engine Settings
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE, return_only_final=True
    )

    # Initialize Backtest
    bt = Backtest(
        data_source=data_config,
        indicators=indicators,
        signal=signal_params,
        backtest=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        enable_timing=True,
    )

    # 3. Config for Sensitivity
    config = SensitivityConfig(
        jitter_ratio=0.1,  # 10% jitter
        n_samples=20,  # 20 samples for demo
        distribution="normal",
        metric=OptimizeMetric.CalmarRatioRaw,  # or TotalReturn
        seed=42,
    )

    logger.info("Running sensitivity analysis...")
    try:
        # We need to run optimize or just sensitivity?
        # Sensitivity usually runs around a "center" param set.
        # By default it uses current params in `bt`.
        # Since we defined `optimize=True` for SMA period=14, it will jitter around 14.

        result = bt.sensitivity(config=config)

        # 4. Report
        print("\nSensitivity Analysis Result:")
        print(f"Target Metric: {result.target_metric}")
        print(f"Original Value: {result.original_value:.4f}")
        print(f"Mean: {result.mean:.4f}")
        print(f"Std Dev: {result.std:.4f}")
        print(f"CV (Coef of Var): {result.cv:.4f}")
        print(f"Min: {result.min:.4f}")
        print(f"Max: {result.max:.4f}")

        print("\nSamples (first 5):")
        for i, sample in enumerate(result.samples[:5]):
            print(
                f"  Sample {i}: Values={sample.values}, Metric={sample.metric_value:.4f}"
            )

        print("\nSuccess!")

        # Optional: Plot
        # result.plot()

    except Exception as e:
        logger.error(f"Sensitivity analysis failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    run_sensitivity_demo()
