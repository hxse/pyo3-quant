"""场景: 无效的长度不匹配偏移 - range/list长度不匹配

测试目标：验证左右操作数offset长度不匹配时的错误处理
预期：应该抛出 InvalidOffset 错误
"""

from py_entry.data_conversion.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)
import pyo3_quant

# 预期的异常类型
EXPECTED_EXCEPTION = pyo3_quant.errors.PyInvalidOffsetError

DESCRIPTION = "测试无效的长度不匹配偏移：左右操作数offset长度不匹配应该报错"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
        "sma_1": {"period": Param.create(30)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# enter_long: 左边有3个offset(&0-2)，右边有2个offset(&1-2)，长度不匹配
SIGNAL_TEMPLATE = SignalTemplate(
    enter_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, &0-2 > sma_0, ohlcv_15m, &1-2",
        ],
    ),
    exit_long=None,
    enter_short=None,
    exit_short=None,
)
