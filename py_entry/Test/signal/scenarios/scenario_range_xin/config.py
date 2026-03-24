"""场景: 进入区间 - xin with .."""

from py_entry.types import SignalTemplate, SignalGroup, LogicOp, Param

DESCRIPTION = "测试 xin ..：前一根不在区间内，当前进入闭区间"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi": {"period": Param(14)},
    },
}

SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 xin 30..70"],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
