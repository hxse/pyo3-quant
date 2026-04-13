"""searcher 结果序列化与提取。"""

from __future__ import annotations

from typing import Any


def safe_attr(obj: Any, name: str) -> Any:
    """安全读取属性。"""

    try:
        return getattr(obj, name)
    except (AttributeError, KeyError):
        return None


def default_backtest_time_info() -> dict[str, Any]:
    """返回默认回测时间占位字段。"""

    return {
        "backtest_start_time_ms": None,
        "backtest_end_time_ms": None,
        "backtest_span_ms": None,
    }


def _serialize_leaf(value: Any) -> Any:
    """序列化 Param 等对象为基础类型。"""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    param_value = safe_attr(value, "value")
    if isinstance(param_value, (bool, int, float, str)):
        return param_value
    if isinstance(value, dict):
        return {str(k): _serialize_leaf(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_leaf(v) for v in value]
    return str(value)


def _serialize_backtest_params(backtest: Any) -> dict[str, Any]:
    """序列化 BacktestParams。"""

    if backtest is None:
        return {}
    out: dict[str, Any] = {}
    names = list(getattr(backtest, "__dict__", {}).keys())
    if not names:
        # 中文注释：PyO3 对象可能没有 __dict__，此时改为枚举 dir()。
        names = dir(backtest)
    for name in names:
        if name.startswith("_"):
            continue
        value = safe_attr(backtest, name)
        if callable(value):
            continue
        out[name] = _serialize_leaf(value)
    return out


def serialize_single_param_set(param_set: Any) -> dict[str, Any]:
    """序列化 SingleParamSet。"""

    if param_set is None:
        return {"indicators": {}, "signal": {}, "backtest": {}}
    return {
        "indicators": _serialize_leaf(safe_attr(param_set, "indicators")) or {},
        "signal": _serialize_leaf(safe_attr(param_set, "signal")) or {},
        "backtest": _serialize_backtest_params(safe_attr(param_set, "backtest")),
    }


def _extract_base_times_ms(result_view: Any) -> list[int]:
    """提取基准周期时间序列。"""

    base_key = result_view.session.data_pack.base_data_key
    base_df = result_view.session.data_pack.source[base_key]
    return [int(x) for x in base_df["time"].to_list()]


def extract_backtest_time_info(result_view: Any) -> dict[str, Any]:
    """提取默认回测时间信息。"""

    times = _extract_base_times_ms(result_view)
    if not times:
        return default_backtest_time_info()
    start_time_ms = int(times[0])
    end_time_ms = int(times[-1])
    return {
        "backtest_start_time_ms": start_time_ms,
        "backtest_end_time_ms": end_time_ms,
        "backtest_span_ms": int(end_time_ms - start_time_ms),
    }


def extract_wf_window_logs(
    wf_result: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """提取 WF 每窗口日志与最后窗口参数。"""

    windows: list[dict[str, Any]] = []
    last_window_start_time_ms: int | None = None
    last_window_best_params: dict[str, Any] | None = None

    for window in wf_result.raw.window_results:
        meta = window.meta
        row = {
            "window_id": int(meta.window_id),
            "test_active_base_row_range": list(meta.test_active_base_row_range),
            "train_warmup_time_range_ms": (
                [
                    int(meta.train_warmup_time_range[0]),
                    int(meta.train_warmup_time_range[1]),
                ]
                if meta.train_warmup_time_range is not None
                else None
            ),
            "train_active_time_range_ms": [
                int(meta.train_active_time_range[0]),
                int(meta.train_active_time_range[1]),
            ],
            "train_pack_time_range_ms": [
                int(meta.train_pack_time_range[0]),
                int(meta.train_pack_time_range[1]),
            ],
            "test_warmup_time_range_ms": [
                int(meta.test_warmup_time_range[0]),
                int(meta.test_warmup_time_range[1]),
            ],
            "test_active_time_range_ms": [
                int(meta.test_active_time_range[0]),
                int(meta.test_active_time_range[1]),
            ],
            "test_pack_time_range_ms": [
                int(meta.test_pack_time_range[0]),
                int(meta.test_pack_time_range[1]),
            ],
            "best_params": serialize_single_param_set(meta.best_params),
            "has_cross_boundary_position": bool(meta.has_cross_boundary_position),
            "test_metrics": window.test_pack_result.performance or {},
        }
        windows.append(row)
        last_window_start_time_ms = int(meta.test_active_time_range[0])
        last_window_best_params = row["best_params"]

    return windows, {
        "last_window_start_time_ms": last_window_start_time_ms,
        "last_window_best_params": last_window_best_params,
    }


def extract_optimize_info(opt_result: Any) -> dict[str, Any]:
    """提取优化结果信息。"""

    return {
        "performance": opt_result.best_metrics,
        "optimize_best_params": serialize_single_param_set(opt_result.best_params),
        "optimize_metric": opt_result.optimize_metric.as_str(),
        "optimize_value": float(opt_result.optimize_value),
        "optimize_total_samples": int(opt_result.total_samples),
        "optimize_rounds": int(opt_result.rounds),
    }


def extract_sensitivity_info(sens_result: Any) -> dict[str, Any]:
    """提取参数抖动结果信息。"""

    return {
        "sensitivity_meta": {
            "target_metric": str(sens_result.target_metric),
            "total_samples_requested": int(sens_result.total_samples_requested),
            "successful_samples": int(sens_result.successful_samples),
            "failed_samples": int(sens_result.failed_samples),
        },
        "performance": {
            "original_value": float(sens_result.original_value),
            "mean": float(sens_result.mean),
            "std": float(sens_result.std),
            "cv": float(sens_result.cv),
            "p05": float(sens_result.p05),
            "p25": float(sens_result.p25),
            "median": float(sens_result.median),
            "p75": float(sens_result.p75),
            "p95": float(sens_result.p95),
            "min": float(sens_result.min),
            "max": float(sens_result.max),
            "failed_sample_rate": float(sens_result.failed_sample_rate),
        },
    }
