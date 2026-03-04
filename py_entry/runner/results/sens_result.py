from __future__ import annotations

from typing import Any

from py_entry.types import SensitivityResult
from py_entry.runner.results.report_json import dump_report


class SensitivityResultWrapper:
    """参数抖动结果包装器。"""

    def __init__(self, raw_result: SensitivityResult):
        self._raw = raw_result

    @property
    def raw(self) -> SensitivityResult:
        return self._raw

    def __getattr__(self, item: str) -> Any:
        """透传 Rust 原始对象属性。"""
        return getattr(self._raw, item)

    def build_report(self) -> dict[str, Any]:
        """构建统一参数抖动报告。"""
        # 中文注释：统一用 Rust 指标字段作为唯一口径，不再保留分级日志。
        return {
            "stage": "sensitivity",
            "meta": {
                "target_metric": str(self._raw.target_metric),
                "total_samples_requested": self._raw.total_samples_requested,
                "successful_samples": self._raw.successful_samples,
                "failed_samples": self._raw.failed_samples,
            },
            "performance": {
                "original_value": self._raw.original_value,
                "failed_sample_rate": self._raw.failed_sample_rate,
                "mean": self._raw.mean,
                "std": self._raw.std,
                "p05": self._raw.p05,
                "p25": self._raw.p25,
                "median": self._raw.median,
                "p75": self._raw.p75,
                "p95": self._raw.p95,
                "min": self._raw.min,
                "max": self._raw.max,
                "cv": self._raw.cv,
            },
        }

    def print_report(self) -> None:
        """打印统一参数抖动报告。"""
        print(dump_report(self.build_report()))
