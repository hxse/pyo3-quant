"""参数集生成逻辑"""

from ..input import (
    Param,
    ParamSet,
    SingleParamSet,
    BacktestParams,
    PerformanceParams,
)


def create_param_set(params_count: int, period_count: int) -> ParamSet:
    """
    创建参数集。
    """
    single_param_sets = []

    for i in range(params_count):
        sma_0 = {
            "period": Param(
                initial_value=14 + i, initial_min=5, initial_max=50, initial_step=1
            ),
        }
        sma_1 = {
            "period": Param(
                initial_value=50 + i, initial_min=10, initial_max=100, initial_step=5
            ),
        }

        indicators_params = [
            {
                "sma_0": sma_0,
                "sma_1": sma_1,
            },
            {},
        ]
        assert len(indicators_params) == period_count, (
            f"需要为每个周期配置指标参数 {len(indicators_params)} {period_count}"
        )

        backtest_params = BacktestParams(
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

        signal_params = {
            "b": Param(
                initial_value=20.0, initial_min=5.0, initial_max=100.0, initial_step=5.0
            )
        }
        risk_params = {
            "size_up_pct": Param(
                initial_value=1.5, initial_min=1.0, initial_max=3.0, initial_step=0.1
            ),
            "size_down_pct": Param(
                initial_value=0.5, initial_min=0.1, initial_max=1.0, initial_step=0.1
            ),
        }

        performance_params = PerformanceParams(
            metrics=["total_return", "sharpe_ratio", "max_drawdown"]
        )

        single_set = SingleParamSet(
            indicators=indicators_params,
            signal=signal_params,
            backtest=backtest_params,
            risk=risk_params,
            performance=performance_params,
        )
        single_param_sets.append(single_set)

    return ParamSet(params=single_param_sets)
