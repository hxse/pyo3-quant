"""场景: 向下交叉 - x<

测试目标：验证向下交叉比较的正确性
语法：x< 表示向下跌破（前值不满足，当前值满足）
"""

from py_entry.data_conversion.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试向下交叉：x< 表示收盘价向下跌破SMA（前一根 >= SMA，当前 < SMA）"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# enter_short: 收盘价向下跌破SMA
SIGNAL_TEMPLATE = SignalTemplate(
    name="crossover_down_test",
    enter_long=None,
    exit_long=None,
    enter_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, 0 x< sma_0, ohlcv_15m, 0",
        ],
        sub_groups=[],
    ),
    exit_short=None,
)
