from abc import ABC, abstractmethod
from typing import List, Dict, Any

from py_entry.data_conversion.input import Param, BacktestParams, PerformanceParams


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
            "period": Param(
                initial_value=14, initial_min=5, initial_max=50, initial_step=1
            ),
        }
        sma_1 = {
            "period": Param(
                initial_value=60, initial_min=10, initial_max=100, initial_step=5
            ),
        }

        return [
            {
                "sma_0": sma_0,
                "sma_1": sma_1,
            },
            *[{} for i in range(period_count - 1)],
        ]

    def build_signal_params(self) -> Dict[str, Any]:
        return {
            "b": Param(
                initial_value=20.0, initial_min=5.0, initial_max=100.0, initial_step=5.0
            )
        }

    def build_backtest_params(self) -> BacktestParams:
        return BacktestParams(
            sl=Param(
                initial_value=2.0, initial_min=0.5, initial_max=5.0, initial_step=0.1
            ),
            tp=Param(
                initial_value=2.0, initial_min=0.5, initial_max=5.0, initial_step=0.1
            ),
            position_pct=Param(
                initial_value=1.0, initial_min=0.1, initial_max=1.0, initial_step=0.1
            ),
        )

    def build_risk_params(self) -> Dict[str, Any]:
        return {
            "size_up_pct": Param(
                initial_value=1.5, initial_min=1.0, initial_max=3.0, initial_step=0.1
            ),
            "size_down_pct": Param(
                initial_value=0.5, initial_min=0.1, initial_max=1.0, initial_step=0.1
            ),
        }

    def build_performance_params(self) -> PerformanceParams:
        return PerformanceParams(
            metrics=["total_return", "sharpe_ratio", "max_drawdown"]
        )
