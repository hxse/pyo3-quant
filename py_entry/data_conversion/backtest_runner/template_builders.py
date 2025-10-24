from abc import ABC, abstractmethod
from py_entry.data_conversion.input import (
    SignalTemplate,
    RiskTemplate,
    CompareOp,
    SignalGroup,
    RiskGroup,
)
from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
    risk_data_vs_data,
    risk_data_vs_param,
)


class BaseSignalTemplateBuilder(ABC):
    @abstractmethod
    def build_signal_template_instance(self) -> SignalTemplate:
        pass


class DefaultSignalTemplateBuilder(BaseSignalTemplateBuilder):
    def build_signal_template_instance(self) -> SignalTemplate:
        enter_long_group = SignalGroup(
            logic="and",
            conditions=[
                signal_data_vs_data(
                    compare=CompareOp.GT,
                    a_name="sma_0",
                    a_source="ohlcv",
                    a_source_idx=0,
                    a_offset=0,
                    b_name="sma_1",
                    b_source="ohlcv",
                    b_source_idx=0,
                    b_offset=0,
                ),
                signal_data_vs_param(
                    compare=CompareOp.GT,
                    a_name="rsi_0",
                    a_source="ohlcv",
                    a_source_idx=1,
                    a_offset=0,
                    b_param="rsi_midline",
                ),
                signal_data_vs_data(
                    compare=CompareOp.CGT,
                    a_name="close",
                    a_source="ohlcv",
                    a_source_idx=2,
                    a_offset=0,
                    b_name="bbands_upper",
                    b_source="ohlcv",
                    b_source_idx=2,
                    b_offset=0,
                ),
            ],
        )

        return SignalTemplate(
            name="multi_timeframe_dynamic_strategy", enter_long=enter_long_group
        )


class BaseRiskTemplateBuilder(ABC):
    @abstractmethod
    def build_risk_template_instance(self) -> RiskTemplate:
        pass


class DefaultRiskTemplateBuilder(BaseRiskTemplateBuilder):
    def build_risk_template_instance(self) -> RiskTemplate:
        size_neutral_pct = RiskGroup(
            logic="and",
            conditions=[
                risk_data_vs_param(
                    compare=CompareOp.GE,
                    a_name="balance",
                    a_source="balance",
                    b_param="zero_value",
                )
            ],
        )
        size_up_pct = RiskGroup(
            logic="and",
            conditions=[
                risk_data_vs_data(
                    compare=CompareOp.GT,
                    a_name="balance",
                    a_source="balance",
                    b_name="bbands_upper",
                    b_source="balance",
                ),
            ],
        )
        size_down_pct = RiskGroup(
            logic="and",
            conditions=[
                risk_data_vs_data(
                    compare=CompareOp.LT,
                    a_name="balance",
                    a_source="balance",
                    b_name="bbands_lower",
                    b_source="balance",
                )
            ],
        )
        size_skip_pct = RiskGroup(
            logic="and",
            conditions=[
                risk_data_vs_param(
                    compare=CompareOp.LE,
                    a_name="balance",
                    a_source="balance",
                    b_param="zero_value",
                )
            ],
        )
        return RiskTemplate(
            name="bbands_position_sizing",
            size_neutral_pct=size_neutral_pct,
            size_up_pct=size_up_pct,
            size_down_pct=size_down_pct,
            size_skip_pct=size_skip_pct,
        )
