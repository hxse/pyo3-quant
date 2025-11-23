"""条件快速构建辅助函数"""

from ..input import (
    CompareOp,
    SignalCondition,
    ParamOperand,
    SignalDataOperand,
)


def signal_data_vs_data(
    compare: CompareOp,
    a_name: str,
    a_source: str,
    b_name: str,
    b_source: str,
    a_offset: int = 0,
    b_offset: int = 0,
) -> SignalCondition:
    """Signal: data vs data"""
    return SignalCondition(
        compare=compare,
        a=SignalDataOperand(name=a_name, source=a_source, offset=a_offset),
        b=SignalDataOperand(name=b_name, source=b_source, offset=b_offset),
    )


def signal_data_vs_param(
    compare: CompareOp,
    a_name: str,
    a_source: str,
    b_param: str,
    a_offset: int = 0,
) -> SignalCondition:
    """Signal: data vs param"""
    return SignalCondition(
        compare=compare,
        a=SignalDataOperand(name=a_name, source=a_source, offset=a_offset),
        b=ParamOperand(name=b_param),
    )
