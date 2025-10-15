from abc import ABC, abstractmethod
from typing import List, Dict, Any

from py_entry.data_conversion.input import (
    BacktestParams,
    PerformanceParams,
    PerformanceMetric,
)
from py_entry.data_conversion.helpers import create_param


class BaseParamBuilder(ABC):
    @abstractmethod
    def build_indicators_params(self, period_count: int) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def build_signal_params(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def build_backtest_params(self) -> BacktestParams:
        pass

    @abstractmethod
    def build_risk_params(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def build_performance_params(self) -> PerformanceParams:
        pass


class DefaultParamBuilder(BaseParamBuilder):
    def build_indicators_params(self, period_count: int) -> List[Dict[str, Any]]:
        sma_0 = {
            "period": create_param(14, 5, 50, 1),
        }
        sma_1 = {
            "period": create_param(200, 100, 300, 10),
        }
        indicators_0 = {
            "sma_0": sma_0,
            "sma_1": sma_1,
        }

        return [
            indicators_0,
            *[{} for i in range(period_count)],
        ][:period_count]

    def build_signal_params(self) -> Dict[str, Any]:
        return {"b": create_param(20, 5, 100, 5)}

    def build_backtest_params(self) -> BacktestParams:
        return BacktestParams(
            sl=create_param(2, 0.5, 5, 0.1),
            tp=create_param(2, 0.5, 5, 0.1),
            position_pct=create_param(1, 0.1, 1, 0.1),
        )

    def build_risk_params(self) -> Dict[str, Any]:
        return {
            "size_up_pct": create_param(1.5, 1.0, 3.0, 0.1),
            "size_down_pct": create_param(0.5, 0.1, 1.0, 0.1),
        }

    def build_performance_params(self) -> PerformanceParams:
        return PerformanceParams(metrics=list(PerformanceMetric))
