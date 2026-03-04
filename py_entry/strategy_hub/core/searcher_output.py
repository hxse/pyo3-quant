"""searcher 输出与落盘。"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from py_entry.strategy_hub.core.spec_loader import get_module_file

_SEARCH_SPACES_DIR = Path(__file__).resolve().parent.parent / "search_spaces"


def utc_now_iso() -> str:
    """返回 UTC ISO 时间字符串（秒级，Z 后缀）。"""

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc_now_iso_for_filename() -> str:
    """返回适用于文件名的 UTC ISO 字符串（冒号替换为下划线）。"""

    return utc_now_iso().replace(":", "_")


def print_rank(results: list[dict[str, Any]], run_mode: str) -> None:
    """打印排序结果。"""

    print(f"\n=== Strategy Search Rank ({run_mode}) ===")
    for i, row in enumerate(results, start=1):
        metrics = row["performance"]
        if run_mode == "sensitivity":
            meta = row.get("sensitivity_meta", {})
            print(
                f"{i}. {row['strategy_name']} {row['symbol']} | "
                f"target={meta.get('target_metric')} | "
                f"mean={metrics.get('mean')} | std={metrics.get('std')} | cv={metrics.get('cv')}"
            )
            continue
        if run_mode == "optimize":
            print(
                f"{i}. {row['strategy_name']} {row['symbol']} | "
                f"calmar_raw={metrics.get('calmar_ratio_raw')} | "
                f"return={metrics.get('total_return')} | "
                f"max_dd={metrics.get('max_drawdown')} | "
                f"trades={metrics.get('total_trades')} | "
                f"samples={row.get('optimize_total_samples')} | rounds={row.get('optimize_rounds')}"
            )
            continue
        print(
            f"{i}. {row['strategy_name']} {row['symbol']} | "
            f"calmar_raw={metrics.get('calmar_ratio_raw')} | "
            f"return={metrics.get('total_return')} | "
            f"max_dd={metrics.get('max_drawdown')} | "
            f"trades={metrics.get('total_trades')}"
        )


def build_output_payload(
    *,
    results: list[dict[str, Any]],
    modes: list[str],
    generated_at_utc: str,
) -> dict[str, Any]:
    """构建标准日志输出。"""

    payload: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "modes": modes,
        "results": results,
    }
    return payload


def save_json(payload: dict[str, Any], output_path: Path) -> None:
    """保存 JSON 输出。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved: {output_path}")


def _build_output_path_with_retry(log_dir: Path, strategy_name: str) -> Path:
    """构建日志路径，冲突重试 3 次。"""

    log_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        ts = _utc_now_iso_for_filename()
        candidate = log_dir / f"{ts}_{strategy_name}.json"
        if not candidate.exists():
            return candidate
        time.sleep(1)
    raise RuntimeError("日志文件名冲突，建议重跑命令")


def resolve_default_output_path(strategy_name: str, module_name: str) -> Path:
    """按策略模块同目录生成日志路径。"""

    module_file = get_module_file(module_name, "search")
    return _build_output_path_with_retry(module_file.parent / "logs", strategy_name)


def _sanitize_symbol_dir(symbol: str) -> str:
    """将 symbol 规范化为可用目录名。"""

    return symbol.strip().replace("/", "_").replace(":", "_")


def _build_command_hash(
    *,
    strategies: list[str],
    symbols: list[str],
    modes: list[str],
) -> str:
    """按命令输入构建稳定短哈希。"""

    raw = (
        f"strategies={'|'.join(strategies)};"
        f"symbols={'|'.join(symbols)};"
        f"modes={'|'.join(modes)}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def resolve_default_output_path_for_command(
    *,
    strategies: list[str],
    symbols: list[str],
    modes: list[str],
    rows: list[dict[str, Any]],
) -> Path:
    """按命令维度生成唯一默认日志路径（一个命令一个文件）。"""

    if not strategies:
        raise ValueError("strategies 不能为空")
    if not symbols:
        raise ValueError("symbols 不能为空")

    # 中文注释：单策略（含单/多品种）固定落该策略目录的 logs。
    if len(strategies) == 1:
        module_name = strategies[0]
        strategy_name = module_name.split(".")[-1]
        if rows:
            for row in rows:
                if row.get("strategy_module", "").endswith(f".{module_name}"):
                    strategy_name = str(row.get("strategy_name") or strategy_name)
                    break
        return resolve_default_output_path(strategy_name, module_name)

    # 中文注释：单品种多策略固定落 search_spaces/logs/<symbol>/。
    if len(symbols) == 1:
        symbol_dir = _sanitize_symbol_dir(symbols[0])
        command_hash = _build_command_hash(
            strategies=strategies,
            symbols=symbols,
            modes=modes,
        )
        return _build_output_path_with_retry(
            _SEARCH_SPACES_DIR / "logs" / symbol_dir,
            command_hash,
        )

    # 中文注释：理论上 workflow 已禁止多策略+多品种，此分支仅兜底。
    command_hash = _build_command_hash(
        strategies=strategies,
        symbols=symbols,
        modes=modes,
    )
    return _build_output_path_with_retry(
        _SEARCH_SPACES_DIR / "logs" / "mixed",
        command_hash,
    )
