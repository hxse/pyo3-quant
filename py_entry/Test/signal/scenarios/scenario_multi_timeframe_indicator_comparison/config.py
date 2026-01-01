"""场景: 多时间周期指标比较测试

测试目标：验证不同时间周期的指标之间互相比较的正确性
这是一个简单的多时间周期指标比较策略，专注于测试不同周期指标的交叉比较

策略逻辑：
1. 趋势确认：比较不同时间周期的EMA指标
2. 动量确认：比较不同时间周期的RSI指标
3. 入场条件：短期指标 > 长期指标 (多时间周期)
4. 出场条件：短期指标 < 长期指标 (多时间周期)
"""

from py_entry.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "多时间周期指标比较：测试不同周期指标之间的交叉比较"

INDICATORS_PARAMS: IndicatorsParams = {
    "ohlcv_15m": {
        # 短期趋势指标
        "ema_0": {"period": Param.create(21, 10, 50, 5)},  # 15分钟EMA
        # 短期动量指标
        "rsi_0": {"period": Param.create(14, 5, 30, 1)},
        # 短期波动率指标
        "bbands_0": {
            "period": Param.create(20, 10, 30, 5),
            "std": Param.create(2.0, 1.5, 3.0, 0.5),
        },
    },
    "ohlcv_1h": {
        # 中期趋势指标
        "ema_0": {"period": Param.create(21, 10, 50, 5)},  # 1小时EMA
        # 中期动量指标
        "rsi_0": {"period": Param.create(14, 5, 30, 1)},
        # 中期波动率指标
        "bbands_0": {
            "period": Param.create(20, 10, 30, 5),
            "std": Param.create(2.0, 1.5, 3.0, 0.5),
        },
    },
    "ohlcv_4h": {
        # 长期趋势指标
        "ema_0": {"period": Param.create(21, 10, 50, 5)},  # 4小时EMA
        # 长期动量指标
        "rsi_0": {"period": Param.create(14, 5, 30, 1)},
    },
}

SIGNAL_PARAMS: SignalParams = {
    # RSI阈值
    "rsi_midline": Param.create(50.0, 40.0, 60.0, 5.0),
}

# 多时间周期指标比较信号模板
SIGNAL_TEMPLATE = SignalTemplate(
    # 做多入场信号
    # 逻辑：不同时间周期的指标比较，确认多时间周期趋势一致
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # 1. EMA多时间周期比较：15分钟EMA > 1小时EMA > 4小时EMA (趋势向上)
            "ema_0, ohlcv_15m, 0 > ema_0, ohlcv_1h, 0",  # 15分钟EMA > 1小时EMA
            "ema_0, ohlcv_1h, 0 > ema_0, ohlcv_4h, 0",  # 1小时EMA > 4小时EMA
            # 2. RSI多时间周期比较：短期RSI > 中期RSI > 长期RSI (动量向上)
            "rsi_0, ohlcv_15m, 0 > rsi_0, ohlcv_1h, 0",  # 15分钟RSI > 1小时RSI
            "rsi_0, ohlcv_1h, 0 > rsi_0, ohlcv_4h, 0",  # 1小时RSI > 4小时RSI
            # 3. 价格与多时间周期指标比较
            "close, ohlcv_15m, 0 > ema_0, ohlcv_1h, 0",  # 15分钟收盘价 > 1小时EMA
            "close, ohlcv_15m, 0 > bbands_0_middle, ohlcv_1h, 0",  # 15分钟收盘价 > 1小时布林带中轨
        ],
    ),
    # 做空入场信号
    # 逻辑：不同时间周期的指标比较，确认多时间周期趋势向下
    entry_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            # 1. EMA多时间周期比较：15分钟EMA < 1小时EMA < 4小时EMA (趋势向下)
            "ema_0, ohlcv_15m, 0 < ema_0, ohlcv_1h, 0",  # 15分钟EMA < 1小时EMA
            "ema_0, ohlcv_1h, 0 < ema_0, ohlcv_4h, 0",  # 1小时EMA < 4小时EMA
            # 2. RSI多时间周期比较：短期RSI < 中期RSI < 长期RSI (动量向下)
            "rsi_0, ohlcv_15m, 0 < rsi_0, ohlcv_1h, 0",  # 15分钟RSI < 1小时RSI
            "rsi_0, ohlcv_1h, 0 < rsi_0, ohlcv_4h, 0",  # 1小时RSI < 4小时RSI
            # 3. 价格与多时间周期指标比较
            "close, ohlcv_15m, 0 < ema_0, ohlcv_1h, 0",  # 15分钟收盘价 < 1小时EMA
            "close, ohlcv_15m, 0 < bbands_0_middle, ohlcv_1h, 0",  # 15分钟收盘价 < 1小时布林带中轨
        ],
    ),
    # 做多离场信号
    exit_long=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # 1. EMA多时间周期趋势反转
            "ema_0, ohlcv_15m, 0 < ema_0, ohlcv_1h, 0",  # 15分钟EMA跌破1小时EMA
            # 2. RSI多时间周期动量反转
            "rsi_0, ohlcv_15m, 0 < $rsi_midline",  # 15分钟RSI跌破中轴线
        ],
    ),
    # 做空离场信号
    exit_short=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # 1. EMA多时间周期趋势反转
            "ema_0, ohlcv_15m, 0 > ema_0, ohlcv_1h, 0",  # 15分钟EMA突破1小时EMA
            # 2. RSI多时间周期动量反转
            "rsi_0, ohlcv_15m, 0 > $rsi_midline",  # 15分钟RSI突破中轴线
        ],
    ),
)
