from __future__ import annotations

from typing import Any

from py_entry.runner.results.log_level import LogLevel
from py_entry.types import SensitivityResult


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

    def log(self, level: LogLevel = LogLevel.BRIEF) -> None:
        """打印参数抖动摘要日志。"""
        if level == LogLevel.BRIEF:
            out = {
                "target_metric": str(self._raw.target_metric),
                "original_value": self._raw.original_value,
                "mean": self._raw.mean,
                "std": self._raw.std,
                "cv": self._raw.cv,
            }
            print(f"sensitivity.brief={out}")
            return
        out = {
            "target_metric": str(self._raw.target_metric),
            "original_value": self._raw.original_value,
            "total_samples_requested": self._raw.total_samples_requested,
            "successful_samples": self._raw.successful_samples,
            "failed_samples": self._raw.failed_samples,
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
        }
        print(f"sensitivity.detailed={out}")
