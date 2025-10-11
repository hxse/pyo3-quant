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
    a_source: str, b_source: str, compare: CompareOp, offset: int = 0, mtf: int = 0
) -> SignalCondition:
    """Signal: data vs data"""
    return SignalCondition(
        compare=compare.value,
        a_data=SignalDataOperand(source=a_source, offset=offset, mtf=mtf),
        b_data=SignalDataOperand(source=b_source, offset=offset, mtf=mtf),
    )


def signal_data_vs_param(
    a_source: str, b_param: str, compare: CompareOp, offset: int = 0, mtf: int = 0
) -> SignalCondition:
    """Signal: data vs param"""
    return SignalCondition(
        compare=compare.value,
        a_data=SignalDataOperand(source=a_source, offset=offset, mtf=mtf),
        b_param=ParamOperand(source=b_param),
    )


def risk_data_vs_data(
    a_source: str, b_source: str, compare: CompareOp
) -> RiskCondition:
    """Risk: data vs data"""
    return RiskCondition(
        compare=compare.value,
        a_data=RiskDataOperand(source=a_source),
        b_data=RiskDataOperand(source=b_source),
    )


def risk_data_vs_param(
    a_source: str, b_param: str, compare: CompareOp
) -> RiskCondition:
    """Risk: data vs param"""
    return RiskCondition(
        compare=compare.value,
        a_data=RiskDataOperand(source=a_source),
        b_param=ParamOperand(source=b_param),
    )
