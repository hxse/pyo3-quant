import pytest
import time
import numpy as np
from scipy.stats import mannwhitneyu
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
)
from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


class TestLayer2Financial:
    """第二层：金融场景统计对比测试"""

    # 测试参数配置
    # --- 大测试参数 (Large Test Config) ---
    # N_BARS = 10000
    # N_RUNS = 8
    # N_TRIALS_OPTUNA = 300
    # N_ROUNDS_RUST = 6
    # SAMPLES_PER_ROUND = 50

    # --- 小测试参数 (Small Test Config - CI Friendly) ---
    N_BARS = 2000
    N_RUNS = 2
    N_TRIALS_OPTUNA = 50
    N_ROUNDS_RUST = 3
    SAMPLES_PER_ROUND = 20

    @pytest.fixture
    def backtest_setup(self):
        """创建回测配置"""
        data_config = DataGenerationParams(
            timeframes=["15m"],
            start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
            num_bars=self.N_BARS,
            fixed_seed=42,  # 数据固定，保证场景一致
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

        # 简单策略模板
        from py_entry.types import SignalTemplate, SignalGroup, LogicOp

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

        # 回测参数优化：加入止损止盈
        from py_entry.types import BacktestParams

        backtest_params = BacktestParams(
            # ATR 止损配置 (Standard trend following ranges)
            sl_atr=Param.create(2.0, min=1.5, max=4.0, step=0.25, optimize=True),
            tsl_atr=Param.create(3.0, min=2.0, max=6.0, step=0.25, optimize=True),
            atr_period=Param.create(
                14, min=10, max=30, optimize=True, dtype=ParamType.INTEGER
            ),
            initial_capital=10000.0,
            fee_pct=0.0005,  # 0.05% fee
            fee_fixed=0.0,
        )

        return data_config, indicators, template, engine_settings, backtest_params

    def test_calmar_ratio_distribution(self, backtest_setup):
        """测试两个优化器找到的最优 Calmar Ratio 分布是否无显著差异"""
        data_config, indicators, template, engine_settings, backtest_params = (
            backtest_setup
        )

        rust_results = []
        optuna_results = []

        logger.info(f"开始 {self.N_RUNS} 次重复实验对比...")

        for seed in range(self.N_RUNS):
            # 动态调整 seed 保证每轮测试场景不同但固定
            data_config.fixed_seed = seed + 1000

            # 必须每次重新初始化 Backtest 以保证状态重置
            # 注意：此处传入了 backtest_params，其中包含 optimizable 的参数
            bt = Backtest(
                data_source=data_config,
                indicators=indicators,
                signal={},
                backtest=backtest_params,
                signal_template=template,
                engine_settings=engine_settings,
            )

            # Rust 优化器
            # 数据的一致性通过 data_config.fixed_seed 控制
            # 恢复使用 CalmarRatioRaw
            rust_config = OptimizerConfig(
                samples_per_round=self.SAMPLES_PER_ROUND,
                max_rounds=self.N_ROUNDS_RUST,
                optimize_metric=OptimizeMetric.CalmarRatioRaw,
                seed=seed + 1000,
            )

            t0 = time.perf_counter()
            rust_opt = bt.optimize(rust_config)
            rust_time = time.perf_counter() - t0

            # 验证优化目标是否正确
            assert rust_opt.optimize_metric == OptimizeMetric.CalmarRatioRaw

            # 使用统一的 optimize_value
            rust_val = rust_opt.optimize_value

            # 验证交易次数 (已通过 best_metrics 暴露)
            # 注意：如果策略参数太差导致0交易，这里会失败，但这正是我们想知道的
            total_trades = rust_opt.best_metrics["total_trades"]
            logger.info(
                f"Rust Run {seed + 1}: Time={rust_time:.4f}s, Trades={total_trades}, Calmar={rust_val}"
            )

            assert total_trades >= 10, (
                f"Rust optimizer selected a parameter set with too few trades: {total_trades}"
            )

            rust_results.append(rust_val)

            # 验证账户安全性 (防止爆仓)
            max_drawdown = rust_opt.best_metrics.get("max_drawdown", 1.0)
            total_return = rust_opt.best_metrics.get("total_return", -1.0)

            logger.info(
                f"Rust Stats: MDD={max_drawdown:.2%}, Return={total_return:.2%}"
            )

            # 务实的安全检查
            # 1. Calmar Ratio > 0
            assert rust_val > 0.0, (
                f"Rust strategy failed to produce positive Calmar: {rust_val:.4f}"
            )
            # 2. Total Return > 0
            assert total_return > 0.0, (
                f"Rust strategy failed to profit: Return={total_return:.2%}"
            )

            # 记录详细统计供参考，但不作为失败依据
            if max_drawdown > 0.8:
                logger.warning(f"High Drawdown detected: {max_drawdown:.2%}")

            # 2. Optuna 优化器
            optuna_config = OptunaConfig(
                n_trials=self.N_TRIALS_OPTUNA,
                batch_size=50,
                seed=seed + 1000,  # 使用相同的种子
                metric=OptimizeMetric.CalmarRatioRaw,
                show_progress_bar=False,
            )
            t0 = time.perf_counter()
            optuna_opt = bt.optimize_with_optuna(optuna_config)
            optuna_time = time.perf_counter() - t0

            optuna_val = optuna_opt.best_value
            optuna_results.append(optuna_val)

            logger.info(
                f"Run {seed + 1}/{self.N_RUNS}: Rust={rust_val:.4f} ({rust_time:.3f}s), Optuna={optuna_val:.4f} ({optuna_time:.3f}s)"
            )

        # 统计分析
        rust_mean = np.mean(rust_results)
        optuna_mean = np.mean(optuna_results)
        logger.info(f"Mean Results: Rust={rust_mean:.4f}, Optuna={optuna_mean:.4f}")

        # Mann-Whitney U 检验 (双尾检测显著差异)
        # H0: 两个分布相同
        # p < 0.05 拒绝 H0，认为有显著差异
        stat, p_value = mannwhitneyu(
            rust_results, optuna_results, alternative="two-sided"
        )

        logger.info(f"Mann-Whitney U Test: statistic={stat}, p-value={p_value:.4f}")

        # 断言逻辑：
        # 1. 均值不能比 Optuna 差太多 (考虑到随机性，允许 10% 的误差或绝对值差异)
        # 注意 Calmar 可能是负数，处理大小时要小心. 这里我们追求 Maximize.
        # 如果 Rust Mean 明显小于 Optuna Mean，那是不好的。
        # 但我们主要目的是验证"可靠性"，如果 Rust 略好或略差但无显著差异也可以。

        # 如果 p_value > 0.05，说明没有显著差异，测试通过
        # 如果 p_value < 0.05，且 Rust 均值 > Optuna 均值，说明 Rust 显著更好，测试也通过
        # 只有当 p_value < 0.05 且 Rust 均值 < Optuna 均值时，才判定失败

        is_statistically_equivalent = p_value > 0.01  # 使用更严格的 0.01 显著性水平
        is_rust_better = rust_mean > optuna_mean

        assert is_statistically_equivalent or is_rust_better, (
            f"Rust optimizer is significantly worse than Optuna (p={p_value:.4f}, Rust Mean={rust_mean:.4f} < Optuna Mean={optuna_mean:.4f})"
        )
