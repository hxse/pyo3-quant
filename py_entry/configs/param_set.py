"""参数集生成逻辑"""

from typing import List, Dict, Any
from py_entry.data_conversion.input.param_set import (
    Param,
    ParamSet,
    SingleParamSet,
    BacktestParams,
    PerformanceParams,
)


def create_param_set(data_dict_len: int) -> ParamSet:
    """
    创建参数集。
    """
    single_param_sets = []

    for i in range(data_dict_len):
        sma_0 = {
            "period": Param(
                initial_value=14 + i, initial_min=5, initial_max=50, initial_step=1
            ),
            "weight": Param(
                initial_value=0.5 + i / 10,
                initial_min=0.1,
                initial_max=1.0,
                initial_step=0.1,
            ),
        }
        sma_1 = {
            "period": Param(
                initial_value=50 + i, initial_min=10, initial_max=100, initial_step=5
            ),
            "weight": Param(
                initial_value=0.8 + i / 10,
                initial_min=0.1,
                initial_max=1.0,
                initial_step=0.1,
            ),
        }

        indicators_params = [
            {
                "sma_0": sma_0,
                "sma_1": sma_1,
            }
        ]

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
