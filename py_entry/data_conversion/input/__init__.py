"""数据转换输入模块：所有输入数据结构的统一接口"""

from .settings import SettingContainer, ExecutionStage

from .data_dict import DataContainer

from .param_set.param import Param

from .param_set.param_set import (
    ParamContainer,
    SingleParamSet,
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    PerformanceMetric,
)


from .template.templates import (
    TemplateContainer,
    SignalTemplate,
    SignalGroup,
)
from .template.conditions import CompareOp, SignalCondition, RiskCondition, LogicOp
from .template.operands import ParamOperand, SignalDataOperand, RiskDataOperand
