from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from py_entry.runner.params import FormatResultsConfig
from py_entry.runner.results._export_pipeline import prepare_single_export_bundle
from py_entry.runner.results.prepared_export_bundle import PreparedExportBundle
from py_entry.runner.results.report_json import dump_report
from py_entry.runner.results.runner_session import RunnerSession
from py_entry.types import ResultPack, SingleParamSet


@dataclass(slots=True)
class SingleBacktestView:
    """single backtest 正式结果视图。"""

    raw: ResultPack
    params: SingleParamSet
    session: RunnerSession

    def prepare_export(self, config: FormatResultsConfig) -> PreparedExportBundle:
        """生成 single backtest 正式导出 bundle。"""
        return prepare_single_export_bundle(
            session=self.session,
            result=self.raw,
            params=self.params,
            config=config,
        )

    def build_report(self) -> dict[str, Any]:
        """构建统一回测报告。"""
        return {
            "stage": "backtest",
            "performance": self.raw.performance or {},
        }

    def print_report(self) -> None:
        """打印统一回测报告。"""
        print(dump_report(self.build_report()))
