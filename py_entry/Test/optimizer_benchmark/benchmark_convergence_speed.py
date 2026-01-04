"""收敛速度对比测试：Rust Optimizer vs Optuna"""

import time
from loguru import logger

from py_entry.runner import Backtest
from py_entry.types import (
    OptunaConfig,
    OptimizerConfig,
    OptimizeMetric,
    ParamType,
    Param,
    SettingContainer,
    ExecutionStage,
    BacktestParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
)
from py_entry.data_generator import DataGenerationParams


def create_backtest():
    """创建标准测试回测配置"""
    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=6000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    indicators = {
        "ohlcv_15m": {
            "sma_fast": {
                "period": Param.create(
                    20, min=10, max=40, optimize=True, dtype=ParamType.INTEGER
                )
            },
            "sma_slow": {
                "period": Param.create(
                    60, min=40, max=100, optimize=True, dtype=ParamType.INTEGER
                )
            },
        }
    }

    template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_fast,ohlcv_15m,0 x> sma_slow,ohlcv_15m,0"],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["sma_fast,ohlcv_15m,0 x< sma_slow,ohlcv_15m,0"],
        ),
    )

    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE, return_only_final=True
    )

    backtest_params = BacktestParams(
        sl_atr=Param.create(2.0, min=1.5, max=4.0, step=0.25, optimize=True),
        tsl_atr=Param.create(3.0, min=2.0, max=6.0, step=0.25, optimize=True),
        atr_period=Param.create(
            14, min=10, max=30, optimize=True, dtype=ParamType.INTEGER
        ),
        initial_capital=10000.0,
        fee_pct=0.0005,
        fee_fixed=0.0,
    )

    return Backtest(
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
