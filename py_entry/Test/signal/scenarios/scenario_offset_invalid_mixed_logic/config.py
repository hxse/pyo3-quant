"""场景: 无效的混合逻辑偏移 - &和|混用

测试目标：验证AND和OR逻辑混用时的错误处理
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

DESCRIPTION = "测试无效的混合逻辑偏移：&和|混用应该报错"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# entry_long: 混合使用AND和OR逻辑，应该报错
# 左边使用AND逻辑(&0-2)，右边使用OR逻辑(|1-3)
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, &0-2 > sma_0, ohlcv_15m, |1-3",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
