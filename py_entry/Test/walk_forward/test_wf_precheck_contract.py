"""WF 预检入口契约测试。"""

from __future__ import annotations
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
        train_active_bars=400,
        test_active_bars=120,
        min_warmup_bars=30,
        mode=WfWarmupMode.ExtendTest,
    )

    report = bt.validate_wf_indicator_readiness(cfg)
    assert report["base_data_key"] == "ohlcv_15m"
    assert int(report["indicator_warmup_bars_base"]) > 0
    assert int(report["test_warmup_bars_base"]) >= int(
        report["indicator_warmup_bars_base"]
    )


def test_wf_precheck_ignore_indicator_warmup_skips_contract_requirement(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """ignore_indicator_warmup=true 时，应跳过指标 warmup 约束。"""
    bt = build_single_sma_backtest(period=80)
    cfg = build_wf_cfg(
        train_active_bars=400,
        test_active_bars=120,
        min_warmup_bars=5,
        mode=WfWarmupMode.ExtendTest,
        ignore_indicator_warmup=True,
    )

    report = bt.validate_wf_indicator_readiness(cfg)
    assert int(report["indicator_warmup_bars_base"]) == 0
    assert int(report["test_warmup_bars_base"]) == 5


def test_wf_precheck_borrow_requires_e_not_exceed_train(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """BorrowFromTrain：E > T 必须报错。"""
    bt = build_single_sma_backtest(period=80)
    cfg = build_wf_cfg(
        train_active_bars=30,
        test_active_bars=120,
        min_warmup_bars=5,
        mode=WfWarmupMode.BorrowFromTrain,
    )

    with pytest.raises(ValueError, match="BorrowFromTrain"):
        bt.validate_wf_indicator_readiness(cfg)


def test_wf_precheck_borrow_large_base_warmup_must_fail_fast(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """BorrowFromTrain：base 预热过大导致 P_test > T 时必须直接报错。"""
    # 中文注释：这不是临时回归，而是当前正式 spec 的 fail-fast 契约。
    bt = build_single_sma_backtest(period=120, num_bars=1_500, seed=17)
    cfg = build_wf_cfg(
        train_active_bars=100,
        test_active_bars=120,
        min_warmup_bars=1,
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
        train_active_bars=200,
        test_active_bars=60,
        min_warmup_bars=10,
        mode=WfWarmupMode.ExtendTest,
    )
    report = bt.validate_wf_indicator_readiness(cfg)
    assert report["warmup_bars_by_source"] == {}
    assert int(report["indicator_warmup_bars_base"]) == 0
    assert int(report["test_warmup_bars_base"]) == 10


def test_wf_precheck_error_message_is_diagnosable(
    monkeypatch: pytest.MonkeyPatch,
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """预检失败信息必须包含实例/source/required/observed。"""
    bt = build_single_sma_backtest(period=48)
    cfg = build_wf_cfg(
        train_active_bars=400,
        test_active_bars=120,
        min_warmup_bars=60,
        mode=WfWarmupMode.ExtendTest,
    )

    # 中文注释：强制篡改观测值，稳定触发“required != observed”分支。
    def _fake_leading(_df, _col):
        return 0

    monkeypatch.setattr(bt, "_leading_missing_count", _fake_leading)

    with pytest.raises(ValueError) as exc:
        bt.validate_wf_indicator_readiness(cfg)
    msg = str(exc.value)
    assert "instance=" in msg
    assert "source=" in msg
    assert "required=" in msg
    assert "observed=" in msg
