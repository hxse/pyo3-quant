"""场景: 区间穿越 inclusive - x>= with .."""

from py_entry.types import SignalTemplate, SignalGroup, LogicOp, Param

DESCRIPTION = "测试 inclusive 区间穿越：rsi x>= 30..70"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi": {"period": Param(14)},
    },
}

SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 x>= 30..70"],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
