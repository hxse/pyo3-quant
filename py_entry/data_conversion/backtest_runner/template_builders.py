from abc import ABC, abstractmethod
from typing import List, Dict, Any

from py_entry.data_conversion.input import SignalTemplate, RiskTemplate, CompareOp
from py_entry.data_conversion.helpers import (
    create_signal_group,
    create_risk_rule,
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
        enter_long_group = create_signal_group(
            logic="and",
            target="enter_long",
            conditions=[
                signal_data_vs_data("sma_0", "sma_1", CompareOp.GT, mtf=2),
                signal_data_vs_param("rsi_0", "rsi_midline", CompareOp.GT, mtf=1),
                signal_data_vs_data("close", "bbands_upper", CompareOp.CGT),
            ],
        )

        return SignalTemplate(
            name="multi_timeframe_dynamic_strategy", template=[enter_long_group]
        )


class BaseRiskTemplateBuilder(ABC):
    @abstractmethod
    def build_risk_template_instance(self) -> RiskTemplate:
        pass


class DefaultRiskTemplateBuilder(BaseRiskTemplateBuilder):
    def build_risk_template_instance(self) -> RiskTemplate:
        rules = [
            create_risk_rule(
                "and",
                "size_up_pct",
                [risk_data_vs_data("balance", "bbands_upper", CompareOp.GT)],
            ),
            create_risk_rule(
                "and",
                "size_down_pct",
                [risk_data_vs_data("balance", "bbands_lower", CompareOp.LT)],
            ),
            create_risk_rule(
                "and",
                "size_mid_pct",
                [risk_data_vs_param("balance", "zero_value", CompareOp.GE)],
            ),
        ]

        return RiskTemplate(name="bbands_position_sizing", template=rules)
