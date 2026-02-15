"""场景: 无效的语法 - 省略第一个参数name

测试目标：验证省略第一个参数（name）时的错误处理
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

DESCRIPTION = "测试无效的语法：省略第一个参数name应该报错"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "sma_0": {"period": Param(20)},
    },
}

SIGNAL_PARAMS = {}

# entry_long: 省略第一个参数name，应该报错
# 错误写法: ", ohlcv_15m, 0 > sma_0, ohlcv_15m, 0"
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            ", ohlcv_15m, 0 > sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
