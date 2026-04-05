"""WF ignore_indicator_warmup 契约测试。"""

from __future__ import annotations

from collections.abc import Callable

from py_entry.runner import Backtest
from py_entry.types import WalkForwardConfig, WfWarmupMode


def test_wf_ignore_indicator_warmup_only_intercepts_indicator_warmup(
    build_single_sma_backtest: Callable[..., Backtest],
    build_wf_cfg: Callable[..., WalkForwardConfig],
):
    """ignore_indicator_warmup=true 时，只截获指标预热，不改变 WF 基础几何参数。"""
    bt = build_single_sma_backtest(period=80)

    cfg_false = build_wf_cfg(
        train_active_bars=400,
        test_active_bars=120,
        min_warmup_bars=10,
        mode=WfWarmupMode.ExtendTest,
        ignore_indicator_warmup=False,
    )
    report_false = bt.validate_wf_indicator_readiness(cfg_false)
    assert int(report_false["indicator_warmup_bars_base"]) > 0
    assert int(report_false["test_warmup_bars_base"]) >= int(
        report_false["indicator_warmup_bars_base"]
    )

    cfg_true = build_wf_cfg(
        train_active_bars=400,
        test_active_bars=120,
        min_warmup_bars=10,
        mode=WfWarmupMode.ExtendTest,
        ignore_indicator_warmup=True,
    )
    report_true = bt.validate_wf_indicator_readiness(cfg_true)
    assert int(report_true["indicator_warmup_bars_base"]) == 0
    assert int(report_true["test_warmup_bars_base"]) == 10
