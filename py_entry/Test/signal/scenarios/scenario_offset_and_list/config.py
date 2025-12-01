"""场景: AND列表偏移 - &0/1/5

测试目标：验证AND列表偏移语法的正确性
语法：&0/1/5 表示 offset 0, 1, 5 都必须满足条件
"""

from py_entry.data_conversion.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试AND列表偏移：&0/1/5 表示指定的K线(0,1,5)都必须满足条件"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# enter_long: K线0、1、5的收盘价都大于SMA
SIGNAL_TEMPLATE = SignalTemplate(
    name="offset_and_list_test",
    enter_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, &0/1/5 > sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    enter_short=None,
    exit_short=None,
)
