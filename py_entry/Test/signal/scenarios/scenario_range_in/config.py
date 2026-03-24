"""场景: 当前值位于区间内 - in with .."""

from py_entry.types import SignalTemplate, SignalGroup, LogicOp, Param

DESCRIPTION = "测试 in ..：当前值是否位于闭区间内"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi": {"period": Param(14)},
    },
}

SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 in 30..70"],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
