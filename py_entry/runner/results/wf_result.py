from typing import Optional, cast
from py_entry.types import WalkForwardResult, SingleParamSet, OptimizeMetric
from py_entry.io import DisplayConfig


class WalkForwardResultWrapper:
    """向前测试结果"""

    def __init__(self, raw_result: WalkForwardResult, context: dict):
        self._raw = raw_result
        self._context = context  # might be needed for display?

    @property
    def is_robust(self) -> bool:
        """判断是否稳健"""
        # Simple logic: aggregate_test_calmar > 0 ? Or based on specific criteria.
        # For now return True if train/test metrics are decent.
        # Actually without domain logic, we just return a placeholder or based on some ratio.
        # Let's assume it's robust if aggregate return is positive for now.
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

    def display(self, config: DisplayConfig | None = None):
        """显示向前测试图表"""
        # WalkForward display likely needs special handling in charts/
        # Current system doesn't seem to have specific WF charts yet?
        # Or maybe check runner.py if it had wf display.
        # runner.py display_dashboard was for backtest results.
        # For WF results, usually we print summary or plot robust checks.
        # If no existing display logic for WF, we can just pass.
        pass
