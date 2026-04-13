from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from py_entry.runner.results.report_json import dump_report
from py_entry.runner.results.runner_session import RunnerSession
from py_entry.types import (
    BacktestParams,
    OptimizationResult,
    OptimizeMetric,
    SingleParamSet,
)


@dataclass(slots=True)
class OptimizationView:
    """优化结果正式视图。"""

    raw: OptimizationResult
    session: RunnerSession

    @property
    def best_params(self) -> SingleParamSet:
        """最优参数集。"""
        return self.raw.best_params

    @property
    def summary_table(self) -> str:
        """优化过程摘要表。"""
        return str(self.raw.history)

    @property
    def best_backtest_params(self) -> BacktestParams:
        """最优回测参数。"""
        return self.raw.best_params.backtest

    @property
    def total_samples(self) -> int:
        """采样总数。"""
        return self.raw.total_samples

    @property
    def rounds(self) -> int:
        """轮数。"""
        return self.raw.rounds

    @property
    def best_metrics(self) -> dict[str, float]:
        """最优 performance 指标集合。"""
        return self.raw.metrics

    @property
    def optimize_metric(self) -> OptimizeMetric:
        """优化目标指标。"""
        return self.raw.optimize_metric

    @property
    def optimize_value(self) -> float:
        """最优目标值。"""
        return self.raw.optimize_value

    def build_report(self) -> dict[str, Any]:
        """构建统一优化报告。"""
        return {
            "stage": "optimize",
            "optimize_metric": str(self.optimize_metric),
            "optimize_value": self.optimize_value,
            "optimize_total_samples": self.total_samples,
            "optimize_rounds": self.rounds,
            "performance": self.best_metrics,
        }

    def print_report(self) -> None:
        """打印统一优化报告。"""
        print(dump_report(self.build_report()))
