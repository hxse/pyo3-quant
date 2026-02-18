"""优化器超参数调优脚本

用于找出 OptimizerConfig 的最佳默认参数组合。
使用网格搜索测试不同超参数组合在金融场景下的表现。
"""

import itertools
from dataclasses import dataclass
from loguru import logger

from py_entry.types import (
    OptimizerConfig,
    OptimizeMetric,
    ExecutionStage,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.Test.shared import (
    make_backtest_runner,
    make_engine_settings,
    make_optimizer_sma_atr_components,
)


@dataclass
class TuningResult:
    explore_ratio: float
    sigma_ratio: float
    weight_decay: float
    top_k_ratio: float
    calmar_mean: float
    calmar_std: float


def create_backtest(seed: int):
    """创建回测实例"""
    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=6000,
        fixed_seed=seed,
        base_data_key="ohlcv_15m",
    )

    indicators, template, backtest_params = make_optimizer_sma_atr_components(
        source_key="ohlcv_15m"
    )

    engine_settings = make_engine_settings(
        execution_stage=ExecutionStage.Performance, return_only_final=True
    )

    return make_backtest_runner(
        data_source=data_config,
        indicators=indicators,
        signal={},
        backtest=backtest_params,
        signal_template=template,
        engine_settings=engine_settings,
    )


def run_with_config(
    explore_ratio: float,
    sigma_ratio: float,
    weight_decay: float,
    top_k_ratio: float,
    n_runs: int = 50,
) -> TuningResult:
    """用指定超参数运行多次并返回结果"""
    import numpy as np

    results = []
    for seed in range(n_runs):
        bt = create_backtest(seed + 1000)
        config = OptimizerConfig(
            explore_ratio=explore_ratio,
            sigma_ratio=sigma_ratio,
            weight_decay=weight_decay,
            top_k_ratio=top_k_ratio,
            samples_per_round=50,
            max_rounds=6,
            optimize_metric=OptimizeMetric.CalmarRatioRaw,
        )
        opt = bt.optimize(config)
        results.append(opt.optimize_value)

    return TuningResult(
        explore_ratio=explore_ratio,
        sigma_ratio=sigma_ratio,
        weight_decay=weight_decay,
        top_k_ratio=top_k_ratio,
        calmar_mean=np.mean(results),
        calmar_std=np.std(results),
    )


def run_hyperparameter_tuning():
    """运行超参数网格搜索"""
    logger.info("=" * 70)
    logger.info("优化器超参数调优")
    logger.info("=" * 70)

    # 超参数搜索空间
    explore_ratios = [0.15, 0.25, 0.35]
    sigma_ratios = [0.10, 0.15, 0.20]
    weight_decays = [0.05, 0.10, 0.15]
    top_k_ratios = [0.50, 0.70, 0.90]

    # 为节省时间，先只调 explore_ratio 和 sigma_ratio
    # 固定 weight_decay=0.10, top_k_ratio=0.70

    results = []

    logger.info("Phase 1: 调优 explore_ratio 和 sigma_ratio")
    logger.info("-" * 70)

    for exp, sig in itertools.product(explore_ratios, sigma_ratios):
        result = run_with_config(
            explore_ratio=exp,
            sigma_ratio=sig,
            weight_decay=0.10,
            top_k_ratio=0.70,
            n_runs=5,
        )
        results.append(result)
        logger.info(
            f"explore={exp:.2f}, sigma={sig:.2f} -> "
            f"Calmar={result.calmar_mean:.2f} ± {result.calmar_std:.2f}"
        )

    # 找出最佳组合
    best = max(results, key=lambda r: r.calmar_mean)
    logger.info("-" * 70)
    logger.info(
        f"Phase 1 最佳: explore={best.explore_ratio:.2f}, sigma={best.sigma_ratio:.2f}"
    )
    logger.info(f"Calmar: {best.calmar_mean:.2f} ± {best.calmar_std:.2f}")

    # Phase 2: 用最佳 explore/sigma 调优 weight_decay 和 top_k_ratio
    logger.info("")
    logger.info("Phase 2: 调优 weight_decay 和 top_k_ratio")
    logger.info("-" * 70)

    results2 = []
    for wd, tk in itertools.product(weight_decays, top_k_ratios):
        result = run_with_config(
            explore_ratio=best.explore_ratio,
            sigma_ratio=best.sigma_ratio,
            weight_decay=wd,
            top_k_ratio=tk,
            n_runs=5,
        )
        results2.append(result)
        logger.info(
            f"weight_decay={wd:.2f}, top_k_ratio={tk:.2f} -> "
            f"Calmar={result.calmar_mean:.2f} ± {result.calmar_std:.2f}"
        )

    best2 = max(results2, key=lambda r: r.calmar_mean)

    # 汇总
    logger.info("=" * 70)
    logger.info("最终推荐参数:")
    logger.info(f"  explore_ratio = {best.explore_ratio:.2f}")
    logger.info(f"  sigma_ratio   = {best.sigma_ratio:.2f}")
    logger.info(f"  weight_decay  = {best2.weight_decay:.2f}")
    logger.info(f"  top_k_ratio   = {best2.top_k_ratio:.2f}")
    logger.info(f"  预期 Calmar   = {best2.calmar_mean:.2f} ± {best2.calmar_std:.2f}")
    logger.info("=" * 70)

    # 和默认参数对比
    logger.info("")
    logger.info("与默认参数对比:")
    default_result = run_with_config(
        explore_ratio=0.30,
        sigma_ratio=0.15,
        weight_decay=0.10,
        top_k_ratio=0.70,
        n_runs=5,
    )
    logger.info(
        f"默认参数 Calmar: {default_result.calmar_mean:.2f} ± {default_result.calmar_std:.2f}"
    )
    logger.info(f"优化参数 Calmar: {best2.calmar_mean:.2f} ± {best2.calmar_std:.2f}")

    improvement = (
        (best2.calmar_mean - default_result.calmar_mean)
        / default_result.calmar_mean
        * 100
    )
    logger.info(f"提升: {improvement:+.1f}%")


if __name__ == "__main__":
    import time

    start = time.perf_counter()
    run_hyperparameter_tuning()
    elapsed = time.perf_counter() - start
    logger.info(f"\n总运行时间: {elapsed:.1f} 秒")
