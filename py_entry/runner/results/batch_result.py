from typing import List, TYPE_CHECKING
from py_entry.types import BacktestSummary, SingleParamSet

if TYPE_CHECKING:
    from .run_result import RunResult
    # Context types if needed


class BatchResult:
    """批量回测结果"""

    def __init__(
        self,
        summaries: List[BacktestSummary],
        param_list: List[SingleParamSet],
        context: dict,  # data_dict, template_config, engine_settings
    ):
        self.summaries = summaries
        self.param_list = param_list
        self.context = context

    def select(self, index: int = 0) -> "RunResult":
        """选择一个结果转为 RunResult"""
        from .run_result import RunResult

        if index < 0 or index >= len(self.summaries):
            raise IndexError(
                f"Index {index} out of range (0-{len(self.summaries) - 1})"
            )

        return RunResult(
            summary=self.summaries[index],
            params=self.param_list[index],
            data_dict=self.context["data_dict"],
            template_config=self.context["template_config"],
            engine_settings=self.context["engine_settings"],
            enable_timing=self.context.get("enable_timing", False),
        )

    def best_by(self, metric: str = "calmar_ratio") -> "RunResult":
        """按指标选择最优结果"""
        # Simple implementation
        if not self.summaries:
            raise ValueError("No results in batch")

        # Inspect first result to see structure. BacktestSummary.performance is PerformanceMetrics
        # PerformanceMetrics has attributes like total_return, max_drawdown, etc.
        # metric should be an attribute name string.

        # Use max() with key to find the best index
        best_idx = max(
            range(len(self.summaries)),
            key=lambda i: getattr(self.summaries[i].performance, metric, -float("inf")),
        )

        return self.select(best_idx)
