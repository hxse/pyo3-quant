from typing import Dict, Any
from py_entry.types import (
    OptimizationResult,
    OptimizeMetric,
    SingleParamSet,
    BacktestParams,
)
# To convert dict params to SingleParamSet, we might need helper builders
# But SingleParamSet expects Pydantic models.
# OptimizationResult.best_params is a dict.
# We probably need to reconstruct SingleParamSet from the initial SetupConfig structure
# but injecting the best values.
# For now, let's just expose best_params as dict, same as current impl,
# or try to keep it simple. The user request draft code showed:
# opt.best_params (which they printed).


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
        # Backtest params are now within best_params.backtest
        return self._raw.best_params.backtest

    @property
    def total_samples(self) -> int:
        return self._raw.total_samples

    @property
    def rounds(self) -> int:
        return self._raw.rounds

    @property
    def best_metrics(self) -> Dict[str, float]:
        """获取所有已计算的性能指标"""
        return self._raw.metrics

    @property
    def optimize_metric(self) -> OptimizeMetric:
        """优化目标指标类型"""
        # Convert string back to Enum
        return OptimizeMetric(self._raw.optimize_metric)

    @property
    def optimize_value(self) -> float:
        """优化目标最优值"""
        return self._raw.optimize_value
