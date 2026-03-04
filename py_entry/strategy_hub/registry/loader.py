"""注册器加载与预检。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

ParamSource = Literal["backtest_default", "walk_forward_last_window"]
RunMode = Literal["backtest", "walk_forward"]


class RegistryItemModel(BaseModel):
    """注册器条目模型。"""

    log_path: str = Field(min_length=1)
    symbol: str
    mode: RunMode
    enabled: bool = Field(default=True)
    position_size_pct: float = Field(ge=0.0, le=1.0)
    leverage: int = Field(ge=1)


@dataclass(frozen=True)
class RegistryResolvedItem:
    """注册器解析后的可运行条目。"""

    strategy_name: str
    strategy_version: str
    strategy_module: str
    symbol: str
    mode: RunMode
    param_source: ParamSource
    params: dict[str, Any]
    start_time_ms: int
    base_data_key: str
    enabled: bool
    position_size_pct: float
    leverage: int


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"JSON 解析失败: {path} ({exc})") from exc


def _require_key(obj: dict[str, Any], key: str, ctx: str) -> Any:
    """强约束读取键。"""

    if key not in obj:
        raise ValueError(f"{ctx} 缺少字段: {key}")
    return obj[key]


def _ensure_single_strategy_results(log_payload: dict[str, Any], ctx: str) -> str:
    """校验单日志单策略。"""

    results = _require_key(log_payload, "results", ctx)
    if not isinstance(results, list) or not results:
        raise ValueError(f"{ctx}.results 必须是非空 list")
    names = {
        str(item.get("strategy_name"))
        for item in results
        if isinstance(item, dict) and item.get("strategy_name") is not None
    }
    if len(names) != 1:
        raise ValueError(
            f"{ctx} 必须是单日志单策略，当前 strategy_name 集合: {sorted(names)}"
        )
    return next(iter(names))


def _resolve_log_entry(
    *,
    log_payload: dict[str, Any],
    symbol: str,
    mode: RunMode,
    ctx: str,
) -> dict[str, Any]:
    """按 (symbol, mode) 从日志定位条目。"""

    results = _require_key(log_payload, "results", ctx)
    matches: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("symbol") == symbol and item.get("mode") == mode:
            matches.append(item)
    if len(matches) > 1:
        raise ValueError(
            f"{ctx} 匹配日志条目必须唯一: (symbol={symbol}, mode={mode}), 当前匹配数量={len(matches)}"
        )
    if len(matches) == 1:
        return matches[0]
    raise ValueError(f"{ctx} 未找到匹配日志条目: (symbol={symbol}, mode={mode})")


def _extract_params_and_time(
    *, log_entry: dict[str, Any], mode: RunMode, ctx: str
) -> tuple[ParamSource, dict[str, Any], int]:
    """按 mode 提取参数与时间。"""

    if mode == "backtest":
        param_source: ParamSource = "backtest_default"
        params = _require_key(log_entry, "backtest_default_params", ctx)
        start_time_ms = _require_key(log_entry, "backtest_start_time_ms", ctx)
    else:
        param_source = "walk_forward_last_window"
        params = _require_key(log_entry, "last_window_best_params", ctx)
        start_time_ms = _require_key(log_entry, "last_window_start_time_ms", ctx)

    if not isinstance(params, dict):
        raise ValueError(f"{ctx} 参数字段必须是 dict")
    if not isinstance(start_time_ms, int):
        raise ValueError(f"{ctx} 起始时间必须是 int(ms)")
    return param_source, params, start_time_ms


def _validate_registered_strategy_name_uniqueness(
    items: list[RegistryResolvedItem],
) -> None:
    """仅校验已注册条目的“同名必须同模块”。"""

    owners: dict[str, list[str]] = {}
    modules_by_name: dict[str, set[str]] = {}
    for item in items:
        owners.setdefault(item.strategy_name, []).append(
            f"{item.symbol} ({item.strategy_module})"
        )
        # 中文注释：允许同一策略多品种部署，但同名策略必须来自同一个模块实现。
        modules_by_name.setdefault(item.strategy_name, set()).add(item.strategy_module)
    conflicts = {
        name: refs
        for name, refs in owners.items()
        if len(modules_by_name.get(name, set())) > 1
    }
    if conflicts:
        lines = ["注册器冲突：同名策略必须映射到同一 strategy_module："]
        for name, refs in sorted(conflicts.items(), key=lambda x: x[0]):
            lines.append(f"- {name}: {refs}")
        raise ValueError("\n".join(lines))


def load_registry_items(registry_path: str | Path) -> list[RegistryResolvedItem]:
    """加载并预检注册器。"""

    path = Path(registry_path).resolve()
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise ValueError("注册器文件必须是 JSON 数组")

    models: list[RegistryItemModel] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"registry[{idx}] 必须是 object")
        models.append(RegistryItemModel.model_validate(item))

    enabled_models = [(idx, model) for idx, model in enumerate(models) if model.enabled]
    symbol_counts: dict[str, int] = {}
    for _, model in enabled_models:
        symbol_counts[model.symbol] = symbol_counts.get(model.symbol, 0) + 1
    dup = sorted(symbol for symbol, count in symbol_counts.items() if count > 1)
    if dup:
        raise ValueError(
            f"注册器冲突：同一 symbol 仅允许一个 enabled 条目，重复: {dup}"
        )

    resolved: list[RegistryResolvedItem] = []
    for original_idx, item in enabled_models:
        # 中文注释：错误上下文使用原始 JSON 索引，避免 enabled 过滤后索引漂移。
        ctx = f"registry[{original_idx}]"
        log_path = Path(item.log_path)
        if not log_path.is_absolute():
            log_path = (path.parent / log_path).resolve()
        if not log_path.exists():
            raise ValueError(f"{ctx}.log_path 不存在: {log_path}")

        log_payload = _load_json(log_path)
        if not isinstance(log_payload, dict):
            raise ValueError(f"{ctx}.log_path 顶层必须是 object")

        _ensure_single_strategy_results(log_payload, ctx)
        log_entry = _resolve_log_entry(
            log_payload=log_payload,
            symbol=item.symbol,
            mode=item.mode,
            ctx=ctx,
        )

        param_source, params, start_time_ms = _extract_params_and_time(
            log_entry=log_entry,
            mode=item.mode,
            ctx=ctx,
        )

        resolved.append(
            RegistryResolvedItem(
                strategy_name=str(_require_key(log_entry, "strategy_name", ctx)),
                strategy_version=str(_require_key(log_entry, "strategy_version", ctx)),
                strategy_module=str(_require_key(log_entry, "strategy_module", ctx)),
                symbol=item.symbol,
                mode=item.mode,
                param_source=param_source,
                params=params,
                start_time_ms=start_time_ms,
                base_data_key=str(_require_key(log_entry, "base_data_key", ctx)),
                enabled=item.enabled,
                position_size_pct=item.position_size_pct,
                leverage=item.leverage,
            )
        )

    # 中文注释：bot 启动仅校验已注册策略名，不扫描未注册策略。
    _validate_registered_strategy_name_uniqueness(resolved)
    return resolved
