"""WF 注入与窗口边界契约测试。"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl
import pytest

from py_entry.runner import Backtest
from py_entry.types import (
    OptimizeMetric,
    OptimizerConfig,
    WalkForwardConfig,
    WfWarmupMode,
)


def _window_has_open_position(window, missing_expr: Callable[[str], pl.Expr]) -> bool:
    """读取窗口 Test 末根是否存在未平持仓。"""
    backtest_df = window.summary.backtest_result
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


@pytest.fixture(scope="module")
def wf_borrow_from_train(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """复用 BorrowFromTrain 结果，避免重复执行 WF。"""
    bt = build_sma_cross_backtest(num_bars=900)
    cfg = build_wf_cfg(
        train_bars=300,
        transition_bars=30,
        test_bars=120,
        mode=WfWarmupMode.BorrowFromTrain,
        optimizer_rounds=8,
    )
    bt.validate_wf_indicator_readiness(cfg)
    return bt.walk_forward(cfg)


@pytest.fixture(scope="module")
def wf_extend_test(
    build_sma_cross_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """复用 ExtendTest 结果，避免重复执行 WF。"""
    bt = build_sma_cross_backtest(num_bars=900)
    cfg = build_wf_cfg(
        train_bars=300,
        transition_bars=30,
        test_bars=120,
        mode=WfWarmupMode.ExtendTest,
        optimizer_rounds=8,
    )
    bt.validate_wf_indicator_readiness(cfg)
    return bt.walk_forward(cfg)


def test_wf_windows_formula_borrow_from_train(wf_borrow_from_train):
    """BorrowFromTrain：transition 必须与 train 尾部重叠。"""
    wf = wf_borrow_from_train

    assert len(wf.window_results) > 0
    for w in wf.window_results:
        _train_start, train_end = w.train_range
        transition_start, transition_end = w.transition_range
        test_start, _test_end = w.test_range
        e = transition_end - transition_start
        assert transition_end == train_end
        assert transition_start == train_end - e
        assert test_start == train_end

    # 中文注释：第一窗没有上一窗，不应出现跨窗继承开仓。
    assert wf.window_results[0].has_cross_boundary_position is False


def test_wf_windows_formula_extend_test(wf_extend_test):
    """ExtendTest：transition 紧跟 train，test 紧跟 transition。"""
    wf = wf_extend_test

    assert len(wf.window_results) > 0
    for w in wf.window_results:
        _train_start, train_end = w.train_range
        transition_start, transition_end = w.transition_range
        test_start, _test_end = w.test_range
        assert transition_start == train_end
        assert test_start == transition_end


def test_wf_e_eq_1_boundary_supported(
    build_sma_cross_backtest: Callable[..., Backtest],
):
    """边界：E==1 在新注入口径下必须合法。"""
    # 中文注释：该用例只验证 E==1 合法性，不需要大数据和高优化轮次。
    bt = build_sma_cross_backtest(
        fast_period=1,
        slow_period=2,
        optimize=True,
        num_bars=360,
    )
    cfg = WalkForwardConfig(
        train_bars=120,
        transition_bars=1,
        test_bars=20,
        wf_warmup_mode=WfWarmupMode.NoWarmup,
        optimizer_config=OptimizerConfig(
            min_samples=2,
            max_samples=4,
            samples_per_round=2,
            stop_patience=1,
            optimize_metric=OptimizeMetric.CalmarRatioRaw,
            seed=7,
        ),
    )
    bt.validate_wf_indicator_readiness(cfg)
    wf = bt.walk_forward(cfg)
    assert len(wf.window_results) > 0


def test_wf_borrow_from_train_rejects_e_gt_t(
    build_sma_cross_backtest: Callable[..., Backtest],
):
    """BorrowFromTrain：E > T 直接报错。"""
    bt = build_sma_cross_backtest(num_bars=900)
    cfg = WalkForwardConfig(
        train_bars=10,
        transition_bars=1,
        test_bars=120,
        wf_warmup_mode=WfWarmupMode.BorrowFromTrain,
    )
    with pytest.raises(Exception):
        bt.walk_forward(cfg)


def test_wf_cross_window_state_chain_consistency_over_four_windows(
    wf_extend_test,
    missing_expr: Callable[[str], pl.Expr],
):
    """跨窗状态链一致性：当前窗注入标记必须等于上一窗 Test 末根持仓状态。"""
    wf = wf_extend_test

    assert len(wf.window_results) >= 4

    # 中文注释：首窗没有上一窗，必须不标记跨窗继承。
    assert wf.window_results[0].has_cross_boundary_position is False

    for i in range(1, len(wf.window_results)):
        prev_open = _window_has_open_position(wf.window_results[i - 1], missing_expr)
        curr_flag = bool(wf.window_results[i].has_cross_boundary_position)
        assert curr_flag == prev_open, (
            f"跨窗状态链不一致: window={i}, expected={prev_open}, actual={curr_flag}"
        )
