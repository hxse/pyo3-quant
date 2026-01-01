"""场景: OR逻辑组合测试配置

测试多个条件的 OR 逻辑组合
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
        "rsi_14": {"period": Param.create(14)},
        "sma_20": {"period": Param.create(20)},
    },
    "ohlcv_1h": {},
    "ohlcv_4h": {},
}

# 2. 信号参数
SIGNAL_PARAMS = {
    "rsi_threshold": Param.create(70.0),
}

# 3. 信号模板
# entry_long: (close > sma_20) OR (rsi_14 > 70)
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            "close, ohlcv_15m, 0 > sma_20, ohlcv_15m, 0",
            "rsi_14, ohlcv_15m, 0 > $rsi_threshold",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)

DESCRIPTION = "测试OR逻辑组合：(close > sma) OR (rsi > 70)"
