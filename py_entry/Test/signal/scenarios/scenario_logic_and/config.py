"""场景: AND逻辑组合测试配置

测试多个条件的 AND 逻辑组合
"""

from py_entry.data_conversion.types import (
    SignalTemplate,
    SignalGroup,
    LogicOp,
    SignalParams,
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
    "rsi_threshold": Param.create(50.0),
}

# 3. 信号模板
# enter_long: (close > sma_20) AND (rsi_14 > 50)
SIGNAL_TEMPLATE = SignalTemplate(
    name="scenario_logic_and",
    enter_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, 0 > sma_20, ohlcv_15m, 0",
            "rsi_14, ohlcv_15m, 0 > $rsi_threshold",
        ],
        sub_groups=[],
    ),
    exit_long=None,
    enter_short=None,
    exit_short=None,
)

DESCRIPTION = "测试AND逻辑组合：(close > sma) AND (rsi > 50)"
