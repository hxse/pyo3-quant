from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from py_entry.io._converters_serialization import convert_to_serializable
from py_entry.runner.params import FormatResultsConfig
from py_entry.runner.results._export_pipeline import prepare_walk_forward_export_bundle
from py_entry.runner.results.prepared_export_bundle import PreparedExportBundle
from py_entry.runner.results.report_json import dump_report
from py_entry.runner.results.runner_session import RunnerSession
from py_entry.types import (
    OptimizeMetric,
    ResultPack,
    SingleParamSet,
    StitchedArtifact,
    WindowArtifact,
    WalkForwardResult,
)


@dataclass(slots=True)
class WalkForwardView:
    """WF 正式结果视图。"""

    raw: WalkForwardResult
    session: RunnerSession

    @property
    def is_robust(self) -> bool:
        """判断 stitched 测试集是否为正收益。"""
        return self.aggregate_test_metrics.get("total_return", 0.0) > 0

    @property
    def recommended_params(self) -> Optional[SingleParamSet]:
        """推荐参数范围（预留接口，暂不实现）。"""
        return None

    @property
    def aggregate_test_metrics(self) -> dict:
        """测试集聚合指标。"""
        return self.raw.stitched_result.result.performance or {}

    @property
    def optimize_metric(self) -> OptimizeMetric:
        """优化目标指标。"""
        return self.raw.optimize_metric

    @property
    def stitched_result(self) -> StitchedArtifact:
        """拼接级完整产物。"""
        return self.raw.stitched_result

    @property
    def window_results(self) -> list[WindowArtifact]:
        """窗口级完整产物数组。"""
        return self.raw.window_results

    @property
    def stitched_pack_result(self) -> ResultPack:
        """拼接级回测结果。"""
        return self.raw.stitched_result.result

    @property
    def stitched_time_range(self) -> list[int]:
        """拼接后样本外时间范围。"""
        start, end = self.raw.stitched_result.meta.stitched_pack_time_range_from_active
        return [start, end]

    @property
    def stitched_equity(self) -> list[float]:
        """拼接后样本外资金曲线。"""
        backtest_df = self.raw.stitched_result.result.backtest_result
        if backtest_df is None:
            return []
        if "equity" not in backtest_df.columns:
            raise KeyError("stitched backtest_result 缺少 equity 列")
        return backtest_df["equity"].to_list()

    def _optimize_metric_key(self) -> str:
        """获取优化指标对应 performance 字段。"""
        return str(self.optimize_metric.as_str())

    def _is_minimize_metric(self) -> bool:
        """判断优化目标是否越小越优。"""
        return self._optimize_metric_key() in {"max_drawdown"}

    @property
    def best_window_id(self) -> int:
        """测试集表现最优窗口 ID。"""
        windows = self.raw.window_results
        if not windows:
            return -1
        metric_key = self._optimize_metric_key()
        minimize = self._is_minimize_metric()
        best_id = windows[0].meta.window_id
        best_score = float("inf") if minimize else float("-inf")
        for window in windows:
            metrics = window.test_pack_result.performance or {}
            default_score = float("inf") if minimize else float("-inf")
            score = float(metrics.get(metric_key, default_score))
            if (score < best_score) if minimize else (score > best_score):
                best_score = score
                best_id = window.meta.window_id
        return best_id

    @property
    def worst_window_id(self) -> int:
        """测试集表现最差窗口 ID。"""
        windows = self.raw.window_results
        if not windows:
            return -1
        metric_key = self._optimize_metric_key()
        minimize = self._is_minimize_metric()
        worst_id = windows[0].meta.window_id
        worst_score = float("-inf") if minimize else float("inf")
        for window in windows:
            metrics = window.test_pack_result.performance or {}
            default_score = float("-inf") if minimize else float("inf")
            score = float(metrics.get(metric_key, default_score))
            if (score > worst_score) if minimize else (score < worst_score):
                worst_score = score
                worst_id = window.meta.window_id
        return worst_id

    def prepare_export(self, config: FormatResultsConfig) -> PreparedExportBundle:
        """生成 WF stitched 正式导出 bundle。"""
        return prepare_walk_forward_export_bundle(
            session=self.session,
            stitched_data=self.stitched_result.stitched_data,
            stitched_result=self.stitched_pack_result,
            backtest_schedule=list(self.stitched_result.meta.backtest_schedule),
            config=config,
        )

    def build_report(self) -> dict[str, Any]:
        """构建统一向前测试报告。"""
        windows = [
            {
                "window_id": window.meta.window_id,
                "test_active_base_row_range": window.meta.test_active_base_row_range,
                "train_warmup_time_range_ms": (
                    list(window.meta.train_warmup_time_range)
                    if window.meta.train_warmup_time_range is not None
                    else None
                ),
                "train_active_time_range_ms": list(window.meta.train_active_time_range),
                "train_pack_time_range_ms": list(window.meta.train_pack_time_range),
                "test_warmup_time_range_ms": list(window.meta.test_warmup_time_range),
                "test_active_time_range_ms": list(window.meta.test_active_time_range),
                "test_pack_time_range_ms": list(window.meta.test_pack_time_range),
                "has_cross_boundary_position": window.meta.has_cross_boundary_position,
                "test_metrics": window.test_pack_result.performance or {},
            }
            for window in self.window_results
        ]
        return {
            "stage": "walk_forward",
            "optimize_metric": self.optimize_metric.as_str(),
            "performance": self.aggregate_test_metrics,
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
