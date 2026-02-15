"""场景: 数值字面量比较测试配置

测试信号生成器对数值字面量 (Scalar) 的支持
"""

from py_entry.types import (
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

# 1. 指标参数
INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi_14": {"period": Param(14)},
    },
    "ohlcv_1h": {},
    "ohlcv_4h": {},
}

# 2. 信号参数 (本场景不使用参数引用，但为了兼容性可以留空或保留一些无关参数)
SIGNAL_PARAMS = {}

# 3. 信号模板 (直接使用数值字面量)
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # RSI < 30 (直接使用数值)
            "rsi_14, ohlcv_15m, 0 < 30.0",
        ],
    ),
    exit_long=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # RSI > 70 (直接使用数值)
            "rsi_14, ohlcv_15m, 0 > 70",
        ],
    ),
    entry_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # RSI > 70 (直接使用数值)
            "rsi_14, ohlcv_15m, 0 > 70.0",
        ],
    ),
    exit_short=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # RSI < 30 (直接使用数值)
            "rsi_14, ohlcv_15m, 0 < 30",
        ],
    ),
)

DESCRIPTION = "测试数值字面量：直接在信号条件中使用数字 (如 < 30.0)"
