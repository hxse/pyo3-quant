"""场景: AND范围偏移 - &0-2

测试目标：验证AND范围偏移语法的正确性
语法：&0-2 表示 offset 0, 1, 2 都必须满足条件
"""

from py_entry.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

# 场景描述
DESCRIPTION = "测试AND范围偏移：&0-2 表示最近3根K线(offset 0,1,2)都必须满足条件"

# 指标参数
INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
}

# 信号参数（本场景不需要）
SIGNAL_PARAMS = {}

# 信号模板
# entry_long: 最近3根K线的收盘价都大于当前SMA
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, &0-2 > sma_0, ohlcv_15m, 0",
        ],
    ),
    exit_long=None,
    entry_short=None,
    exit_short=None,
)
