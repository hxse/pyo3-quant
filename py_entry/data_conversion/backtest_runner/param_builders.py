from abc import ABC, abstractmethod
from py_entry.data_conversion.input import (
    PerformanceMetric,
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    RiskParams,
    PerformanceParams,
    Param,
)


class BaseParamBuilder(ABC):
    @abstractmethod
    def build_indicators_params(self, period_count: int) -> IndicatorsParams:
        pass

    @abstractmethod
    def build_signal_params(self) -> SignalParams:
        pass

    @abstractmethod
    def build_backtest_params(self) -> BacktestParams:
        pass

    @abstractmethod
    def build_risk_params(self) -> RiskParams:
        pass

    @abstractmethod
    def build_performance_params(self) -> PerformanceParams:
        pass


class DefaultParamBuilder(BaseParamBuilder):
    def build_indicators_params(self, period_count: int) -> IndicatorsParams:
        sma_0 = {
            "period": Param.create(14, 5, 50, 1),
        }
        sma_1 = {
            "period": Param.create(200, 100, 300, 10),
        }
        indicators_0 = {
            "sma_0": sma_0,
            "sma_1": sma_1,
        }

        return {
            "ohlcv": [
                indicators_0,
                *[{} for i in range(period_count)],
            ][:period_count]
        }

    def build_signal_params(self) -> SignalParams:
        return {"rsi_midline": Param.create(20, 10, 90, 5)}

    def build_backtest_params(self) -> BacktestParams:
        return BacktestParams(
            sl=Param.create(2, 0.5, 5, 0.1),
            tp=Param.create(2, 0.5, 5, 0.1),
            position_pct=Param.create(1, 0.1, 1, 0.1),
        )

    def build_risk_params(self) -> RiskParams:
        return {
            "size_up_pct": Param.create(1.5, 1.0, 3.0, 0.1),
            "size_down_pct": Param.create(0.5, 0.1, 1.0, 0.1),
        }

    def build_performance_params(self) -> PerformanceParams:
        return PerformanceParams(metrics=list(PerformanceMetric))
