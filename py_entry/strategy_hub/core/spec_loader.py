"""统一策略协议加载器。"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType
from typing import Literal

from py_entry.strategy_hub.core.spec import (
    CommonStrategySpec,
    SearchSpaceSpec,
    TestStrategySpec,
    ensure_valid_spec,
)

SourceType = Literal["search", "test"]

_SEARCH_PACKAGE = "py_entry.strategy_hub.search_spaces"
_TEST_PACKAGE = "py_entry.strategy_hub.test_strategies"
_SEARCH_DIR = Path(__file__).resolve().parent.parent / "search_spaces"
_TEST_DIR = Path(__file__).resolve().parent.parent / "test_strategies"


def _iter_modules(
    base_dir: Path, *, include_subdirs: bool, source: SourceType
) -> list[str]:
    """扫描策略模块。"""

    names: list[str] = []
    for py_file in sorted(base_dir.glob("*.py"), key=lambda p: p.name):
        stem = py_file.stem
        if stem.startswith("_") or stem in {"__init__", "common"}:
            continue
        names.append(stem)

    if include_subdirs:
        for child in sorted(base_dir.iterdir(), key=lambda p: p.name):
            if not child.is_dir():
                continue
            if child.name.startswith((".", "_")) or child.name in {
                "__pycache__",
                "trash",
                "logs",
                "log",
            }:
                continue
            if source == "test":
                # 中文注释：test 目录策略统一按“目录名即模块名”暴露，不扫描目录内部文件。
                if (child / "__init__.py").exists():
                    names.append(child.name)
                continue
            for py_file in sorted(child.glob("*.py"), key=lambda p: p.name):
                stem = py_file.stem
                if stem.startswith("_") or stem in {"__init__", "common"}:
                    continue
                names.append(f"{child.name}.{stem}")
    return names


def _import_module(name: str, source: SourceType) -> ModuleType:
    """按来源导入策略模块。"""

    pkg = _SEARCH_PACKAGE if source == "search" else _TEST_PACKAGE
    return importlib.import_module(f"{pkg}.{name}")


def _resolve_module_name_from_available(raw: str, available: list[str]) -> str | None:
    """基于候选列表解析模块名，找不到时返回 None。"""

    if raw in available:
        return raw

    by_leaf = [name for name in available if name.split(".")[-1] == raw]
    if len(by_leaf) == 1:
        return by_leaf[0]
    if len(by_leaf) > 1:
        raise ValueError(
            f"策略名短名冲突: {raw}，请使用完整模块名。候选: {sorted(by_leaf)}"
        )
    return None


def discover_modules(source: SourceType) -> list[str]:
    """按来源发现可加载策略模块。"""

    candidates = _iter_modules(
        _SEARCH_DIR if source == "search" else _TEST_DIR,
        include_subdirs=True,
        source=source,
    )
    valid: list[str] = []
    for name in candidates:
        try:
            module = _import_module(name, source)
        except Exception as exc:
            raise ValueError(f"加载策略模块失败: {source}:{name} ({exc})") from exc
        if not callable(getattr(module, "build_strategy_bundle", None)):
            raise ValueError(f"策略模块缺少 build_strategy_bundle(): {source}:{name}")
        valid.append(name)
    _validate_unique_module_refs(valid, source=source)
    return valid


def try_resolve_module_name(module_name: str, source: SourceType) -> str | None:
    """把短名解析为唯一可导入模块名；找不到返回 None。"""

    raw = module_name.strip()
    if not raw:
        raise ValueError("策略模块名不能为空")
    available = discover_modules(source)
    return _resolve_module_name_from_available(raw, available)


def resolve_module_name(module_name: str, source: SourceType) -> str:
    """把短名解析为唯一可导入模块名。"""

    resolved = try_resolve_module_name(module_name, source)
    if resolved is None:
        available = discover_modules(source)
        raise ValueError(
            f"未找到策略模块: {module_name.strip()}，可选: {sorted(available)}"
        )
    return resolved


def _validate_unique_module_refs(modules: list[str], *, source: SourceType) -> None:
    """校验完整模块名与短名都唯一。"""

    short_owners: dict[str, list[str]] = {}

    for module in modules:
        short = module.split(".")[-1]
        short_owners.setdefault(short, []).append(module)

    # 中文注释：短名唯一性是 workflow(search) 的硬约束；test 侧保留现有模块组织方式。
    if source == "search":
        short_dup = {k: v for k, v in short_owners.items() if len(v) > 1}
        if short_dup:
            raise ValueError(f"{source} 模块短名冲突，必须唯一: {short_dup}")


def _load_spec_from_resolved_name(
    resolved_name: str, source: SourceType
) -> CommonStrategySpec:
    """按已解析模块名加载并返回统一策略协议。"""

    module = _import_module(resolved_name, source)
    bundle_fn = getattr(module, "build_strategy_bundle", None)
    if not callable(bundle_fn):
        raise ValueError(f"策略模块缺少 build_strategy_bundle(): {resolved_name}")

    spec = bundle_fn()
    if not isinstance(spec, CommonStrategySpec):
        raise ValueError(
            f"build_strategy_bundle() 必须返回 CommonStrategySpec 子类: {resolved_name}"
        )

    ensure_valid_spec(spec, module_name=resolved_name)
    if source == "search" and not isinstance(spec, SearchSpaceSpec):
        raise ValueError(f"search 模块必须返回 SearchSpaceSpec: {resolved_name}")
    if source == "test" and not isinstance(spec, TestStrategySpec):
        raise ValueError(f"test 模块必须返回 TestStrategySpec: {resolved_name}")
    return spec


def load_spec_resolved(module_name: str, source: SourceType) -> CommonStrategySpec:
    """按完整模块名加载统一策略协议（不做短名解析）。"""

    return _load_spec_from_resolved_name(module_name, source)


def load_spec(module_name: str, source: SourceType) -> CommonStrategySpec:
    """加载并返回统一策略协议。"""

    resolved_name = resolve_module_name(module_name, source)
    return _load_spec_from_resolved_name(resolved_name, source)


def get_module_file(module_name: str, source: SourceType) -> Path:
    """返回策略模块文件路径。"""

    resolved_name = resolve_module_name(module_name, source)
    module = _import_module(resolved_name, source)
    module_file = getattr(module, "__file__", None)
    if not module_file:
        raise ValueError(f"策略模块无文件路径: {resolved_name}")
    return Path(module_file).resolve()


def list_specs(source: SourceType) -> list[CommonStrategySpec]:
    """加载指定来源全部策略协议。"""

    modules = discover_modules(source)
    return [_load_spec_from_resolved_name(name, source) for name in modules]


__all__ = [
    "discover_modules",
    "get_module_file",
    "list_specs",
    "load_spec",
    "load_spec_resolved",
    "resolve_module_name",
    "try_resolve_module_name",
]
