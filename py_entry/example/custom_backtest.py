import path_tool
import time


from py_entry.data_conversion.backtest_runner import (
    BacktestRunner,
    DefaultDataBuilder,
    DefaultParamBuilder,
    DefaultEngineSettingsBuilder,
    SettingContainer,
    ExecutionStage,
    DefaultSignalTemplateBuilder,
    DefaultRiskTemplateBuilder,
)
from py_entry.data_conversion.input import (
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    RiskParams,
    PerformanceParams,
    SignalTemplate,
    RiskTemplate,
    Param,
)

from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
    risk_data_vs_data,
    risk_data_vs_param,
)

from py_entry.data_conversion.input import (
    SignalTemplate,
    RiskTemplate,
    CompareOp,
    LogicOp,
    SignalGroup,
)

import pyo3_quant


from loguru import logger

# ==============================================================================
# 自定义 Builder 类
# ==============================================================================


class CustomParamBuilder(DefaultParamBuilder):
    """
    自定义参数构建器。
    用户可以通过覆盖此类的特定方法来定制回测参数。
    如果某个方法未被覆盖，将使用父类 DefaultParamBuilder 的默认实现。
    """

    def build_indicators_params(self, period_count: int) -> IndicatorsParams:
        """
        构建指标参数。
        用户可以通过取消注释并实现此方法来自定义指标参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_indicators_params(period_count)
        sma_0 = {
            "period": Param.create(8),
        }
        sma_1 = {
            "period": Param.create(16),
        }
        rsi_0 = {
            "period": Param.create(14),
        }
        bbands_0 = {
            "period": Param.create(14),
            "std": Param.create(2),
        }
        indicators_0 = {
            "bbands_0": bbands_0,
        }
        indicators_1 = {
            "rsi_0": rsi_0,
        }
        indicators_2 = {
            "sma_0": sma_0,
            "sma_1": sma_1,
        }

        return {
            "ohlcv": [
                indicators_0,
                indicators_1,
                indicators_2,
                *[{} for i in range(period_count)],
            ][:period_count]
        }

    def build_signal_params(self) -> SignalParams:
        """
        构建信号参数。
        用户可以通过取消注释并实现此方法来自定义信号参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_signal_params()
        return {"rsi_midline": Param.create(20, 10, 90, 5)}

    def build_backtest_params(self) -> BacktestParams:
        """
        构建回测参数。
        用户可以通过取消注释并实现此方法来自定义回测参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        return super().build_backtest_params()

    def build_risk_params(self) -> RiskParams:
        """
        构建风险参数。
        用户可以通过取消注释并实现此方法来自定义风险参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        return super().build_risk_params()

    def build_performance_params(self) -> PerformanceParams:
        """
        构建性能参数。
        用户可以通过取消注释并实现此方法来自定义性能参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        return super().build_performance_params()


class CustomSignalTemplateBuilder(DefaultSignalTemplateBuilder):
    """
    自定义信号模板构建器。
    用户可以通过覆盖此类的特定方法来定制信号模板。
    如果某个方法未被覆盖，将使用父类 DefaultSignalTemplateBuilder 的默认实现。
    """

    def build_signal_template_instance(self) -> SignalTemplate:
        """
        构建信号模板实例。
        用户可以通过取消注释并实现此方法来自定义信号模板实例。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_signal_template_instance()

        enter_long_group = SignalGroup(
            logic=LogicOp.AND,
            conditions=[
                signal_data_vs_data(
                    compare=CompareOp.GT,
                    a_name="sma_0",
                    a_source="ohlcv_2",
                    a_offset=0,
                    b_name="sma_1",
                    b_source="ohlcv_2",
                    b_offset=0,
                ),
                signal_data_vs_param(
                    compare=CompareOp.GT,
                    a_name="rsi_0",
                    a_source="ohlcv_1",
                    a_offset=0,
                    b_param="rsi_midline",
                ),
                signal_data_vs_data(
                    compare=CompareOp.CGT,
                    a_name="close",
                    a_source="ohlcv_0",
                    a_offset=0,
                    b_name="bbands_0_upper",
                    b_source="ohlcv_0",
                    b_offset=0,
                ),
            ],
        )

        return SignalTemplate(
            name="multi_timeframe_dynamic_strategy", enter_long=[enter_long_group]
        )


class CustomRiskTemplateBuilder(DefaultRiskTemplateBuilder):
    """
    自定义风险模板构建器。
    用户可以通过覆盖此类的特定方法来定制风险模板。
    如果某个方法未被覆盖，将使用父类 DefaultRiskTemplateBuilder 的默认实现。
    """

    def build_risk_template_instance(self) -> RiskTemplate:
        """
        构建风险模板实例。
        用户可以通过取消注释并实现此方法来自定义风险模板实例。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        return super().build_risk_template_instance()


class CustomEngineSettingsBuilder(DefaultEngineSettingsBuilder):
    """
    自定义引擎设置构建器。
    用户可以通过覆盖此类的特定方法来定制引擎设置。
    如果某个方法未被覆盖，将使用父类 DefaultEngineSettingsBuilder 的默认实现。
    """

    def build_engine_settings(self) -> SettingContainer:
        """
        构建引擎设置。
        用户可以通过取消注释并实现此方法来自定义引擎设置。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_engine_settings()

        return SettingContainer(
            # execution_stage=ExecutionStage.INDICATOR,
            execution_stage=ExecutionStage.PERFORMANCE,
            return_only_final=False,
            skip_risk=True,
        )


if __name__ == "__main__":
    print("-" * 30)
    start_time = time.perf_counter()
    res = pyo3_quant.minimal_working_example.sum_as_string(5, 25)
    print("sum_as_string:", res)
    print("耗时", time.perf_counter() - start_time)

    print("-" * 30)
    start_time = time.perf_counter()

    br = BacktestRunner()

    backtest_result = (
        br.with_data(
            {
                "timeframes": ["15m", "1h", "4h"],
                "start_time": 1735689600000,
                "num_bars": 200,
            },
            data_builder=DefaultDataBuilder(),
        )
        .with_param_set(param_builder=CustomParamBuilder())
        .with_templates(
            signal_template_builder=CustomSignalTemplateBuilder(),
            risk_template_builder=CustomRiskTemplateBuilder(),
        )
        .with_engine_settings(engine_settings_builder=CustomEngineSettingsBuilder())
        .run()
    )

    print(backtest_result)
    logger.info(f"performance: {backtest_result[0].performance}")

    logger.info(f"耗时 {time.perf_counter() - start_time}")
