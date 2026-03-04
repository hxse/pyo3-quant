"""策略名唯一性检查。"""

from __future__ import annotations

from collections import defaultdict

from py_entry.strategy_hub.core.spec_loader import discover_modules, load_spec_resolved


def validate_global_strategy_name_uniqueness() -> None:
    """校验 test/search 两域策略名全局唯一。"""

    search_modules = discover_modules("search")
    test_modules = discover_modules("test")
    owners: dict[str, list[str]] = defaultdict(list)

    for source, modules in (("search", search_modules), ("test", test_modules)):
        for module_name in modules:
            try:
                # 中文注释：discover 后复用已解析模块名，避免单次校验内重复模块发现。
                spec = load_spec_resolved(module_name, source)
            except Exception as exc:
                raise ValueError(
                    f"加载策略失败: {source}:{module_name} ({exc})"
                ) from exc
            owners[spec.name].append(f"{source}:{module_name}")

    conflicts = {k: v for k, v in owners.items() if len(v) > 1}
    if conflicts:
        lines = ["策略名冲突，必须全局唯一："]
        for name, paths in sorted(conflicts.items(), key=lambda x: x[0]):
            lines.append(f"- {name}: {paths}")
        raise ValueError("\n".join(lines))


__all__ = ["validate_global_strategy_name_uniqueness"]
