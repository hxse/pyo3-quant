from helpers.condition_builders import signal_data_vs_data, signal_data_vs_param
from helpers.template_builders import create_signal_group, create_signal_template
from py_entry.data_conversion.input.template import CompareOp


def create_signal_template_instance():
    """创建 signal template"""
    enter_long_group = create_signal_group(
        logic="and",
        target="enter_long",
        conditions=[
            signal_data_vs_data("sma_0", "sma_1", CompareOp.GT, mtf=2),
            signal_data_vs_param("rsi_0", "rsi_midline", CompareOp.GT, mtf=1),
            signal_data_vs_data("close", "bbands_upper", CompareOp.CGT),
        ],
    )

    return create_signal_template(
        name="multi_timeframe_dynamic_strategy", groups=[enter_long_group]
    )
