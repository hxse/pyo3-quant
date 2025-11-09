"""
自定义Builder类实现
包含CustomParamBuilder、CustomSignalTemplateBuilder和CustomEngineSettingsBuilder
"""

from py_entry.data_conversion.backtest_runner import (
    DefaultParamBuilder,
    DefaultSignalTemplateBuilder,
    DefaultEngineSettingsBuilder,
    SettingContainer,
    ExecutionStage,
)
from py_entry.data_conversion.input import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    Param,
    CompareOp,
    LogicOp,
    SignalGroup,
)
from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
)


class CustomParamBuilder(DefaultParamBuilder):
    """
    自定义参数构建器，定义多时间框架指标参数
    """

    def build_indicators_params(self, period_count: int) -> IndicatorsParams:
        # 定义多个时间框架的指标参数
        bbands_0 = {"period": Param.create(20), "std": Param.create(2)}

        rsi_0 = {"period": Param.create(14)}

        sma_0 = {"period": Param.create(8)}
        sma_1 = {"period": Param.create(20)}

        # 按时间框架分组指标
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
        return {
            "rsi_upper": Param.create(80),
            "rsi_lower": Param.create(20),
        }


class CustomSignalTemplateBuilder(DefaultSignalTemplateBuilder):
    """
    自定义信号模板构建器，定义复杂信号逻辑
    """

    def build_signal_template_instance(self) -> SignalTemplate:
        # 只保留多时间框架信号组，简化测试
        enter_long = SignalGroup(
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
                    compare=CompareOp.LT,
                    a_name="rsi_0",
                    a_source="ohlcv_1",
                    a_offset=0,
                    b_param="rsi_lower",
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

        exit_long = SignalGroup(
            logic=LogicOp.OR,
            conditions=[
                signal_data_vs_data(
                    compare=CompareOp.LT,
                    a_name="close",
                    a_source="ohlcv_0",
                    a_offset=0,
                    b_name="bbands_0_upper",
                    b_source="ohlcv_0",
                    b_offset=0,
                ),
            ],
        )

        # 对称的做空信号
        enter_short = SignalGroup(
            logic=LogicOp.AND,
            conditions=[
                signal_data_vs_data(
                    compare=CompareOp.LT,
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
                    b_param="rsi_upper",
                ),
                signal_data_vs_data(
                    compare=CompareOp.CLT,
                    a_name="close",
                    a_source="ohlcv_0",
                    a_offset=0,
                    b_name="bbands_0_lower",
                    b_source="ohlcv_0",
                    b_offset=0,
                ),
            ],
        )

        exit_short = SignalGroup(
            logic=LogicOp.OR,
            conditions=[
                signal_data_vs_data(
                    compare=CompareOp.GT,
                    a_name="close",
                    a_source="ohlcv_0",
                    a_offset=0,
                    b_name="bbands_0_lower",
                    b_source="ohlcv_0",
                    b_offset=0,
                ),
            ],
        )

        return SignalTemplate(
            name="simplified_multi_timeframe_strategy",
            enter_long=[enter_long],
            exit_long=[exit_long],
            enter_short=[enter_short],
            exit_short=[exit_short],
        )


class CustomEngineSettingsBuilder(DefaultEngineSettingsBuilder):
    """
    自定义引擎设置构建器，确保运行到SIGNAL阶段
    """

    def build_engine_settings(self) -> SettingContainer:
        return SettingContainer(
            execution_stage=ExecutionStage.SIGNALS,  # 确保返回signals数据
            return_only_final=False,
        )
