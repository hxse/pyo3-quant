"""WF 预检入口契约测试。"""

from __future__ import annotations

import types
from collections.abc import Callable

import pytest

from py_entry.runner import Backtest
from py_entry.types import WalkForwardConfig, WfWarmupMode


def test_wf_precheck_success_returns_base_binding(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """成功路径：返回 base 绑定与有效过渡长度。"""
    bt = build_single_sma_backtest(period=48)
    cfg = build_wf_cfg(
        train_bars=400,
        transition_bars=30,
        test_bars=120,
        mode=WfWarmupMode.ExtendTest,
    )

    report = bt.validate_wf_indicator_readiness(cfg)
    assert report["base_data_key"] == "ohlcv_15m"
    assert int(report["indicator_warmup_bars_base"]) > 0
    assert int(report["effective_transition_bars"]) >= int(
        report["indicator_warmup_bars_base"]
    )


def test_wf_precheck_no_warmup_fails_when_transition_insufficient(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """失败路径：NoWarmup 下 transition 不足必须直接报错。"""
    bt = build_single_sma_backtest(period=80)
    cfg = build_wf_cfg(
        train_bars=400,
        transition_bars=5,
        test_bars=120,
        mode=WfWarmupMode.NoWarmup,
    )

    with pytest.raises(ValueError, match="NoWarmup"):
        bt.validate_wf_indicator_readiness(cfg)


def test_wf_precheck_borrow_requires_e_not_exceed_train(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """BorrowFromTrain：E > T 必须报错。"""
    bt = build_single_sma_backtest(period=80)
    cfg = build_wf_cfg(
        train_bars=30,
        transition_bars=5,
        test_bars=120,
        mode=WfWarmupMode.BorrowFromTrain,
    )

    with pytest.raises(ValueError, match="BorrowFromTrain"):
        bt.validate_wf_indicator_readiness(cfg)


def test_wf_precheck_borrow_large_base_warmup_regression_currently_errors(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """回归锁定：当前实现中 base 预热过大时 BorrowFromTrain 会报错。"""
    # 中文注释：该用例用于先暴露问题，修复前预期抛错，修复后应改为“可通过”。
    bt = build_single_sma_backtest(period=120, num_bars=1_500, seed=17)
    cfg = build_wf_cfg(
        train_bars=100,
        transition_bars=1,
        test_bars=120,
        mode=WfWarmupMode.BorrowFromTrain,
    )

    with pytest.raises(ValueError, match="BorrowFromTrain"):
        bt.validate_wf_indicator_readiness(cfg)


def test_wf_precheck_supports_strategy_without_indicators(
    build_no_indicator_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """无指标策略也应支持预检通过。"""
    bt = build_no_indicator_backtest()
    cfg = build_wf_cfg(
        train_bars=200,
        transition_bars=10,
        test_bars=60,
        mode=WfWarmupMode.NoWarmup,
    )
    report = bt.validate_wf_indicator_readiness(cfg)
    assert report["warmup_bars_by_source"] == {}
    assert int(report["indicator_warmup_bars_base"]) == 0
    assert int(report["effective_transition_bars"]) == 10


def test_wf_precheck_error_message_is_diagnosable(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """预检失败信息必须包含实例/source/required/observed。"""
    bt = build_single_sma_backtest(period=48)
    cfg = build_wf_cfg(
        train_bars=400,
        transition_bars=60,
        test_bars=120,
        mode=WfWarmupMode.ExtendTest,
    )

    # 中文注释：强制篡改观测值，稳定触发“required != observed”分支。
    def _fake_leading(_self, _df, _col):
        return 0

    bt._leading_missing_count = types.MethodType(_fake_leading, bt)  # type: ignore[attr-defined]

    with pytest.raises(ValueError) as exc:
        bt.validate_wf_indicator_readiness(cfg)
    msg = str(exc.value)
    assert "instance=" in msg
    assert "source=" in msg
    assert "required=" in msg
    assert "observed=" in msg
