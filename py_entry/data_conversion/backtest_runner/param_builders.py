from abc import ABC, abstractmethod
from py_entry.data_conversion.input import (
    PerformanceMetric,
    IndicatorsParams,
    SignalParams,
    BacktestParams,
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
            sl_pct=Param.create(2, 0.5, 5, 0.1),
            tp_pct=Param.create(2, 0.5, 5, 0.1),
            tsl_pct=Param.create(1, 0.5, 3, 0.1),
            sl_atr=Param.create(2, 1, 5, 0.5),
            tp_atr=Param.create(3, 1, 5, 0.5),
            tsl_atr=Param.create(2, 1, 4, 0.5),
            atr_period=Param.create(14, 7, 21, 1),
            tsl_use_high=True,
            tsl_per_bar_update=False,
            exit_in_bar=False,
            initial_capital=10000.0,
            stop_pct=Param.create(0.05, 0.01, 0.1, 0.01),
            resume_pct=Param.create(0.02, 0.01, 0.05, 0.01),
            fee_fixed=0.0,
            fee_pct=0.001,
        )

    def build_performance_params(self) -> PerformanceParams:
        return PerformanceParams(metrics=list(PerformanceMetric))
