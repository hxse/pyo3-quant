"""strategy_hub 工作流预检入口测试。"""

from __future__ import annotations

from types import SimpleNamespace

from py_entry.strategy_hub.core import strategy_searcher
from py_entry.strategy_hub.core import searcher_runtime
from py_entry.strategy_hub.core.spec_loader import load_spec


class _DummyBacktest:
    """用于入口调用断言的最小桩对象。"""

    def __init__(self) -> None:
        self.precheck_calls = 0
        self.walk_forward_calls = 0

    def validate_wf_indicator_readiness(self, wf_cfg):
        """记录预检调用次数并返回最小报告。"""
        self.precheck_calls += 1
        return {
            "base_data_key": "ohlcv_15m",
            "indicator_warmup_bars_base": 10,
            "effective_transition_bars": 10,
        }

    def run(self):
        return SimpleNamespace(
            summary=SimpleNamespace(performance={"total_return": 0.1})
        )

    def optimize(self, _):
        return SimpleNamespace()

    def sensitivity(self, _):
        return SimpleNamespace()

    def walk_forward(self, _):
        self.walk_forward_calls += 1
        return SimpleNamespace(
            aggregate_test_metrics={},
            best_window_id=0,
            worst_window_id=0,
            raw=SimpleNamespace(window_results=[]),
        )


def _patch_searcher_runtime(monkeypatch, bt: _DummyBacktest) -> None:
    """注入统一 runtime 桩，避免重复 monkeypatch。"""

    spec = load_spec("sma_2tf", "search")
    monkeypatch.setattr(
        searcher_runtime,
        "build_strategy_runtime",
        lambda _strategy_ref, run_symbol=None: (
            spec,
            {
                "wf_cfg": SimpleNamespace(),
                "opt_cfg": SimpleNamespace(),
                "sens_cfg": SimpleNamespace(),
            },
            bt,
        ),
    )
    monkeypatch.setattr(
        searcher_runtime,
        "extract_backtest_time_info",
        lambda _run_result: {
            "backtest_start_time_ms": 1,
            "backtest_end_time_ms": 2,
            "backtest_span_ms": 1,
        },
    )
    monkeypatch.setattr(
        searcher_runtime,
        "extract_optimize_info",
        lambda _opt_result: {"performance": {"calmar_ratio_raw": 1.0}},
    )
    monkeypatch.setattr(
        searcher_runtime,
        "extract_sensitivity_info",
        lambda _sens_result: {"performance": {"mean": 0.1, "std": 0.2, "cv": 2.0}},
    )


def test_searcher_walk_forward_calls_precheck_once(monkeypatch):
    """searcher 的 walk_forward 分支必须显式预检一次。"""
    bt = _DummyBacktest()

    _patch_searcher_runtime(monkeypatch, bt)

    result = strategy_searcher._run_once(
        module_name="sma_2tf.sma_2tf",
        symbol_override="SOL/USDT",
        run_mode="walk_forward",
    )
    assert result["mode"] == "walk_forward"
    assert bt.precheck_calls == 1
    assert bt.walk_forward_calls == 1


def test_searcher_non_walk_forward_should_not_call_precheck(monkeypatch):
    """其余 3 个 mode 不应触发 WF 预检。"""

    bt = _DummyBacktest()
    _patch_searcher_runtime(monkeypatch, bt)

    for mode in ("backtest", "optimize", "sensitivity"):
        result = strategy_searcher._run_once(
            module_name="sma_2tf.sma_2tf",
            symbol_override="SOL/USDT",
            run_mode=mode,
        )
        assert result["mode"] == mode

    assert bt.precheck_calls == 0
    assert bt.walk_forward_calls == 0
