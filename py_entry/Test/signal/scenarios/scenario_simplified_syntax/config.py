"""场景: 简化语法测试配置

测试信号生成器对简化语法的支持
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
        "sma_10": {"period": Param(10)},
    },
    "ohlcv_1h": {},
    "ohlcv_4h": {},
}

# 2. 信号参数
SIGNAL_PARAMS = {}

# 3. 信号模板
SIGNAL_TEMPLATE = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # 简化写法: close > sma_10 (隐含 source=base_data_key, offset=0)
            "close > sma_10",
        ],
    ),
    exit_long=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # 完整写法但留空: close, , > sma_10, ,
            "close, , > sma_10, ,",
        ],
    ),
    entry_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # 混合写法: close, ohlcv_15m, 1 > sma_10 (左边偏移1, 右边简化)
            "close, ohlcv_15m, 1 > sma_10",
        ],
    ),
    exit_short=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # 混合写法: close > sma_10, , 1 (左边简化, 右边偏移1)
            "close > sma_10, , 1",
        ],
    ),
)

DESCRIPTION = "测试简化语法：省略 source 和 offset"
