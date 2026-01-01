"""场景: 无效的负数偏移 - offset不能是负数

测试目标：验证负数offset时的错误处理
预期：应该抛出解析错误
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
EXPECTED_EXCEPTION = pyo3_quant.errors.PyParseError

DESCRIPTION = "测试无效的负数偏移：offset不能是负数，应该报错"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# entry_long: 使用负数offset，应该报错
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, -1 > sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
