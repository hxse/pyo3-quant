from typing import Optional, cast
from py_entry.types import (
    WalkForwardResult,
    SingleParamSet,
    OptimizeMetric,
    MetricDistributionStats,
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
        return self._raw.aggregate_test_metrics.get("total_return", 0.0) > 0

    @property
    def recommended_params(self) -> Optional[SingleParamSet]:
        """推荐参数范围（预留接口，暂不实现）"""
        return None

    @property
    def aggregate_test_metrics(self) -> dict:
        """测试集聚合指标"""
        return self._raw.aggregate_test_metrics

    @property
    def optimize_metric(self) -> OptimizeMetric:
        """优化目标指标类型"""
        # Rust 侧已返回枚举实例，这里直接透传，避免重复构造导致 TypeError。
        return cast(OptimizeMetric, self._raw.optimize_metric)

    @property
    def raw(self) -> WalkForwardResult:
        return self._raw

    @property
    def window_metric_stats(self) -> dict[str, MetricDistributionStats]:
        """窗口级测试指标分布统计"""
        return self._raw.window_metric_stats

    @property
    def stitched_time(self) -> list[int]:
        """拼接后样本外时间轴（UTC ms）"""
        return self._raw.stitched_time

    @property
    def stitched_equity(self) -> list[float]:
        """拼接后样本外资金曲线（起点固定 1.0）"""
        return self._raw.stitched_equity

    @property
    def best_window_id(self) -> int:
        """测试集表现最优窗口 ID"""
        return self._raw.best_window_id

    @property
    def worst_window_id(self) -> int:
        """测试集表现最差窗口 ID"""
        return self._raw.worst_window_id

    def display(self, config: DisplayConfig | None = None):
        """显示向前测试图表"""
        pass
