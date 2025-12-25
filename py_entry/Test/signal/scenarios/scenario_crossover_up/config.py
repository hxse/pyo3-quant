"""场景: 向上交叉 - x>

测试目标：验证向上交叉比较的正确性
语法：x> 表示向上突破（前值不满足，当前值满足）
"""

from py_entry.data_conversion.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试向上交叉：x> 表示收盘价向上突破SMA（前一根 <= SMA，当前 > SMA）"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

SIGNAL_PARAMS: SignalParams = {}

# entry_long: 收盘价向上突破SMA
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, 0 x> sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
