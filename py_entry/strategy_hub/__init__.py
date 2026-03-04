"""strategy_hub 包统一导出（统一 Spec 协议）。"""

from __future__ import annotations

from typing import Any, Literal

from py_entry.runner import Backtest

from .core.executor import (
    build_backtest as _build_backtest,
    get_stage_configs as _get_stage_configs,
)
from .core.spec import CommonStrategySpec
from .core.spec_loader import (
    discover_modules,
    load_spec,
    resolve_module_name,
    try_resolve_module_name,
)


def _resolve_strategy_ref(strategy_ref: str) -> tuple[Literal["search", "test"], str]:
    """解析统一策略引用，返回 (source, name)。"""

    raw = strategy_ref.strip()
    if not raw:
        raise ValueError("策略引用不能为空")

    if ":" in raw:
        source_raw, name = raw.split(":", 1)
        source_raw = source_raw.strip()
        name = name.strip()
        if source_raw not in {"search", "test"}:
            raise ValueError(f"策略引用来源非法: {source_raw}，仅支持 search/test")
        source: Literal["search", "test"] = (
            "search" if source_raw == "search" else "test"
        )
        if not name:
            raise ValueError("策略引用名称不能为空")
        resolved = resolve_module_name(name, source)
        return source, resolved

    search_resolved = try_resolve_module_name(raw, "search")
    test_resolved = try_resolve_module_name(raw, "test")

    if search_resolved and test_resolved:
        raise ValueError(f"策略名歧义: {raw}，请使用 search:{raw} 或 test:{raw}")
    if search_resolved:
        return "search", search_resolved
    if test_resolved:
        return "test", test_resolved
    raise ValueError(f"未找到策略: {raw}，可选: {_list_strategy_refs()}")


def _list_strategy_refs() -> list[str]:
    """返回统一策略引用列表（search:xxx / test:xxx）。"""

    refs: list[str] = []
    refs.extend([f"search:{name}" for name in discover_modules("search")])
    refs.extend([f"test:{name}" for name in discover_modules("test")])
    return refs


def get_strategy_refs() -> list[str]:
    """返回可选策略引用列表（仅用于展示/选择）。"""

    return _list_strategy_refs()


def build_strategy_runtime(
    strategy_ref: str, *, run_symbol: str | None = None
) -> tuple[CommonStrategySpec, dict[str, Any], Backtest]:
    """统一构建策略运行时对象（内部完成 symbol 校验）。"""

    # 统一清洗外部输入，空白字符串按未提供处理。
    symbol = (run_symbol or "").strip() or None
    source, name = _resolve_strategy_ref(strategy_ref)
    spec = load_spec(name, source)
    stage_cfgs = _get_stage_configs(spec)
    bt = _build_backtest(spec, symbol=symbol)
    return spec, stage_cfgs, bt


__all__ = [
    "build_strategy_runtime",
    "get_strategy_refs",
]
