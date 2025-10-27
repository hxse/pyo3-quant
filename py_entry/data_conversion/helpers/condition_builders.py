"""条件快速构建辅助函数"""

from ..input import (
    CompareOp,
    SignalCondition,
    RiskCondition,
    ParamOperand,
    SignalDataOperand,
    RiskDataOperand,
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
        compare=compare.value,
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
        compare=compare.value,
        a=SignalDataOperand(name=a_name, source=a_source, offset=a_offset),
        b=ParamOperand(name=b_param),
    )


def risk_data_vs_data(
    compare: CompareOp, a_name: str, a_source: str, b_name: str, b_source: str
) -> RiskCondition:
    """Risk: data vs data"""
    return RiskCondition(
        compare=compare.value,
        a=RiskDataOperand(name=a_name, source=a_source),
        b=RiskDataOperand(name=b_name, source=b_source),
    )


def risk_data_vs_param(
    compare: CompareOp, a_name: str, a_source: str, b_param: str
) -> RiskCondition:
    """Risk: data vs param"""
    return RiskCondition(
        compare=compare.value,
        a=RiskDataOperand(name=a_name, source=a_source),
        b=ParamOperand(name=b_param),
    )
