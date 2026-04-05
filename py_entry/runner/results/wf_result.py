from typing import TYPE_CHECKING, Any, Optional, Self, cast
from py_entry.types import (
    DataPack,
    ResultPack,
    StitchedArtifact,
    WindowArtifact,
    WalkForwardResult,
    SingleParamSet,
    OptimizeMetric,
)
from py_entry.io import DisplayConfig
from py_entry.io._converters_serialization import convert_to_serializable
from py_entry.runner.results.report_json import dump_report

if TYPE_CHECKING:
    from py_entry.runner import FormatResultsConfig
    from py_entry.runner.results.run_result import RunResult
    from py_entry.io import SaveConfig, UploadConfig


class WalkForwardResultWrapper:
    """向前测试结果"""

    def __init__(self, raw_result: WalkForwardResult, context: dict):
        self._raw = raw_result
        self._context = context
        self._stitched_run_result: "RunResult | None" = None

    @property
    def is_robust(self) -> bool:
        """判断是否稳健"""
        metrics = self.aggregate_test_metrics
        return metrics.get("total_return", 0.0) > 0

    @property
    def recommended_params(self) -> Optional[SingleParamSet]:
        """推荐参数范围（预留接口，暂不实现）"""
        return None

    @property
    def aggregate_test_metrics(self) -> dict:
        """测试集聚合指标"""
        return self._raw.stitched_result.result.performance or {}

    @property
    def optimize_metric(self) -> OptimizeMetric:
        """优化目标指标类型"""
        # Rust 侧已返回枚举实例，这里直接透传，避免重复构造导致 TypeError。
        return cast(OptimizeMetric, self._raw.optimize_metric)

    @property
    def raw(self) -> WalkForwardResult:
        return self._raw

    @property
    def stitched_result(self) -> StitchedArtifact:
        """拼接级完整产物"""
        return self._raw.stitched_result

    @property
    def window_results(self) -> list[WindowArtifact]:
        """窗口级完整产物数组"""
        return self._raw.window_results

    @property
    def stitched_pack_result(self) -> ResultPack:
        """拼接级回测结果。"""
        return self._raw.stitched_result.result

    @property
    def stitched_time_range(self) -> list[int]:
        """拼接后样本外时间范围（UTC ms，[start, end]）"""
        start, end = self._raw.stitched_result.meta.stitched_pack_time_range_from_active
        return [start, end]

    @property
    def stitched_equity(self) -> list[float]:
        """拼接后样本外资金曲线（起点为 initial_capital）"""
        backtest_df = self._raw.stitched_result.result.backtest_result
        if backtest_df is None:
            return []
        try:
            return backtest_df["equity"].to_list()
        except Exception:
            return []

    def _optimize_metric_key(self) -> str:
        """获取优化指标对应的 performance 字段键名"""
        return str(self.optimize_metric.as_str())

    def _is_minimize_metric(self) -> bool:
        """判断该优化指标是否是越小越优"""
        return self._optimize_metric_key() in {"max_drawdown"}

    @property
    def best_window_id(self) -> int:
        """测试集表现最优窗口 ID（仅返回 ID，不改变 window_results 原有时间顺序）"""
        windows = self._raw.window_results
        if not windows:
            return -1
        metric_key = self._optimize_metric_key()
        minimize = self._is_minimize_metric()
        best_id = windows[0].meta.window_id
        best_score = float("inf") if minimize else float("-inf")
        for w in windows:
            metrics = w.test_pack_result.performance or {}
            default_score = float("inf") if minimize else float("-inf")
            score = float(metrics.get(metric_key, default_score))
            if (score < best_score) if minimize else (score > best_score):
                best_score = score
                best_id = w.meta.window_id
        return best_id

    @property
    def worst_window_id(self) -> int:
        """测试集表现最差窗口 ID（仅返回 ID，不改变 window_results 原有时间顺序）"""
        windows = self._raw.window_results
        if not windows:
            return -1
        metric_key = self._optimize_metric_key()
        minimize = self._is_minimize_metric()
        worst_id = windows[0].meta.window_id
        worst_score = float("-inf") if minimize else float("inf")
        for w in windows:
            metrics = w.test_pack_result.performance or {}
            default_score = float("-inf") if minimize else float("inf")
            score = float(metrics.get(metric_key, default_score))
            if (score > worst_score) if minimize else (score < worst_score):
                worst_score = score
                worst_id = w.meta.window_id
        return worst_id

    def display(self, config: DisplayConfig | None = None):
        """显示向前测试图表"""
        return self.run_result.display(config=config)

    def _build_stitched_run_result(self) -> "RunResult":
        """构建 stitched 对应的 RunResult（不做格式化）。"""
        from py_entry.runner.results.run_result import RunResult

        windows = self.window_results
        if not windows:
            raise ValueError("window_results 为空，无法构建 stitched RunResult。")
        best_id = self.best_window_id
        target_window = next(
            (w for w in windows if w.meta.window_id == best_id),
            windows[0],
        )
        return RunResult(
            result=self.stitched_pack_result,
            params=target_window.meta.best_params,
            export_params=None,
            backtest_schedule=list(self.stitched_result.meta.backtest_schedule),
            data_pack=self.stitched_result.stitched_data,
            template_config=self._context["template_config"],
            engine_settings=self._context["engine_settings"],
            enable_timing=self._context.get("enable_timing", False),
        )

    def _ensure_stitched_run_result(self) -> "RunResult":
        """获取 stitched RunResult，不存在则按当前口径惰性构建。"""
        if self._stitched_run_result is None:
            self._stitched_run_result = self._build_stitched_run_result()
        return self._stitched_run_result

    @property
    def run_result(self) -> "RunResult":
        """获取 stitched 结果对应的 RunResult 代理。"""
        return self._ensure_stitched_run_result()

    @property
    def chart_config(self):
        """透传 stitched RunResult 的 chart_config。"""
        return self.run_result.chart_config

    @property
    def export_buffers(self):
        """透传 stitched RunResult 的导出 buffers。"""
        return self.run_result.export_buffers

    @property
    def export_zip_buffer(self):
        """透传 stitched RunResult 的 ZIP 导出缓存。"""
        return self.run_result.export_zip_buffer

    def format_for_export(self, config: "FormatResultsConfig") -> Self:
        """按显式配置格式化 stitched 结果，行为与 RunResult 保持一致。"""
        self.run_result.format_for_export(config)
        return self

    def save(self, config: "SaveConfig") -> Self:
        """透传 stitched RunResult 的保存能力。"""
        self.run_result.save(config)
        return self

    def upload(self, config: "UploadConfig") -> Self:
        """透传 stitched RunResult 的上传能力。"""
        self.run_result.upload(config)
        return self

    def build_report(self) -> dict[str, Any]:
        """构建统一向前测试报告。"""
        agg = self.aggregate_test_metrics
        # 中文注释：统一只保留一套完整口径，避免 brief/detailed 双轨并存。
        windows = [
            {
                "window_id": w.meta.window_id,
                "test_active_base_row_range": w.meta.test_active_base_row_range,
                "train_warmup_time_range_ms": (
                    list(w.meta.train_warmup_time_range)
                    if w.meta.train_warmup_time_range is not None
                    else None
                ),
                "train_active_time_range_ms": list(w.meta.train_active_time_range),
                "train_pack_time_range_ms": list(w.meta.train_pack_time_range),
                "test_warmup_time_range_ms": list(w.meta.test_warmup_time_range),
                "test_active_time_range_ms": list(w.meta.test_active_time_range),
                "test_pack_time_range_ms": list(w.meta.test_pack_time_range),
                "has_cross_boundary_position": w.meta.has_cross_boundary_position,
                "test_metrics": w.test_pack_result.performance or {},
            }
            for w in self.window_results
        ]
        return {
            "stage": "walk_forward",
            "optimize_metric": self.optimize_metric.as_str(),
            "performance": agg,
            "best_window_id": self.best_window_id,
            "worst_window_id": self.worst_window_id,
            "stitched_time_range": self.stitched_time_range,
            "next_window_hint": {
                "expected_window_switch_time_ms": self.stitched_result.meta.next_window_hint.expected_window_switch_time_ms,
                "eta_days": self.stitched_result.meta.next_window_hint.eta_days,
                "based_on_window_id": self.stitched_result.meta.next_window_hint.based_on_window_id,
            },
            "backtest_schedule": [
                {
                    "start_row": segment.start_row,
                    "end_row": segment.end_row,
                    "params": {
                        "backtest": convert_to_serializable(segment.params),
                    },
                }
                for segment in self.stitched_result.meta.backtest_schedule
            ],
            "windows": windows,
        }

    def print_report(self) -> None:
        """打印统一向前测试报告。"""
        print(dump_report(self.build_report()))
