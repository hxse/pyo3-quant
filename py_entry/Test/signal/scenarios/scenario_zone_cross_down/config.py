"""场景: 区间穿越向下 - x< with .."""

from py_entry.types import (
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试区间穿越向下：RSI 从区间上方进入 [30, 70] 后持续有效"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi": {"period": Param(14)},
    },
}

SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 x< 70..30"],
    ),
    entry_long=None,
    exit_long=None,
    exit_short=None,
)
