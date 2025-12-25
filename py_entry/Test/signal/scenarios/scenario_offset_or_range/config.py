"""场景: OR范围偏移 - |0-2

测试目标：验证OR范围偏移语法的正确性
语法：|0-2 表示 offset 0, 1, 2 中任一满足条件即可
"""

from py_entry.data_conversion.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试OR范围偏移：|0-2 表示最近3根K线中至少有一根满足条件"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# entry_long: 最近3根K线中至少有一根收盘价大于SMA
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, |0-2 > sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
