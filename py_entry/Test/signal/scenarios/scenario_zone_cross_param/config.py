"""场景: 区间穿越参数化边界 - x> with $param"""

from py_entry.types import SignalTemplate, SignalGroup, LogicOp, Param

DESCRIPTION = "测试参数化区间穿越：rsi x> $lower..$upper"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi": {"period": Param.create(14)},
    },
}

SIGNAL_PARAMS = {
    "lower": Param.create(30.0),
    "upper": Param.create(70.0),
}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 x> $lower..$upper"],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
