"""收敛速度对比测试：Rust Optimizer vs Optuna"""

import time
from loguru import logger

from py_entry.types import (
    OptunaConfig,
    OptimizerConfig,
    OptimizeMetric,
    ExecutionStage,
)
from py_entry.Test.shared import (
    make_backtest_runner,
    make_data_generation_params,
    make_engine_settings,
    make_optimizer_sma_atr_components,
)


def create_backtest():
    """创建标准测试回测配置"""
    data_config = make_data_generation_params(
        timeframes=["15m"],
        num_bars=6000,
        fixed_seed=42,
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


def run_convergence_test():
    """运行收敛速度对比"""

    # 测试不同采样数量下的性能
    sample_counts = [50, 100, 150, 200, 250, 300]

    logger.info("=" * 60)
    logger.info("收敛速度对比测试: Rust Optimizer vs Optuna")
    logger.info("=" * 60)

    results = []

    for total_samples in sample_counts:
        bt = create_backtest()

        # Rust: 分 6 轮，每轮 samples / 6
        samples_per_round = max(10, total_samples // 6)
        rust_config = OptimizerConfig(
            samples_per_round=samples_per_round,
            max_rounds=6,
            optimize_metric=OptimizeMetric.CalmarRatioRaw,
        )

        rust_start = time.perf_counter()
        rust_opt = bt.optimize(rust_config)
        rust_time = time.perf_counter() - rust_start
        rust_val = rust_opt.optimize_value

        # Optuna: 相同总采样数
        optuna_config = OptunaConfig(
            n_trials=total_samples,
            batch_size=50,
            seed=42,
            metric=OptimizeMetric.CalmarRatioRaw,
            show_progress_bar=False,
        )

        optuna_start = time.perf_counter()
        optuna_opt = bt.optimize_with_optuna(optuna_config)
        optuna_time = time.perf_counter() - optuna_start
        optuna_val = optuna_opt.best_value

        results.append(
            {
                "samples": total_samples,
                "rust_val": rust_val,
                "rust_time": rust_time,
                "optuna_val": optuna_val,
                "optuna_time": optuna_time,
            }
        )

        logger.info(
            f"Samples={total_samples:3d} | Rust: {rust_val:8.2f} ({rust_time:.2f}s) | Optuna: {optuna_val:8.2f} ({optuna_time:.2f}s)"
        )

    # 汇总
    logger.info("=" * 60)
    logger.info("汇总:")
    logger.info("-" * 60)
    logger.info(
        f"{'Samples':<10} {'Rust Calmar':<15} {'Optuna Calmar':<15} {'Rust Win?':<10}"
    )
    logger.info("-" * 60)

    rust_wins = 0
    for r in results:
        win = "✓" if r["rust_val"] >= r["optuna_val"] else ""
        if r["rust_val"] >= r["optuna_val"]:
            rust_wins += 1
        logger.info(
            f"{r['samples']:<10} {r['rust_val']:<15.2f} {r['optuna_val']:<15.2f} {win:<10}"
        )

    logger.info("-" * 60)
    logger.info(
        f"Rust 胜率: {rust_wins}/{len(results)} ({100 * rust_wins / len(results):.0f}%)"
    )

    # 时间对比
    total_rust_time = sum(r["rust_time"] for r in results)
    total_optuna_time = sum(r["optuna_time"] for r in results)
    logger.info(f"总耗时: Rust={total_rust_time:.2f}s, Optuna={total_optuna_time:.2f}s")
    logger.info(f"速度提升: {total_optuna_time / total_rust_time:.1f}x")


if __name__ == "__main__":
    run_convergence_test()
