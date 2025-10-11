from . import (
    risk_data_vs_data,
    risk_data_vs_param,
)
from . import (
    create_risk_rule,
    create_risk_template,
)
from ..input import CompareOp


def create_risk_template_instance():
    """创建 risk template"""
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

    return create_risk_template(name="bbands_position_sizing", rules=rules)
