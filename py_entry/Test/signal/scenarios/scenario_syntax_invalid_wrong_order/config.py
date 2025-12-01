"""场景: 无效的语法 - name/source/offset顺序错误

测试目标：验证参数顺序错误时的错误处理
预期：应该抛出解析错误或数据源未找到错误
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

# 预期的异常类型（数据源未找到）
EXPECTED_EXCEPTION = pyo3_quant.errors.PySourceNotFoundError

DESCRIPTION = "测试无效的语法：name/source/offset顺序错误应该报错"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# enter_long: 参数顺序错误，应该报错
# 错误写法: "ohlcv_15m, close, 0 > sma_0, ohlcv_15m, 0"
# 正确顺序应该是: name, source, offset
# 这里把source和name的顺序颠倒了
SIGNAL_TEMPLATE = SignalTemplate(
    name="syntax_invalid_wrong_order",
    enter_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "ohlcv_15m, close, 0 > sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    enter_short=None,
    exit_short=None,
)
