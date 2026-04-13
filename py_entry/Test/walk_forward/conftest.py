"""Walk-Forward 测试共享构建器。"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl
import pytest

from py_entry.Test.shared.constants import TEST_START_TIME_MS
from py_entry.data_generator import DataGenerationParams
from py_entry.runner import Backtest
from py_entry.types import (
    ArtifactRetention,
    BacktestParams,
    ExecutionStage,
    LogicOp,
    OptimizeMetric,
    OptimizerConfig,
    Param,
    ParamType,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
    WalkForwardConfig,
    WfWarmupMode,
)


@pytest.fixture(scope="session")
def wf_base_key() -> str:
    """统一的 WF 基准 source key。"""
    return "ohlcv_15m"


@pytest.fixture(scope="session")
def build_wf_cfg() -> Callable[..., WalkForwardConfig]:
    """构建 WF 配置（含可调优化轮次）。"""

    def _build(
        *,
        train_active_bars: int,
        test_active_bars: int,
        min_warmup_bars: int = 0,
        mode: WfWarmupMode | None = None,
        ignore_indicator_warmup: bool = False,
        optimizer_rounds: int = 8,
        optimizer_seed: int = 42,
    ) -> WalkForwardConfig:
        # 中文注释：统一让 min/max/samples_per_round 同步，避免测试配置漂移。
        optimizer_cfg = OptimizerConfig(
            min_samples=optimizer_rounds,
            max_samples=optimizer_rounds,
            samples_per_round=optimizer_rounds,
            stop_patience=2,
            optimize_metric=OptimizeMetric.CalmarRatioRaw,
            seed=optimizer_seed,
        )
        if mode is None:
            return WalkForwardConfig(
                train_active_bars=train_active_bars,
                test_active_bars=test_active_bars,
                min_warmup_bars=min_warmup_bars,
                ignore_indicator_warmup=ignore_indicator_warmup,
                optimizer_config=optimizer_cfg,
            )
        return WalkForwardConfig(
            train_active_bars=train_active_bars,
            test_active_bars=test_active_bars,
            min_warmup_bars=min_warmup_bars,
            warmup_mode=mode,
            ignore_indicator_warmup=ignore_indicator_warmup,
            optimizer_config=optimizer_cfg,
        )

    return _build


@pytest.fixture(scope="session")
def build_sma_cross_backtest(
    wf_base_key: str,
) -> Callable[..., Backtest]:
    """构建 SMA 交叉策略 Backtest。"""

    def _build(
        *,
        num_bars: int,
        fast_period: int = 12,
        slow_period: int = 48,
        optimize: bool = True,
        no_trade: bool = False,
        with_backtest_params: bool = False,
        seed: int = 42,
    ) -> Backtest:
        data_cfg = DataGenerationParams(
            timeframes=["15m"],
            start_time=TEST_START_TIME_MS,
            num_bars=num_bars,
            base_data_key=wf_base_key,
            fixed_seed=seed,
            allow_gaps=False,
        )

        indicators = {
            wf_base_key: {
                "sma_fast": {
                    "period": Param(
                        fast_period,
                        min=max(1, fast_period),
                        max=max(1, fast_period),
                        step=1.0,
                        optimize=optimize,
                        dtype=ParamType.Integer,
                    )
                },
                "sma_slow": {
                    "period": Param(
                        slow_period,
                        min=max(1, slow_period),
                        max=max(1, slow_period),
                        step=1.0,
                        optimize=optimize,
                        dtype=ParamType.Integer,
                    )
                },
            }
        }

        if no_trade:
            # 中文注释：构造恒不触发条件，确保整个流程无交易。
            template = SignalTemplate(
                entry_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"close, {wf_base_key}, 0 > 1000000000"],
                ),
                entry_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[f"close, {wf_base_key}, 0 < -1000000000"],
                ),
                exit_long=None,
                exit_short=None,
            )
        else:
            template = SignalTemplate(
                entry_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast, {wf_base_key}, 0 x> sma_slow, {wf_base_key}, 0"
                    ],
                ),
                entry_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast, {wf_base_key}, 0 x< sma_slow, {wf_base_key}, 0"
                    ],
                ),
                exit_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast, {wf_base_key}, 0 x< sma_slow, {wf_base_key}, 0"
                    ],
                ),
                exit_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        f"sma_fast, {wf_base_key}, 0 x> sma_slow, {wf_base_key}, 0"
                    ],
                ),
            )

        settings = SettingContainer(
            stop_stage=ExecutionStage.Performance,
            artifact_retention=ArtifactRetention.AllCompletedStages,
        )

        backtest_params = None
        if with_backtest_params:
            backtest_params = BacktestParams(
                initial_capital=10_000.0,
                fee_fixed=0.0,
                fee_pct=0.001,
                sl_exit_in_bar=False,
                tp_exit_in_bar=False,
                sl_trigger_mode=False,
                tp_trigger_mode=False,
                tsl_trigger_mode=False,
                sl_anchor_mode=False,
                tp_anchor_mode=False,
                tsl_anchor_mode=False,
            )

        return Backtest(
            enable_timing=False,
            data_source=data_cfg,
            indicators=indicators,
            signal={},
            backtest=backtest_params,
            signal_template=template,
            engine_settings=settings,
        )

    return _build


@pytest.fixture(scope="session")
def build_single_sma_backtest(wf_base_key: str) -> Callable[..., Backtest]:
    """构建单 SMA 指标的最小预检 Backtest。"""

    def _build(*, period: int = 48, num_bars: int = 1200, seed: int = 7) -> Backtest:
        data_cfg = DataGenerationParams(
            timeframes=["15m"],
            start_time=TEST_START_TIME_MS,
            num_bars=num_bars,
            base_data_key=wf_base_key,
            fixed_seed=seed,
            allow_gaps=False,
        )

        indicators = {
            wf_base_key: {
                "sma_fast": {
                    "period": Param(
                        period,
                        min=12,
                        max=120,
                        step=1.0,
                        optimize=True,
                        dtype=ParamType.Integer,
                    )
                }
            }
        }

        settings = SettingContainer(
            stop_stage=ExecutionStage.Performance,
            artifact_retention=ArtifactRetention.AllCompletedStages,
        )
        return Backtest(
            enable_timing=False,
            data_source=data_cfg,
            indicators=indicators,
            signal={},
            engine_settings=settings,
        )

    return _build


@pytest.fixture(scope="session")
def build_no_indicator_backtest(wf_base_key: str) -> Callable[..., Backtest]:
    """构建无指标策略 Backtest。"""

    def _build(*, num_bars: int = 600, seed: int = 9) -> Backtest:
        data_cfg = DataGenerationParams(
            timeframes=["15m"],
            start_time=TEST_START_TIME_MS,
            num_bars=num_bars,
            base_data_key=wf_base_key,
            fixed_seed=seed,
            allow_gaps=False,
        )
        settings = SettingContainer(
            stop_stage=ExecutionStage.Performance,
            artifact_retention=ArtifactRetention.AllCompletedStages,
        )
        return Backtest(
            enable_timing=False,
            data_source=data_cfg,
            indicators={},
            signal={},
            engine_settings=settings,
        )

    return _build


@pytest.fixture(scope="session")
def missing_expr() -> Callable[[str], pl.Expr]:
    """统一缺失表达式（null 或 NaN）。"""

    def _build(col_name: str) -> pl.Expr:
        col = pl.col(col_name).cast(pl.Float64, strict=False)
        return col.is_null() | col.is_nan()

    return _build
