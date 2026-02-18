import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from loguru import logger
from py_entry.runner.backtest import Backtest
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.strategies import get_strategy
from py_entry.strategies.base import StrategyConfig
from py_entry.types import (
    PerformanceParams,
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


def get_sensitivity_demo_config() -> StrategyConfig:
    """获取 sensitivity_demo 示例的完整策略配置。"""
    cfg = get_strategy("mtf_bbands_rsi_sma")
    if not isinstance(cfg.data_config, DataGenerationParams):
        raise TypeError("mtf_bbands_rsi_sma.data_config 必须为 DataGenerationParams")

    # 1. Setup Data Source (Simulated)
    data_config = cfg.data_config.model_copy(
        update={
            "timeframes": ["15m"],
            "start_time": get_utc_timestamp_ms("2025-01-01 00:00:00"),
            "num_bars": 1000,
            "fixed_seed": 42,
            "base_data_key": "ohlcv_15m",
        }
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
        execution_stage=ExecutionStage.Performance, return_only_final=True
    )

    return StrategyConfig(
        name="sensitivity_demo",
        description="参数敏感性分析示例（SMA 单参数）",
        data_config=data_config,
        indicators_params=indicators,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
        performance_params=PerformanceParams(metrics=[]),
    )


def get_sensitivity_config() -> SensitivityConfig:
    """获取 sensitivity 分析参数配置。"""
    return SensitivityConfig(
        jitter_ratio=0.1,  # 10% jitter
        n_samples=20,  # 20 samples for demo
        distribution="normal",
        metric=OptimizeMetric.CalmarRatioRaw,  # or TotalReturn
        seed=42,
    )


def run_sensitivity_demo(
    *,
    config: StrategyConfig | None = None,
    sensitivity_config: SensitivityConfig | None = None,
) -> dict[str, object]:
    """运行敏感性分析示例，返回摘要结果供 notebook 或脚本调用。"""
    logger.info("Starting Sensitivity Analysis Demo...")
    cfg = config if config is not None else get_sensitivity_demo_config()

    # Initialize Backtest
    bt = Backtest(
        data_source=cfg.data_config,
        indicators=cfg.indicators_params,
        signal=cfg.signal_params,
        backtest=cfg.backtest_params,
        performance=cfg.performance_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
        enable_timing=True,
    )

    # 3. Config for Sensitivity
    sens_cfg = (
        sensitivity_config
        if sensitivity_config is not None
        else get_sensitivity_config()
    )

    logger.info("Running sensitivity analysis...")
    # We need to run optimize or just sensitivity?
    # Sensitivity usually runs around a "center" param set.
    # By default it uses current params in `bt`.
    # Since we defined `optimize=True` for SMA period=14, it will jitter around 14.

    result = bt.sensitivity(config=sens_cfg)

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
        print(f"  Sample {i}: Values={sample.values}, Metric={sample.metric_value:.4f}")

    print("\nSuccess!")
    return {
        "target_metric": str(result.target_metric),
        "original_value": result.original_value,
        "mean": result.mean,
        "std": result.std,
        "cv": result.cv,
        "min": result.min,
        "max": result.max,
        "sample_count": len(result.samples),
    }


def format_result_for_ai(summary: dict[str, object]) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== SENSITIVITY_DEMO_RESULT ===")
    lines.append(f"target_metric={summary.get('target_metric')}")
    lines.append(
        f"original_value={summary.get('original_value')}, mean={summary.get('mean')}, "
        f"std={summary.get('std')}, cv={summary.get('cv')}"
    )
    lines.append(f"min={summary.get('min')}, max={summary.get('max')}")
    lines.append(f"sample_count={summary.get('sample_count')}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑用于 AI 调试与结果读取。
    run_summary = run_sensitivity_demo()
    print(format_result_for_ai(run_summary))
