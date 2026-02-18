"""private_strategies 通用阶段执行工具。"""

from typing import Any

from py_entry.private_strategies.live.base import LiveStrategyConfig
from py_entry.runner import Backtest, FormatResultsConfig, RunResult
from py_entry.types import OptimizerConfig, SensitivityConfig, WalkForwardConfig


# 中文注释：统一构建 Backtest，避免策略文件重复样板代码。
def build_backtest(config: LiveStrategyConfig) -> Backtest:
    cfg = config.strategy
    return Backtest(
        enable_timing=True,
        data_source=cfg.data_config,
        indicators=cfg.indicators_params,
        signal=cfg.signal_params,
        backtest=cfg.backtest_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
        performance=cfg.performance_params,
    )


# 中文注释：统一序列化 Rust 的统计对象，输出纯数值字典给 AI。
def serialize_metric_stats(
    metric_stats: dict[str, object],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key, stats in metric_stats.items():
        out[key] = {
            "mean": float(getattr(stats, "mean", 0.0)),
            "median": float(getattr(stats, "median", 0.0)),
            "std": float(getattr(stats, "std", 0.0)),
            "min": float(getattr(stats, "min", 0.0)),
            "max": float(getattr(stats, "max", 0.0)),
            "p05": float(getattr(stats, "p05", 0.0)),
            "p95": float(getattr(stats, "p95", 0.0)),
        }
    return out


def run_backtest_stage(config: LiveStrategyConfig) -> RunResult:
    bt = build_backtest(config)
    return bt.run().format_for_export(FormatResultsConfig(dataframe_format="csv"))


def run_optimization_stage(config: LiveStrategyConfig, opt_cfg: OptimizerConfig):
    bt = build_backtest(config)
    return bt.optimize(opt_cfg)


def run_sensitivity_stage(config: LiveStrategyConfig, sens_cfg: SensitivityConfig):
    bt = build_backtest(config)
    return bt.sensitivity(sens_cfg)


def run_walk_forward_stage(config: LiveStrategyConfig, wf_cfg: WalkForwardConfig):
    bt = build_backtest(config)
    return bt.walk_forward(wf_cfg)


# 中文注释：提取优化后的少量关键参数，避免输出全量参数树。
def extract_optimize_key_params(
    opt_result: Any, base_data_key: str
) -> dict[str, object]:
    summary: dict[str, object] = {}

    indicators = getattr(opt_result.best_params, "indicators", {})
    indicator_group = (
        indicators.get(base_data_key, {}) if isinstance(indicators, dict) else {}
    )

    fast = (
        indicator_group.get("sma_fast", {}) if isinstance(indicator_group, dict) else {}
    )
    slow = (
        indicator_group.get("sma_slow", {}) if isinstance(indicator_group, dict) else {}
    )

    fast_period = fast.get("period") if isinstance(fast, dict) else None
    slow_period = slow.get("period") if isinstance(slow, dict) else None

    summary["sma_fast"] = getattr(fast_period, "value", fast_period)
    summary["sma_slow"] = getattr(slow_period, "value", slow_period)

    for key in ("sl_pct", "tp_pct", "tsl_pct"):
        param_obj = getattr(opt_result.best_backtest_params, key, None)
        summary[key] = getattr(param_obj, "value", param_obj)

    return summary


def run_pipeline(
    config: LiveStrategyConfig,
    *,
    base_data_key: str,
    opt_cfg: OptimizerConfig,
    sens_cfg: SensitivityConfig,
    wf_cfg: WalkForwardConfig,
) -> dict[str, object]:
    # 中文注释：非交互式顺序执行全部阶段，避免 CLI 阶段 input 阻塞。
    summary: dict[str, object] = {
        "backtest": None,
        "optimize": None,
        "sensitivity": None,
        "walk_forward": None,
    }

    backtest_result = run_backtest_stage(config)
    summary["backtest"] = (
        backtest_result.summary.performance if backtest_result.summary else None
    )
    summary["backtest_stage"] = {"status": "ok"}

    opt_result = run_optimization_stage(config, opt_cfg)
    summary["optimize"] = {
        "metric": str(opt_result.optimize_metric),
        "value": opt_result.optimize_value,
        "samples": opt_result.total_samples,
        "rounds": opt_result.rounds,
        "best_params": extract_optimize_key_params(opt_result, base_data_key),
    }
    summary["optimize_stage"] = {"status": "ok"}

    sens_result = run_sensitivity_stage(config, sens_cfg)
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
        # 中文注释：只抽取极值样本的核心字段供 AI 快速诊断，不做二次统计。
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

    wf_result = run_walk_forward_stage(config, wf_cfg)
    summary["walk_forward"] = {
        "optimize_metric": str(wf_result.optimize_metric),
        "aggregate_test_metrics": wf_result.aggregate_test_metrics,
        "window_metric_stats": serialize_metric_stats(wf_result.window_metric_stats),
        "best_window_id": wf_result.best_window_id,
        "worst_window_id": wf_result.worst_window_id,
        "stitched_points": len(wf_result.stitched_time),
        "window_best_params": [
            {
                "window_id": w.window_id,
                "train_range": w.train_range,
                "transition_range": w.transition_range,
                "test_range": w.test_range,
                "best_params": str(w.best_params),
            }
            for w in wf_result.raw.windows
        ],
    }
    summary["walk_forward_stage"] = {"status": "ok"}

    return summary


def format_pipeline_summary_for_ai(
    summary: dict[str, object],
    elapsed_seconds: float,
    runtime_config: dict[str, object] | None = None,
    runtime_thresholds: dict[str, object] | None = None,
) -> str:
    lines: list[str] = []
    lines.append("=== RESEARCH_PIPELINE_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")
    if runtime_config is not None:
        lines.append(f"runtime_config={runtime_config}")
    if runtime_thresholds is not None:
        lines.append(f"runtime_thresholds={runtime_thresholds}")
    lines.append(f"backtest={summary.get('backtest')}")
    lines.append(f"optimize={summary.get('optimize')}")
    lines.append(f"sensitivity={summary.get('sensitivity')}")
    lines.append(f"walk_forward={summary.get('walk_forward')}")
    return "\n".join(lines)
