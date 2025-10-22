"""数据转换输入模块：所有输入数据结构的统一接口"""

from .settings import EngineSettings, ExecutionStage

from .data_dict import DataDict

from .param_set.param import Param

from .param_set.param_set import (
    ParamSet,
    SingleParamSet,
    IndicatorsParams,
    SignalParams,
    RiskParams,
    BacktestParams,
    PerformanceParams,
    PerformanceMetric,
)


from .template.templates import (
    TemplateConfig,
    SignalTemplate,
    RiskTemplate,
    SignalGroup,
    RiskGroup,
)
from .template.conditions import (
    CompareOp,
    SignalCondition,
    RiskCondition,
)
from .template.operands import (
    ParamOperand,
    SignalDataOperand,
    RiskDataOperand,
)
