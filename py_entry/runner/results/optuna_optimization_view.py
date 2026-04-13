from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from py_entry.runner.results.report_json import dump_report
from py_entry.runner.results.runner_session import RunnerSession


@dataclass(slots=True)
class OptunaOptimizationRaw:
    """Optuna 优化原始结果快照。"""

    best_params: dict[str, Any]
    best_signal_params: dict[str, Any]
    best_backtest_params: dict[str, Any]
    best_value: float
    n_trials: int
    history: list[dict[str, Any]] = field(default_factory=list)
    study: Any | None = None


@dataclass(slots=True)
class OptunaOptimizationView:
    """Optuna 优化正式视图。"""

    raw: OptunaOptimizationRaw
    session: RunnerSession

    @property
    def best_params(self) -> dict[str, Any]:
        """最优指标参数。"""
        return self.raw.best_params

    @property
    def best_signal_params(self) -> dict[str, Any]:
        """最优信号参数。"""
        return self.raw.best_signal_params

    @property
    def best_backtest_params(self) -> dict[str, Any]:
        """最优回测参数。"""
        return self.raw.best_backtest_params

    @property
    def best_value(self) -> float:
        """最优目标值。"""
        return self.raw.best_value

    @property
    def n_trials(self) -> int:
        """试验总数。"""
        return self.raw.n_trials

    @property
    def history(self) -> list[dict[str, Any]]:
        """优化历史。"""
        return self.raw.history

    @property
    def study(self) -> Any | None:
        """Optuna study。"""
        return self.raw.study

    def build_report(self) -> dict[str, Any]:
        """构建统一 Optuna 优化报告。"""
        return {
            "stage": "optuna_optimize",
            "best_value": self.best_value,
            "n_trials": self.n_trials,
            "best_params": self.best_params,
            "best_signal_params": self.best_signal_params,
            "best_backtest_params": self.best_backtest_params,
        }

    def print_report(self) -> None:
        """打印统一 Optuna 优化报告。"""
        print(dump_report(self.build_report()))
