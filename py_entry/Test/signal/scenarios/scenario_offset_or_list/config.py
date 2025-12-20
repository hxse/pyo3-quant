"""场景: OR列表偏移 - |0/1/5

测试目标：验证OR列表偏移语法的正确性
语法：|0/1/5 表示 offset 0, 1, 5 中任一满足条件即可
"""

from py_entry.data_conversion.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试OR列表偏移：|0/1/5 表示指定的K线中至少有一根满足条件"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# enter_long: K线0、1、5中至少有一根收盘价大于SMA
SIGNAL_TEMPLATE = SignalTemplate(
    enter_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, |0/1/5 > sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    enter_short=None,
    exit_short=None,
)
