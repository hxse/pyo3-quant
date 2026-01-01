"""场景: 参数引用测试配置

测试信号生成器对参数引用 ($param_name) 的支持
"""

from py_entry.types import (
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)
# from py_entry.Test.signal.utils import get_indicator

# 1. 指标参数
# 1. 指标参数
INDICATORS_PARAMS = {
    "ohlcv_15m": {
        "rsi_14": {"period": Param.create(14)},
        "sma_20": {"period": Param.create(20)},
    },
    "ohlcv_1h": {},
    "ohlcv_4h": {},
}

# 2. 信号参数 (定义将被引用的参数)
# SignalParams 是 Dict[str, Param] 类型别名，直接使用字典
SIGNAL_PARAMS = {
    "rsi_buy_threshold": Param.create(30.0),
    "rsi_sell_threshold": Param.create(70.0),
    "sma_period_param": Param.create(20.0),
}

# 3. 信号模板 (使用 $param_name 引用参数)
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # RSI < 30 (使用参数引用)
            "rsi_14, ohlcv_15m, 0 < $rsi_buy_threshold",
        ],
    ),
    exit_long=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # RSI > 70 (使用参数引用)
            "rsi_14, ohlcv_15m, 0 > $rsi_sell_threshold",
        ],
    ),
    entry_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # RSI > 70 (使用参数引用)
            "rsi_14, ohlcv_15m, 0 > $rsi_sell_threshold",
        ],
    ),
    exit_short=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # RSI < 30 (使用参数引用)
            "rsi_14, ohlcv_15m, 0 < $rsi_buy_threshold",
        ],
    ),
)

DESCRIPTION = "测试参数引用：使用 $param_name 在信号条件中引用外部参数"
