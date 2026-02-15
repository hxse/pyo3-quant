"""场景: 区间穿越向上 - x> with .."""

from py_entry.types import (
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试区间穿越向上：rsi x> 30..70 表示RSI上穿30后持续有效直到70"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi": {"period": Param(14)},
    },
}

# 使用默认参数
SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["rsi, ohlcv_15m, 0 x> 30..70"],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
