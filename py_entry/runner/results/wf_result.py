from typing import Optional, cast
from py_entry.types import (
    BacktestSummary,
    StitchedArtifact,
    WindowArtifact,
    WalkForwardResult,
    SingleParamSet,
    OptimizeMetric,
)
from py_entry.io import DisplayConfig


class WalkForwardResultWrapper:
    """向前测试结果"""

    def __init__(self, raw_result: WalkForwardResult, context: dict):
        self._raw = raw_result
        self._context = context

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
        stitched_summary = self._raw.stitched_result.summary
        return stitched_summary.performance or {}

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
    def stitched_summary(self) -> BacktestSummary:
        """拼接级回测摘要"""
        return self._raw.stitched_result.summary

    @property
    def stitched_time_range(self) -> list[int]:
        """拼接后样本外时间范围（UTC ms，[start, end]）"""
        start, end = self._raw.stitched_result.time_range
        return [start, end]

    @property
    def stitched_equity(self) -> list[float]:
        """拼接后样本外资金曲线（起点为 initial_capital）"""
        backtest_df = self._raw.stitched_result.summary.backtest_result
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
        best_id = windows[0].window_id
        best_score = float("inf") if minimize else float("-inf")
        for w in windows:
            metrics = w.summary.performance or {}
            default_score = float("inf") if minimize else float("-inf")
            score = float(metrics.get(metric_key, default_score))
            if (score < best_score) if minimize else (score > best_score):
                best_score = score
                best_id = w.window_id
        return best_id

    @property
    def worst_window_id(self) -> int:
        """测试集表现最差窗口 ID（仅返回 ID，不改变 window_results 原有时间顺序）"""
        windows = self._raw.window_results
        if not windows:
            return -1
        metric_key = self._optimize_metric_key()
        minimize = self._is_minimize_metric()
        worst_id = windows[0].window_id
        worst_score = float("-inf") if minimize else float("inf")
        for w in windows:
            metrics = w.summary.performance or {}
            default_score = float("-inf") if minimize else float("inf")
            score = float(metrics.get(metric_key, default_score))
            if (score > worst_score) if minimize else (score < worst_score):
                worst_score = score
                worst_id = w.window_id
        return worst_id

    def display(self, config: DisplayConfig | None = None):
        """显示向前测试图表"""
        pass
