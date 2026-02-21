"""
简易策略搜索器（顺序执行，支持默认回测与向前测试两种模式）。

设计原则：
1. 搜索器只负责调度，不内嵌具体策略组合；
2. 搜索组合放在 search_spaces 目录中，和正式策略文件解耦；
3. 默认顺序执行，避免本地机器过载。
4. 支持两种验证模式：default backtest 与 walk_forward。
"""

from __future__ import annotations

import argparse
import importlib
import json
from datetime import datetime, UTC
from pathlib import Path
from types import ModuleType
from typing import Any

from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.io import load_local_config
from py_entry.runner import Backtest
from py_entry.types import ExecutionStage, SettingContainer

_SEARCH_SPACE_PACKAGE = "py_entry.private_strategies.search_spaces"
_SEARCH_SPACE_DIR = Path(__file__).resolve().parent / "search_spaces"
_ALLOWED_MODES = {"backtest", "walk_forward"}


def _discover_space_modules() -> list[str]:
    """扫描 search_spaces 顶层与一层子目录，返回可加载模块名列表。"""
    names: list[str] = []
    # 中文注释：先扫描顶层 *.py，兼容当前平铺组织方式。
    for py_file in sorted(_SEARCH_SPACE_DIR.glob("*.py"), key=lambda p: p.name):
        mod = py_file.stem
        if mod == "__init__" or mod.startswith("_"):
            continue
        names.append(mod)

    # 中文注释：再扫描一层子目录，便于按主题分类策略；显式跳过 trash 垃圾箱目录。
    for child in sorted(_SEARCH_SPACE_DIR.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if child.name in {"trash", "__pycache__"} or child.name.startswith((".", "_")):
            continue
        for py_file in sorted(child.glob("*.py"), key=lambda p: p.name):
            mod = py_file.stem
            if mod == "__init__" or mod.startswith("_"):
                continue
            names.append(f"{child.name}.{mod}")
    return names


def _load_space_module(module_name: str) -> ModuleType:
    """加载单个搜索空间模块。"""
    return importlib.import_module(f"{_SEARCH_SPACE_PACKAGE}.{module_name}")


def _parse_csv(value: str) -> list[str]:
    """解析逗号分隔参数并去重保序。"""
    items = [x.strip() for x in value.split(",") if x.strip()]
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _build_data_source(space: dict[str, Any], symbol_override: str | None):
    """根据搜索空间定义构建数据源。"""
    symbol = symbol_override or str(space["symbol"])
    return OhlcvDataFetchConfig(
        config=load_local_config(),
        exchange_name="binance",
        market="future",
        symbol=symbol,
        timeframes=list(space["timeframes"]),
        since=get_utc_timestamp_ms(str(space["since"])),
        limit=int(space["limit"]),
        enable_cache=True,
        mode="live",
        base_data_key=str(space["base_data_key"]),
    )


def _score_of(metrics: dict[str, Any]) -> tuple[float, float, float]:
    """统一排序口径：calmar_raw > total_return > -max_drawdown。"""
    calmar_raw = float(metrics.get("calmar_ratio_raw", float("-inf")))
    total_return = float(metrics.get("total_return", float("-inf")))
    max_dd = float(metrics.get("max_drawdown", float("inf")))
    return calmar_raw, total_return, -max_dd


def _parse_bool(value: str) -> bool:
    """解析布尔字符串。"""
    norm = value.strip().lower()
    if norm in {"1", "true", "yes", "y", "on"}:
        return True
    if norm in {"0", "false", "no", "n", "off", ""}:
        return False
    raise ValueError(f"无法解析布尔值: {value}")


def _is_positive_return(metrics: dict[str, Any]) -> bool:
    """判断是否为正收益。"""
    return float(metrics.get("total_return", 0.0)) > 0.0


def _extract_summary_metrics(run_mode: str, result: Any) -> dict[str, Any]:
    """抽取统一摘要指标。"""
    if run_mode == "backtest":
        # 中文注释：默认参数回测直接读取单次回测 performance。
        return result.summary.performance or {}
    # 中文注释：向前测试读取拼接 OOS 聚合指标。
    return result.aggregate_test_metrics


def _run_single_variant(
    space: dict[str, Any],
    variant: dict[str, Any],
    symbol_override: str | None,
    run_mode: str,
) -> dict[str, Any]:
    """执行单个变体。"""
    bt = Backtest(
        enable_timing=True,
        data_source=_build_data_source(space, symbol_override),
        indicators=variant["indicators"],
        signal=variant.get("signal_params", {}),
        backtest=variant.get("backtest", space["backtest"]),
        signal_template=variant["template"],
        engine_settings=SettingContainer(
            execution_stage=ExecutionStage.Performance,
            return_only_final=False,
        ),
    )

    if run_mode == "backtest":
        run_result = bt.run()
        metrics = _extract_summary_metrics(run_mode, run_result)
        return {
            "mode": run_mode,
            "space": space["space_name"],
            "name": variant["name"],
            "note": variant.get("note", ""),
            "symbol": symbol_override or space["symbol"],
            "metrics": metrics,
            "best_window_id": None,
            "worst_window_id": None,
        }

    wf = bt.walk_forward(variant.get("wf", space["wf"]))
    metrics = _extract_summary_metrics(run_mode, wf)
    return {
        "mode": run_mode,
        "space": space["space_name"],
        "name": variant["name"],
        "note": variant.get("note", ""),
        "symbol": symbol_override or space["symbol"],
        "metrics": metrics,
        "best_window_id": wf.best_window_id,
        "worst_window_id": wf.worst_window_id,
    }


def _print_rank(results: list[dict[str, Any]], run_mode: str) -> None:
    """打印排序结果。"""
    print(f"\n=== Strategy Search Rank ({run_mode}) ===")
    for i, r in enumerate(results, start=1):
        m = r["metrics"]
        print(
            f"{i}. [{r['space']}] {r['name']} | "
            f"calmar_raw={m.get('calmar_ratio_raw')} | "
            f"return={m.get('total_return')} | "
            f"max_dd={m.get('max_drawdown')} | "
            f"trades={m.get('total_trades')}"
        )


def _save_json(results: list[dict[str, Any]], output_path: Path) -> None:
    """保存 JSON 结果。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "results": results,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved: {output_path}")


def _build_run_tasks(
    spaces: list[str], symbols: list[str]
) -> list[tuple[str, str | None]]:
    """构建执行任务，限制只支持两种模式。"""
    if not symbols:
        return [(space, None) for space in spaces]

    if len(spaces) == 1:
        # 中文注释：单策略多品种。
        return [(spaces[0], symbol) for symbol in symbols]

    if len(symbols) == 1:
        # 中文注释：单品种多策略。
        return [(space, symbols[0]) for space in spaces]

    # 中文注释：明确拒绝“多策略+多品种”混合搜索，避免任务语义不清。
    raise ValueError(
        "不支持“不同品种不同策略”组合。只支持：1) 单策略多品种；2) 单品种多策略。"
    )


def run_search(
    spaces: list[str],
    symbols: list[str],
    run_mode: str,
    positive_only: bool,
) -> list[dict[str, Any]]:
    """顺序执行多个搜索空间并返回排序后的结果。"""
    if run_mode not in _ALLOWED_MODES:
        raise ValueError(f"未知模式: {run_mode}，可选: {sorted(_ALLOWED_MODES)}")

    all_results: list[dict[str, Any]] = []
    tasks = _build_run_tasks(spaces, symbols)

    for module_name, symbol_override in tasks:
        module = _load_space_module(module_name)
        builder = getattr(module, "build_search_space", None)
        if builder is None or not callable(builder):
            raise AttributeError(
                f"搜索空间模块 {module_name} 缺少 build_search_space()"
            )

        space = builder()
        variants = list(space.get("variants", []))
        if not variants:
            print(f"skip [{module_name}]: no variants")
            continue

        run_symbol = symbol_override or str(space["symbol"])
        print(
            f"\n--- space: {space['space_name']} ({module_name}), "
            f"symbol={run_symbol}, variants={len(variants)}, mode={run_mode} ---"
        )
        for idx, variant in enumerate(variants, start=1):
            print(f"[{idx}/{len(variants)}] running {variant['name']} ...")
            result = _run_single_variant(space, variant, symbol_override, run_mode)
            m = result["metrics"]
            if positive_only and not _is_positive_return(m):
                print("summary: skip non-positive total_return")
                continue
            all_results.append(result)
            print(
                "summary:",
                {
                    "calmar_ratio_raw": m.get("calmar_ratio_raw"),
                    "total_return": m.get("total_return"),
                    "max_drawdown": m.get("max_drawdown"),
                    "total_trades": m.get("total_trades"),
                },
            )

    all_results.sort(key=lambda x: _score_of(x["metrics"]), reverse=True)
    return all_results


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="简易策略搜索器（支持 backtest/walk_forward，顺序执行）"
    )
    parser.add_argument(
        "--spaces",
        default="",
        help="逗号分隔的搜索空间模块名；为空时自动扫描全部（例如: sol_macd_3tf,sol_rsi30_macd4h）",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="逗号分隔品种（例如: SOL/USDT,BTC/USDT）。仅支持单策略多品种或单品种多策略。",
    )
    parser.add_argument(
        "--mode",
        default="walk_forward",
        choices=sorted(_ALLOWED_MODES),
        help="运行模式：backtest=默认参数单次回测；walk_forward=向前测试。",
    )
    parser.add_argument(
        "--positive-only",
        default="false",
        help="是否仅保留 total_return>0 的结果（true/false）。",
    )
    parser.add_argument("--output", default="", help="可选：输出 JSON 文件路径")
    args = parser.parse_args()

    available = _discover_space_modules()
    if not available:
        raise ValueError("未发现任何搜索空间模块，请先在 search_spaces/ 下创建 *.py")

    if args.spaces.strip():
        requested = _parse_csv(args.spaces)
        unknown = [x for x in requested if x not in available]
        if unknown:
            raise ValueError(f"未知搜索空间: {unknown}，可选: {available}")
        spaces = requested
    else:
        spaces = available

    symbols = _parse_csv(args.symbols)
    results = run_search(
        spaces=spaces,
        symbols=symbols,
        run_mode=args.mode,
        positive_only=_parse_bool(args.positive_only),
    )
    _print_rank(results, run_mode=args.mode)

    if args.output:
        _save_json(results, Path(args.output))


if __name__ == "__main__":
    main()
