"""Runner 层统一管道执行与摘要输出。"""

from __future__ import annotations

from typing import Any

from py_entry.runner.backtest import Backtest
from py_entry.types import OptimizerConfig, SensitivityConfig, WalkForwardConfig


def extract_optimize_key_params(
    opt_result: Any, base_data_key: str
) -> dict[str, object]:
    """提取优化关键参数，避免输出全量参数树。"""
    summary: dict[str, object] = {}

    indicators = getattr(opt_result.best_params, "indicators", {})
    indicator_group = (
        indicators.get(base_data_key, {}) if isinstance(indicators, dict) else {}
    )
    for indicator_name, params in indicator_group.items():
        if not isinstance(params, dict):
            continue
        for param_name, param_obj in params.items():
            value = getattr(param_obj, "value", param_obj)
            summary[f"{indicator_name}.{param_name}"] = value

    # 中文注释：常见回测参数保留显式白名单，避免无关字段过量输出。
    for key in (
        "sl_pct",
        "tp_pct",
        "tsl_pct",
        "sl_atr",
        "tp_atr",
        "tsl_atr",
        "atr_period",
    ):
        param_obj = getattr(opt_result.best_backtest_params, key, None)
        value = getattr(param_obj, "value", param_obj)
        if value is not None:
            summary[key] = value

    return summary


def run_pipeline(
    bt: Backtest,
    *,
    base_data_key: str,
    opt_cfg: OptimizerConfig,
    sens_cfg: SensitivityConfig,
    wf_cfg: WalkForwardConfig,
) -> dict[str, object]:
    """非交互式顺序执行完整研究管道。"""
    summary: dict[str, object] = {
        "backtest": None,
        "optimize": None,
        "sensitivity": None,
        "walk_forward": None,
    }

    backtest_result = bt.run()
    summary["backtest"] = (
        backtest_result.summary.performance if backtest_result.summary else None
    )
    summary["backtest_stage"] = {"status": "ok"}

    opt_result = bt.optimize(opt_cfg)
    summary["optimize"] = {
        "metric": str(opt_result.optimize_metric),
        "value": opt_result.optimize_value,
        "samples": opt_result.total_samples,
        "rounds": opt_result.rounds,
        "best_params": extract_optimize_key_params(opt_result, base_data_key),
    }
    summary["optimize_stage"] = {"status": "ok"}

    sens_result = bt.sensitivity(sens_cfg)
    summary["sensitivity"] = {
        "target_metric": str(sens_result.target_metric),
        "original_value": sens_result.original_value,
        "total_samples_requested": sens_result.total_samples_requested,
        "successful_samples": sens_result.successful_samples,
        "failed_samples": sens_result.failed_samples,
        "failed_sample_rate": sens_result.failed_sample_rate,
        "mean": sens_result.mean,
        "std": sens_result.std,
        "p05": sens_result.p05,
        "p25": sens_result.p25,
        "median": sens_result.median,
        "p75": sens_result.p75,
        "p95": sens_result.p95,
        "min": sens_result.min,
        "max": sens_result.max,
        "cv": sens_result.cv,
        "top_k_samples": [
            {"metric_value": s.metric_value, "values": s.values}
            for s in sens_result.top_k_samples
        ],
        "bottom_k_samples": [
            {"metric_value": s.metric_value, "values": s.values}
            for s in sens_result.bottom_k_samples
        ],
    }
    summary["sensitivity_stage"] = {"status": "ok"}

    wf_result = bt.walk_forward(wf_cfg)
    stitched_metrics = wf_result.aggregate_test_metrics
    summary["walk_forward"] = {
        "optimize_metric": str(wf_result.optimize_metric),
        "aggregate_test_metrics": stitched_metrics,
        "best_window_id": wf_result.best_window_id,
        "worst_window_id": wf_result.worst_window_id,
        "stitched_time_range": wf_result.stitched_result.time_range,
        "stitched_bars": wf_result.stitched_result.bars,
        "rolling_every_days": wf_result.stitched_result.rolling_every_days,
        "next_window_hint": {
            "expected_train_start_time_ms": wf_result.stitched_result.next_window_hint.expected_train_start_time_ms,
            "expected_transition_start_time_ms": wf_result.stitched_result.next_window_hint.expected_transition_start_time_ms,
            "expected_test_start_time_ms": wf_result.stitched_result.next_window_hint.expected_test_start_time_ms,
            "expected_test_end_time_ms": wf_result.stitched_result.next_window_hint.expected_test_end_time_ms,
            "expected_window_ready_time_ms": wf_result.stitched_result.next_window_hint.expected_window_ready_time_ms,
            "eta_days": wf_result.stitched_result.next_window_hint.eta_days,
            "based_on_window_id": wf_result.stitched_result.next_window_hint.based_on_window_id,
        },
        "window_best_params": [
            {
                "window_id": w.window_id,
                "train_range": w.train_range,
                "transition_range": w.transition_range,
                "test_range": w.test_range,
                "best_params": str(w.best_params),
                "has_cross_boundary_position": w.has_cross_boundary_position,
                "test_metrics": w.summary.performance or {},
            }
            for w in wf_result.raw.window_results
        ],
    }
    summary["walk_forward_stage"] = {"status": "ok"}

    return summary


def format_pipeline_summary_for_ai(
    summary: dict[str, object],
    elapsed_seconds: float,
    runtime_config: dict[str, object] | None = None,
) -> str:
    """格式化管道摘要，供 CLI/AI 统一读取。"""
    lines: list[str] = []
    lines.append("=== RESEARCH_PIPELINE_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")
    if runtime_config is not None:
        lines.append(f"runtime_config={runtime_config}")
    lines.append(f"backtest={summary.get('backtest')}")
    lines.append(f"optimize={summary.get('optimize')}")
    lines.append(f"sensitivity={summary.get('sensitivity')}")
    lines.append(f"walk_forward={summary.get('walk_forward')}")
    return "\n".join(lines)
