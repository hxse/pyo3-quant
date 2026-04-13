from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from py_entry.runner.results.report_json import dump_report
from py_entry.runner.results.runner_session import RunnerSession
from py_entry.runner.results.single_backtest_view import SingleBacktestView
from py_entry.types import ResultPack


@dataclass(slots=True)
class BatchBacktestView:
    """batch backtest 正式集合视图。"""

    items: list[SingleBacktestView]
    session: RunnerSession

    @property
    def raw(self) -> list[ResultPack]:
        """批量结果的原始 ResultPack 列表。"""
        return [item.raw for item in self.items]

    def build_report(self) -> dict[str, Any]:
        """构建批量回测统一报告。"""
        rows: list[dict[str, Any]] = []
        for idx, item in enumerate(self.items):
            rows.append(
                {
                    "index": idx,
                    "performance": item.raw.performance or {},
                }
            )
        return {
            "stage": "batch",
            "total_results": len(self.items),
            "results": rows,
        }

    def print_report(self) -> None:
        """打印批量回测统一报告。"""
        print(dump_report(self.build_report()))
