"""场景: 无效的语法 - 省略部分逗号

测试目标：验证只出现部分逗号（1个逗号）时的错误处理
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


DESCRIPTION = "测试无效的语法：省略部分逗号（只有1个逗号）应该报错"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS = {}

# entry_long: 只有1个逗号，应该报错
# 错误写法: "close, ohlcv_15m > sma_0"
# 规则：要么0个逗号，要么2个逗号，不允许1个逗号
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m > sma_0",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
