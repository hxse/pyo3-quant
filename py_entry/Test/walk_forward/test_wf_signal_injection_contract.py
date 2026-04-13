"""WF 注入与窗口边界契约测试。"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl
import pytest

from py_entry.Test.shared.constants import TEST_START_TIME_MS
from py_entry.data_generator import DataGenerationParams
from py_entry.runner import Backtest
from py_entry.types import (
    ArtifactRetention,
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


def _window_has_open_position(window, missing_expr: Callable[[str], pl.Expr]) -> bool:
    """读取窗口 Test 末根是否存在未平持仓。"""
    backtest_df = window.test_pack_result.backtest_result
    assert backtest_df is not None and backtest_df.height > 0
    # 中文注释：只取末根一行，用向量表达式判定多空是否仍有未平仓位。
    last_row = backtest_df.slice(backtest_df.height - 1, 1)
    row = last_row.select(
        ((~missing_expr("entry_long_price")) & missing_expr("exit_long_price")).alias(
            "__long_open"
        ),
        ((~missing_expr("entry_short_price")) & missing_expr("exit_short_price")).alias(
            "__short_open"
        ),
    )
    long_open = bool(row["__long_open"][0])
    short_open = bool(row["__short_open"][0])
    return long_open or short_open


def _build_persistent_long_backtest() -> Backtest:
    """构造“自然末根持仓、正式结果尾部强平”的最小 WF 场景。"""
    data_cfg = DataGenerationParams(
        timeframes=["15m"],
        start_time=TEST_START_TIME_MS,
        num_bars=720,
        base_data_key="ohlcv_15m",
        fixed_seed=17,
        allow_gaps=False,
    )

    template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=["close, ohlcv_15m, 0 > $always_below"],
        ),
        entry_short=None,
        exit_long=None,
        exit_short=None,
    )

    settings = SettingContainer(
        stop_stage=ExecutionStage.Performance,
        artifact_retention=ArtifactRetention.AllCompletedStages,
    )
    return Backtest(
        enable_timing=False,
        data_source=data_cfg,
        indicators={},
        signal={
            "always_below": Param(
                -1.0,
                min=-1.0,
                max=-1.0,
                step=1.0,
                optimize=True,
                dtype=ParamType.Float,
            )
        },
        signal_template=template,
        engine_settings=settings,
    )


@pytest.fixture(scope="module")
def wf_borrow_from_train(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """复用 BorrowFromTrain 结果，避免重复执行 WF。"""
    bt = build_sma_cross_backtest(num_bars=900)
    cfg = build_wf_cfg(
        train_active_bars=300,
        test_active_bars=120,
        min_warmup_bars=30,
        mode=WfWarmupMode.BorrowFromTrain,
        optimizer_rounds=8,
    )
    return bt.walk_forward(cfg)


@pytest.fixture(scope="module")
def wf_extend_test(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """复用 ExtendTest 结果，避免重复执行 WF。"""
    bt = build_sma_cross_backtest(num_bars=900)
    cfg = build_wf_cfg(
        train_active_bars=300,
        test_active_bars=120,
        min_warmup_bars=30,
        mode=WfWarmupMode.ExtendTest,
        optimizer_rounds=8,
    )
    return bt.walk_forward(cfg)


def test_wf_windows_formula_borrow_from_train(wf_borrow_from_train):
    """BorrowFromTrain：test warmup 必须贴住训练 pack 尾部。"""
    wf = wf_borrow_from_train

    assert len(wf.window_results) > 0
    for w in wf.window_results:
        assert w.meta.test_warmup_time_range[1] == w.meta.train_pack_time_range[1]
        assert w.meta.test_active_time_range[0] >= w.meta.test_warmup_time_range[1]


def test_wf_windows_formula_extend_test(wf_extend_test):
    """ExtendTest：test warmup 必须严格落在训练 pack 之后。"""
    wf = wf_extend_test

    assert len(wf.window_results) > 0
    for w in wf.window_results:
        assert w.meta.test_warmup_time_range[0] > w.meta.train_pack_time_range[1]


def test_wf_e_eq_1_boundary_supported(
    build_sma_cross_backtest: Callable[..., Backtest],
):
    """边界：ignore_indicator_warmup=true 时，E==1 在新注入口径下必须合法。"""
    # 中文注释：该用例只验证 E==1 合法性，不需要大数据和高优化轮次。
    bt = build_sma_cross_backtest(
        fast_period=1,
        slow_period=2,
        optimize=True,
        num_bars=360,
    )
    cfg = WalkForwardConfig(
        train_active_bars=120,
        test_active_bars=20,
        min_warmup_bars=1,
        warmup_mode=WfWarmupMode.ExtendTest,
        ignore_indicator_warmup=True,
        optimizer_config=OptimizerConfig(
            min_samples=2,
            max_samples=4,
            samples_per_round=2,
            stop_patience=1,
            optimize_metric=OptimizeMetric.CalmarRatioRaw,
            seed=7,
        ),
    )
    wf = bt.walk_forward(cfg)
    assert len(wf.window_results) > 0


def test_wf_borrow_from_train_rejects_e_gt_t(
    build_sma_cross_backtest: Callable[..., Backtest],
):
    """BorrowFromTrain：E > T 直接报错。"""
    bt = build_sma_cross_backtest(num_bars=900)
    cfg = WalkForwardConfig(
        train_active_bars=10,
        test_active_bars=120,
        min_warmup_bars=1,
        warmup_mode=WfWarmupMode.BorrowFromTrain,
    )
    with pytest.raises(Exception):
        bt.walk_forward(cfg)


def test_wf_cross_window_state_comes_from_natural_replay_not_final_result(
    missing_expr: Callable[[str], pl.Expr],
):
    """上一窗自然末根仍持仓时，即使正式结果已强平，下一窗仍必须标记跨窗继承。"""
    bt = _build_persistent_long_backtest()
    cfg = WalkForwardConfig(
        train_active_bars=180,
        test_active_bars=120,
        min_warmup_bars=20,
        warmup_mode=WfWarmupMode.ExtendTest,
        ignore_indicator_warmup=True,
        optimizer_config=OptimizerConfig(
            min_samples=2,
            max_samples=2,
            samples_per_round=2,
            stop_patience=1,
            optimize_metric=OptimizeMetric.CalmarRatioRaw,
            seed=19,
        ),
    )
    wf = bt.walk_forward(cfg)

    assert len(wf.window_results) >= 2

    prev_window = wf.window_results[0]
    prev_open_from_public_final = _window_has_open_position(prev_window, missing_expr)
    assert prev_open_from_public_final is False, "正式窗口结果应在尾部强平后落为平仓"

    next_window = wf.window_results[1]
    assert next_window.meta.has_cross_boundary_position is True, (
        "下一窗 carry 标记必须读取上一窗自然回放末根状态，而不是正式强平后的公开结果"
    )
