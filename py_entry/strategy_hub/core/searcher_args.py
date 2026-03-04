"""searcher 参数解析。"""

from __future__ import annotations

from py_entry.strategy_hub.core.spec_loader import discover_modules, resolve_module_name

ALLOWED_MODES = {"backtest", "optimize", "sensitivity", "walk_forward"}
ALLOWED_TOPOLOGIES = {
    "auto",
    "single_strategy_multi_symbols",
    "single_symbol_multi_strategies",
}


def parse_csv(value: str) -> list[str]:
    """解析逗号分隔参数；若出现重复项则直接报错。"""

    items = [x.strip() for x in value.split(",") if x.strip()]
    seen: set[str] = set()
    dup: list[str] = []
    for item in items:
        if item in seen:
            dup.append(item)
            continue
        seen.add(item)
    if dup:
        # 中文注释：与 strategies/mode 保持一致，重复输入不做静默纠正。
        raise ValueError(f"存在重复项，请先去重: {dup}")
    return items


def parse_csv_keep_order(value: str) -> list[str]:
    """解析逗号分隔参数，保留顺序与重复项。"""

    return [x.strip() for x in value.split(",") if x.strip()]


def parse_bool(value: str) -> bool:
    """解析布尔字符串。"""

    norm = value.strip().lower()
    if norm in {"1", "true", "yes", "y", "on"}:
        return True
    if norm in {"0", "false", "no", "n", "off", ""}:
        return False
    raise ValueError(f"无法解析布尔值: {value}")


def parse_modes(*, mode_value: str) -> list[str]:
    """解析执行模式，支持组合执行。"""

    modes = parse_csv_keep_order(mode_value) or ["walk_forward"]
    if len(set(modes)) != len(modes):
        raise ValueError(f"mode 重复，必须去重后再执行: {modes}")
    unknown = [m for m in modes if m not in ALLOWED_MODES]
    if unknown:
        raise ValueError(
            f"未知 mode: {unknown}，仅支持: {sorted(ALLOWED_MODES)}，可逗号组合"
        )
    return modes


def expand_strategy_refs(raw_refs: list[str]) -> list[str]:
    """展开策略引用，支持 `folder.*` 与 `*`。"""

    available = discover_modules("search")
    resolved: list[str] = []
    for raw in raw_refs:
        if raw == "*":
            if not available:
                raise ValueError("未找到任何搜索空间策略，无法展开 `*`")
            resolved.extend(available)
            continue
        if raw.endswith(".*"):
            prefix = raw[:-2].strip().rstrip(".")
            if not prefix:
                raise ValueError("通配策略前缀不能为空，例如: sma_2tf.*")
            # 中文注释：folder.* 只匹配该子目录下的策略模块。
            matches = [name for name in available if name.startswith(f"{prefix}.")]
            if not matches:
                raise ValueError(f"未找到子目录策略: {raw}，可选: {sorted(available)}")
            resolved.extend(matches)
            continue
        resolved.append(resolve_module_name(raw, "search"))
    return resolved
