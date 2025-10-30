from abc import ABC, abstractmethod
from py_entry.data_conversion.input import (
    SignalTemplate,
    CompareOp,
    LogicOp,
    SignalGroup,
)
from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
)


class BaseSignalTemplateBuilder(ABC):
    @abstractmethod
    def build_signal_template_instance(self) -> SignalTemplate:
        pass


class DefaultSignalTemplateBuilder(BaseSignalTemplateBuilder):
    def build_signal_template_instance(self) -> SignalTemplate:
        enter_long_group = SignalGroup(
            logic=LogicOp.AND,
            conditions=[
                signal_data_vs_data(
                    compare=CompareOp.GT,
                    a_name="sma_0",
                    a_source="ohlcv_0",
                    a_offset=0,
                    b_name="sma_1",
                    b_source="ohlcv_0",
                    b_offset=0,
                )
            ],
        )

        return SignalTemplate(
            name="multi_timeframe_dynamic_strategy", enter_long=[enter_long_group]
        )
