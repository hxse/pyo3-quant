"""场景: 区间穿越动态边界 - x> with Series operands"""

from py_entry.types import (
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试动态区间穿越：close x> ema_30..ema_100 表示价格站上 EMA30 后持续有效直到碰到 EMA100"

INDICATORS_PARAMS = {
    "ohlcv_1h": {
        "ema_0": {"period": Param.create(30)},
        "ema_1": {"period": Param.create(100)},
    },
}

SIGNAL_PARAMS = {}

SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["close, ohlcv_1h, 0 x> ema_0, ohlcv_1h, 0 .. ema_1, ohlcv_1h, 0"],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
