from typing import Any
from py_entry.types import (
    OptimizationResult,
    OptimizeMetric,
    SingleParamSet,
    BacktestParams,
)
from py_entry.runner.results.report_json import dump_report


class OptimizeResult:
    """优化结果"""

    def __init__(self, raw_result: OptimizationResult):
        self._raw = raw_result

    @property
    def best_params(self) -> SingleParamSet:
        """获取最优参数集"""
        return self._raw.best_params

    @property
    def summary_table(self) -> str:
        """优化过程摘要表"""
        # This could be formatted string of history
        return str(self._raw.history)

    @property
    def raw(self) -> OptimizationResult:
        return self._raw

    @property
    def best_backtest_params(self) -> BacktestParams:
        """提取最优参数中的回测参数。"""
        return self._raw.best_params.backtest

    @property
    def total_samples(self) -> int:
        return self._raw.total_samples

    @property
    def rounds(self) -> int:
        return self._raw.rounds

    @property
    def best_metrics(self) -> dict[str, float]:
        """获取所有已计算的性能指标"""
        return self._raw.metrics

    @property
    def optimize_metric(self) -> OptimizeMetric:
        """优化目标指标类型"""
        return self._raw.optimize_metric

    @property
    def optimize_value(self) -> float:
        """优化目标最优值"""
        return self._raw.optimize_value

    def build_report(self) -> dict[str, Any]:
        """构建统一优化报告。"""
        # 中文注释：仅保留单一输出结构，不再区分 brief/detailed。
        return {
            "stage": "optimize",
            "optimize_metric": str(self.optimize_metric),
            "optimize_value": self.optimize_value,
            "optimize_total_samples": self.total_samples,
            "optimize_rounds": self.rounds,
            # 中文注释：统一透传 Rust performance 指标口径，禁止 Python 侧派生第二套字段。
            "performance": self.best_metrics,
        }

    def print_report(self) -> None:
        """打印统一优化报告。"""
        print(dump_report(self.build_report()))
