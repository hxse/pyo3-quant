"""test_strategies 统一加载入口。"""

from __future__ import annotations

from typing import cast

from py_entry.strategy_hub.core.spec import TestStrategySpec
from py_entry.strategy_hub.core.spec_loader import discover_modules, load_spec


def get_test_strategy_names() -> list[str]:
    """返回 test 策略名列表。"""

    return sorted(discover_modules("test"))


def get_test_strategy(name: str) -> TestStrategySpec:
    """按名称加载 test 策略 Spec。"""

    module_names = discover_modules("test")
    if name not in module_names:
        raise KeyError(f"策略 '{name}' 未找到。可选: {sorted(module_names)}")
    # 中文注释：类型校验已在 load_spec(source="test") 内做强约束，这里仅做静态类型收窄。
    return cast(TestStrategySpec, load_spec(name, "test"))


def get_all_strategies() -> list[TestStrategySpec]:
    """返回全部测试策略 Spec。"""

    seen: set[str] = set()
    out: list[TestStrategySpec] = []
    for strategy_name in get_test_strategy_names():
        spec = get_test_strategy(strategy_name)
        if spec.name in seen:
            raise ValueError(f"test strategy name 重复: {spec.name}")
        seen.add(spec.name)
        out.append(spec)
    return out


__all__ = [
    "get_all_strategies",
    "get_test_strategy",
    "get_test_strategy_names",
]
