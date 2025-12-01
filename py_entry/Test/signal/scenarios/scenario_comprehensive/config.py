"""场景: 综合场景测试配置

综合测试：多时间周期、多种指标、复杂逻辑组合、参数引用
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
        "bbands_20": {"period": Param.create(20), "std": Param.create(2.0)},
    },
    "ohlcv_1h": {
        "rsi_14": {"period": Param.create(14)},
    },
    "ohlcv_4h": {
        "sma_10": {"period": Param.create(10)},
        "sma_30": {"period": Param.create(30)},
    },
}

# 2. 信号参数
SIGNAL_PARAMS = {
    "rsi_midline": Param.create(50.0),
    "rsi_oversold": Param.create(30.0),
}

# 3. 信号模板
# Enter Long:
#   (15m Close > 15m BB Upper)  -- 突破布林带上轨
#   AND
#   (1h RSI > 50)               -- 1h 趋势向上
#   AND
#   (4h SMA_10 > 4h SMA_30)     -- 4h 均线多头排列
#
# Exit Long:
#   (15m Close < 15m BB Lower)  -- 跌破布林带下轨
#   OR
#   (1h RSI < 30)               -- 1h 进入超卖区 (趋势反转风险)

SIGNAL_TEMPLATE = SignalTemplate(
    name="scenario_comprehensive",
    enter_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ohlcv_15m, 0 > bbands_20_upper, ohlcv_15m, 0",
            "rsi_14, ohlcv_1h, 0 > $rsi_midline",
            "sma_10, ohlcv_4h, 0 > sma_30, ohlcv_4h, 0",
        ],
    ),
    exit_long=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            "close, ohlcv_15m, 0 < bbands_20_lower, ohlcv_15m, 0",
            "rsi_14, ohlcv_1h, 0 < $rsi_oversold",
        ],
    ),
    enter_short=None,
    exit_short=None,
)

DESCRIPTION = (
    "综合场景：多周期(15m/1h/4h) + 多指标(BB/RSI/SMA) + 复杂逻辑(AND/OR) + 参数引用"
)
