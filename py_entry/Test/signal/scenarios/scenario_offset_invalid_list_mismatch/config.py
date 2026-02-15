"""场景: 无效的列表长度不匹配偏移 - list长度不匹配

测试目标：验证左右操作数列表offset长度不匹配时的错误处理
预期：应该抛出 InvalidOffset 错误
"""

from py_entry.types import (
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

DESCRIPTION = "测试无效的列表长度不匹配偏移：左右操作数列表offset长度不匹配应该报错"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "sma_0": {"period": Param(20)},
        "sma_1": {"period": Param(30)},
    },
}

SIGNAL_PARAMS = {}

# entry_long: 左边有3个offset(&0/1/5)，右边有2个offset(&1/3)，长度不匹配
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, &0/1/5 > sma_0, ohlcv_15m, &1/3",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
