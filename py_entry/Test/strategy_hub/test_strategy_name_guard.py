"""strategy_name_guard 行为测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from py_entry.strategy_hub.core import strategy_name_guard


def test_validate_global_strategy_name_uniqueness_should_discover_once_per_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """全量校验应仅发现一次模块列表，并复用该列表加载 spec。"""

    discover_calls: dict[str, int] = {"search": 0, "test": 0}

    def fake_discover_modules(source: str) -> list[str]:
        discover_calls[source] += 1
        return ["search_mod"] if source == "search" else ["test_mod"]

    def fake_load_spec_resolved(module_name: str, source: str) -> SimpleNamespace:
        return SimpleNamespace(name=f"{source}:{module_name}")

    monkeypatch.setattr(
        strategy_name_guard,
        "discover_modules",
        fake_discover_modules,
    )
    monkeypatch.setattr(
        strategy_name_guard,
        "load_spec_resolved",
        fake_load_spec_resolved,
    )

    strategy_name_guard.validate_global_strategy_name_uniqueness()
    assert discover_calls == {"search": 1, "test": 1}


def test_validate_global_strategy_name_uniqueness_should_raise_on_name_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同名策略跨模块冲突时必须报错。"""

    def fake_discover_modules(source: str) -> list[str]:
        return ["mod_a"] if source == "search" else ["mod_b"]

    def fake_load_spec_resolved(module_name: str, source: str) -> SimpleNamespace:
        return SimpleNamespace(name="dup_name")

    monkeypatch.setattr(
        strategy_name_guard,
        "discover_modules",
        fake_discover_modules,
    )
    monkeypatch.setattr(
        strategy_name_guard,
        "load_spec_resolved",
        fake_load_spec_resolved,
    )

    with pytest.raises(ValueError, match="策略名冲突，必须全局唯一"):
        strategy_name_guard.validate_global_strategy_name_uniqueness()
