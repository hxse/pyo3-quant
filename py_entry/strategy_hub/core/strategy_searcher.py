"""策略搜索执行器（顺序执行，统一 Spec 协议）。"""

from __future__ import annotations

import argparse
from pathlib import Path

from py_entry.strategy_hub.core.searcher_args import (
    ALLOWED_TOPOLOGIES,
    expand_strategy_refs,
    parse_bool,
    parse_csv,
    parse_csv_keep_order,
    parse_modes,
)
from py_entry.strategy_hub.core.searcher_output import (
    build_output_payload,
    print_rank,
    resolve_default_output_path_for_command,
    save_json,
    utc_now_iso,
)
from py_entry.strategy_hub.core.searcher_runtime import run_modules, run_once
from py_entry.strategy_hub.core.strategy_name_guard import (
    validate_global_strategy_name_uniqueness,
)

# 中文注释：保留给测试使用的符号，避免测试直接依赖 runtime 模块路径。
_run_once = run_once


def _parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="策略搜索器（backtest/optimize/sensitivity/walk_forward）"
    )
    parser.add_argument("--strategies", default="", help="逗号分隔策略模块名")
    parser.add_argument("--symbols", default="", help="逗号分隔品种")
    parser.add_argument(
        "--topology",
        default="auto",
        choices=sorted(ALLOWED_TOPOLOGIES),
        help="任务拓扑：自动推断或显式二选一",
    )
    parser.add_argument("--mode", default="walk_forward", help="执行模式，可逗号组合")
    parser.add_argument("--positive-only", default="false", help="仅保留正收益")
    parser.add_argument("--output", default="", help="输出 JSON 文件")
    return parser.parse_args()


def _parse_required_inputs(
    args: argparse.Namespace,
) -> tuple[list[str], list[str], list[str], bool]:
    """解析并校验 workflow 输入。"""

    raw_strategies = parse_csv_keep_order(args.strategies)
    if not raw_strategies:
        raise ValueError("必须显式指定 --strategies，且至少包含一个策略")
    if len(set(raw_strategies)) != len(raw_strategies):
        raise ValueError(f"--strategies 存在重复项: {raw_strategies}")

    strategies = expand_strategy_refs(raw_strategies)
    if len(set(strategies)) != len(strategies):
        raise ValueError(
            "策略引用存在重复（可能短名与完整名指向同一策略），请去重后重试: "
            f"{raw_strategies}"
        )

    symbols = parse_csv(args.symbols)
    if not symbols:
        raise ValueError("必须显式指定 --symbols，且至少包含一个品种")

    modes = parse_modes(mode_value=args.mode)
    positive_only = parse_bool(args.positive_only)
    return strategies, symbols, modes, positive_only


def main() -> None:
    """CLI 入口。"""

    args = _parse_args()
    validate_global_strategy_name_uniqueness()
    strategies, symbols, modes, positive_only = _parse_required_inputs(args)

    rows: list[dict] = []
    for mode in modes:
        mode_rows = run_modules(
            strategies=strategies,
            symbols=symbols,
            topology=args.topology,
            mode=mode,
            positive_only=positive_only,
        )
        print_rank(mode_rows, mode)
        rows.extend(mode_rows)

    generated_at = utc_now_iso()
    payload = build_output_payload(
        results=rows,
        modes=modes,
        generated_at_utc=generated_at,
    )
    if args.output:
        save_json(payload, Path(args.output))
        return
    output_path = resolve_default_output_path_for_command(
        strategies=strategies,
        symbols=symbols,
        modes=modes,
        rows=rows,
    )
    save_json(payload, output_path)


if __name__ == "__main__":
    main()
