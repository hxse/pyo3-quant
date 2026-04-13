from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from py_entry.runner.results.report_json import dump_report
from py_entry.runner.results.runner_session import RunnerSession
from py_entry.types import SensitivityResult


@dataclass(slots=True)
class SensitivityView:
    """参数敏感性正式视图。"""

    raw: SensitivityResult
    session: RunnerSession

    @property
    def target_metric(self):
        """目标指标。"""
        return self.raw.target_metric

    @property
    def samples(self):
        """采样结果数组。"""
        return self.raw.samples

    @property
    def total_samples_requested(self) -> int:
        """请求采样数。"""
        return self.raw.total_samples_requested

    @property
    def successful_samples(self) -> int:
        """成功采样数。"""
        return self.raw.successful_samples

    @property
    def failed_samples(self) -> int:
        """失败采样数。"""
        return self.raw.failed_samples

    @property
    def original_value(self) -> float:
        """基准值。"""
        return self.raw.original_value

    @property
    def failed_sample_rate(self) -> float:
        """失败率。"""
        return self.raw.failed_sample_rate

    @property
    def mean(self) -> float:
        """均值。"""
        return self.raw.mean

    @property
    def std(self) -> float:
        """标准差。"""
        return self.raw.std

    @property
    def p05(self) -> float:
        """5 分位。"""
        return self.raw.p05

    @property
    def p25(self) -> float:
        """25 分位。"""
        return self.raw.p25

    @property
    def median(self) -> float:
        """中位数。"""
        return self.raw.median

    @property
    def p75(self) -> float:
        """75 分位。"""
        return self.raw.p75

    @property
    def p95(self) -> float:
        """95 分位。"""
        return self.raw.p95

    @property
    def min(self) -> float:
        """最小值。"""
        return self.raw.min

    @property
    def max(self) -> float:
        """最大值。"""
        return self.raw.max

    @property
    def cv(self) -> float:
        """变异系数。"""
        return self.raw.cv

    def build_report(self) -> dict[str, Any]:
        """构建统一参数抖动报告。"""
        return {
            "stage": "sensitivity",
            "meta": {
                "target_metric": str(self.target_metric),
                "total_samples_requested": self.total_samples_requested,
                "successful_samples": self.successful_samples,
                "failed_samples": self.failed_samples,
            },
            "performance": {
                "original_value": self.original_value,
                "failed_sample_rate": self.failed_sample_rate,
                "mean": self.mean,
                "std": self.std,
                "p05": self.p05,
                "p25": self.p25,
                "median": self.median,
                "p75": self.p75,
                "p95": self.p95,
                "min": self.min,
                "max": self.max,
                "cv": self.cv,
            },
        }

    def print_report(self) -> None:
        """打印统一参数抖动报告。"""
        print(dump_report(self.build_report()))
