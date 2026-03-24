"""场景: 非 base source 上使用 xin

测试目标：验证 xin 也属于交叉类运算符，只能用于 base_data_key。
"""

from py_entry.types import SignalTemplate, SignalGroup, LogicOp, Param
import pyo3_quant

EXPECTED_EXCEPTION = pyo3_quant.errors.PyInvalidInputError

DESCRIPTION = "测试非 base source 上使用 xin 应该报错"

INDICATORS_PARAMS = {
    "ohlcv_1h": {
        "ema_0": {"period": Param(20)},
        "ema_1": {"period": Param(50)},
    },
}

SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_1h, 0 xin ema_0, ohlcv_1h, 0 .. ema_1, ohlcv_1h, 0",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
