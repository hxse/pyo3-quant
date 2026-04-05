"""searcher 执行与排序。"""

from __future__ import annotations

from typing import Any

from py_entry.strategy_hub.core.executor import (
    build_backtest,
    get_stage_configs,
    run_stage,
)
from py_entry.strategy_hub.core.searcher_args import ALLOWED_TOPOLOGIES
from py_entry.strategy_hub.core.searcher_serialize import (
    default_backtest_time_info,
    extract_backtest_time_info,
    extract_optimize_info,
    extract_sensitivity_info,
    extract_wf_window_logs,
    safe_attr,
    serialize_single_param_set,
)
from py_entry.strategy_hub.core.spec import SearchSpaceSpec
from py_entry.strategy_hub.core.spec_loader import load_spec


def score_of(metrics: dict[str, Any]) -> tuple[float, float, float]:
    """统一排序口径：calmar_raw > total_return > -max_drawdown。"""

    if "mean" in metrics:
        mean = float(metrics.get("mean", float("-inf")))
        std = float(metrics.get("std", float("inf")) or float("inf"))
        cv = float(metrics.get("cv", float("inf")) or float("inf"))
        return mean, -std, -cv
    calmar_raw = float(metrics.get("calmar_ratio_raw", float("-inf")))
    total_return = float(metrics.get("total_return", float("-inf")))
    max_dd = float(metrics.get("max_drawdown", float("inf")) or float("inf"))
    return calmar_raw, total_return, -max_dd


def is_positive_return(metrics: dict[str, Any]) -> bool:
    """判断是否为正收益。"""

    if "total_return" not in metrics:
        return True
    return float(metrics.get("total_return", 0.0) or 0.0) > 0.0


def _default_stage_fields() -> dict[str, Any]:
    """返回统一默认字段，避免各 stage 手写占位键。"""

    return {
        "windows": [],
        "last_window_start_time_ms": None,
        "last_window_best_params": None,
        **default_backtest_time_info(),
        "best_window_id": None,
        "worst_window_id": None,
    }


def build_strategy_runtime(
    module_name: str, *, run_symbol: str | None = None
) -> tuple[SearchSpaceSpec, dict[str, Any], Any]:
    """构建 search runtime（core 内部直连，不经过包级 re-export）。"""

    # 中文注释：空白 symbol 统一按未提供处理，保持与外层入口行为一致。
    symbol = (run_symbol or "").strip() or None
    spec = load_spec(module_name, "search")
    if not isinstance(spec, SearchSpaceSpec):
        raise TypeError(f"搜索模块必须返回 SearchSpaceSpec: {module_name}")
    stages = get_stage_configs(spec)
    bt = build_backtest(spec, symbol=symbol)
    return spec, stages, bt


def run_once(
    *,
    module_name: str,
    symbol_override: str | None,
    run_mode: str,
) -> dict[str, Any]:
    """执行单策略单品种。"""

    spec, stages, bt = build_strategy_runtime(module_name, run_symbol=symbol_override)

    default_params = safe_attr(bt, "params")
    resolved_symbol = symbol_override or str(
        getattr(spec.data_config, "symbol", "") or ""
    )

    base_row = {
        "strategy_name": spec.name,
        "strategy_version": spec.version,
        "strategy_module": f"py_entry.strategy_hub.search_spaces.{module_name}",
        "mode": run_mode,
        "symbol": resolved_symbol,
        "base_data_key": spec.data_config.base_data_key,
        "backtest_default_params": serialize_single_param_set(default_params),
        **_default_stage_fields(),
    }
    raw_result = run_stage(
        spec, stage=run_mode, symbol=symbol_override, bt=bt, stages=stages
    )

    if run_mode == "backtest":
        run_result = raw_result
        return {
            **base_row,
            "performance": run_result.result.performance or {},
            **extract_backtest_time_info(run_result),
        }

    if run_mode == "optimize":
        opt_result = raw_result
        return {
            **base_row,
            **extract_optimize_info(opt_result),
        }

    if run_mode == "sensitivity":
        sens_result = raw_result
        return {
            **base_row,
            **extract_sensitivity_info(sens_result),
        }

    if run_mode == "walk_forward":
        wf = raw_result
        windows, tail = extract_wf_window_logs(wf)
        return {
            **base_row,
            "performance": wf.aggregate_test_metrics,
            "windows": windows,
            "last_window_start_time_ms": tail["last_window_start_time_ms"],
            "last_window_best_params": tail["last_window_best_params"],
            "best_window_id": wf.best_window_id,
            "worst_window_id": wf.worst_window_id,
        }
    raise ValueError(f"未知 mode: {run_mode}")


def build_run_tasks(
    strategies: list[str], symbols: list[str], topology: str
) -> list[tuple[str, str | None]]:
    """构建执行任务，仅支持两种拓扑。"""

    if topology not in ALLOWED_TOPOLOGIES:
        raise ValueError(
            f"未知 topology: {topology}，可选: {sorted(ALLOWED_TOPOLOGIES)}"
        )

    if topology == "single_strategy_multi_symbols":
        if len(strategies) != 1 or len(symbols) < 1:
            raise ValueError(
                "topology=single_strategy_multi_symbols 要求: 单策略 + 至少一个品种"
            )
        return [(strategies[0], symbol) for symbol in symbols]

    if topology == "single_symbol_multi_strategies":
        if len(symbols) != 1 or len(strategies) < 1:
            raise ValueError(
                "topology=single_symbol_multi_strategies 要求: 单品种 + 至少一个策略"
            )
        return [(strategy, symbols[0]) for strategy in strategies]

    if len(strategies) == 1:
        return [(strategies[0], symbol) for symbol in symbols]
    if len(symbols) == 1:
        return [(strategy, symbols[0]) for strategy in strategies]
    raise ValueError("不支持多策略+多品种混合执行，仅支持单策略多品种或单品种多策略")


def run_modules(
    *,
    strategies: list[str],
    symbols: list[str],
    topology: str,
    mode: str,
    positive_only: bool,
) -> list[dict[str, Any]]:
    """执行多个策略模块。"""

    tasks = build_run_tasks(strategies, symbols, topology)
    rows: list[dict[str, Any]] = []
    for module_name, symbol in tasks:
        row = run_once(
            module_name=module_name,
            symbol_override=symbol,
            run_mode=mode,
        )
        if positive_only and not is_positive_return(row["performance"]):
            continue
        rows.append(row)

    rows.sort(key=lambda r: score_of(r["performance"]), reverse=True)
    return rows
