"""private 工作流预检入口测试。"""

from __future__ import annotations

from types import SimpleNamespace

from py_entry.private_strategies import strategy_searcher, template


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
        return "run"

    def optimize(self, _):
        return "opt"

    def sensitivity(self, _):
        return "sens"

    def walk_forward(self, _):
        self.walk_forward_calls += 1
        return SimpleNamespace(
            aggregate_test_metrics={},
            best_window_id=0,
            worst_window_id=0,
            raw=SimpleNamespace(window_results=[]),
        )


def test_template_pipeline_calls_precheck_once(monkeypatch):
    """pipeline 入口必须显式预检一次。"""
    bt = _DummyBacktest()

    def _fake_build_runtime(_module_name: str):
        return {
            "cfg": SimpleNamespace(
                data_config=SimpleNamespace(base_data_key="ohlcv_15m")
            ),
            "bt": bt,
            "opt_cfg": SimpleNamespace(),
            "sens_cfg": SimpleNamespace(),
            "wf_cfg": SimpleNamespace(),
        }

    captured: dict[str, object] = {}

    def _fake_runner_run_pipeline(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(template, "_build_runtime", _fake_build_runtime)
    monkeypatch.setattr(template, "runner_run_pipeline", _fake_runner_run_pipeline)

    out = template.run_pipeline("dummy")
    assert out == {"ok": True}
    assert bt.precheck_calls == 1
    assert "wf_precheck" in captured


def test_template_run_stage_does_not_auto_precheck(monkeypatch):
    """run_stage 不自动预检（由用户显式调用）。"""
    bt = _DummyBacktest()

    def _fake_build_runtime(_module_name: str):
        return {
            "bt": bt,
            "opt_cfg": SimpleNamespace(),
            "sens_cfg": SimpleNamespace(),
            "wf_cfg": SimpleNamespace(),
        }

    monkeypatch.setattr(template, "_build_runtime", _fake_build_runtime)

    template.run_stage("dummy", "walk_forward")
    assert bt.precheck_calls == 0
    assert bt.walk_forward_calls == 1


def test_searcher_walk_forward_calls_precheck_once(monkeypatch):
    """searcher 的 walk_forward 分支必须显式预检一次。"""
    bt = _DummyBacktest()

    class _BacktestFactory:
        """替换 strategy_searcher.Backtest。"""

        def __new__(cls, **_kwargs):
            return bt

    monkeypatch.setattr(strategy_searcher, "Backtest", _BacktestFactory)

    space = {
        "space_name": "demo",
        "symbol": "SOL/USDT",
        "timeframes": ["15m"],
        "since": "2024-01-01 00:00:00",
        "limit": 1000,
        "base_data_key": "ohlcv_15m",
        "backtest": SimpleNamespace(),
        "wf": SimpleNamespace(),
    }
    variant = {
        "name": "v1",
        "indicators": {},
        "template": SimpleNamespace(),
    }

    result = strategy_searcher._run_single_variant(
        space=space,
        variant=variant,
        symbol_override=None,
        run_mode="walk_forward",
    )
    assert result["mode"] == "walk_forward"
    assert bt.precheck_calls == 1
    assert bt.walk_forward_calls == 1
