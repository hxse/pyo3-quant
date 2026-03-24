"""场景: 区间穿越动态边界 - x> with Series operands"""

from py_entry.types import (
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试 base 周期上的动态区间穿越：close x> ema_30..ema_100"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "ema_0": {"period": Param(30)},
        "ema_1": {"period": Param(100)},
    },
}

SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, 0 x> ema_0, ohlcv_15m, 0 .. ema_1, ohlcv_15m, 0"
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
