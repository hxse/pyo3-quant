"""场景: 复杂嵌套TA策略 - 多层次技术分析组合

测试目标：验证复杂嵌套技术分析策略的正确性
这是一个多层次的交易策略，结合趋势、动量和波动率指标

策略逻辑：
1. 趋势确认：使用EMA和SMA的组合判断趋势方向
2. 动量确认：使用RSI和MACD判断动量状态
3. 波动率过滤：使用布林带过滤震荡市场
4. 入场条件：趋势向上 + 动量超卖 + 价格突破布林带中轨
5. 出场条件：趋势转向 + 动量超买 + 价格跌破布林带中轨
"""

from py_entry.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "复杂嵌套TA策略：结合趋势、动量和波动率指标的多层次交易策略"

INDICATORS_PARAMS = {
    "ohlcv_15m": {
        # 趋势指标
        "ema_0": {"period": Param(21, min=10, max=50, step=5)},  # 短期EMA
        "ema_1": {"period": Param(55, min=20, max=100, step=10)},  # 长期EMA
        # 动量指标
        "rsi_0": {"period": Param(14, min=5, max=30, step=1)},
        # 趋势强度指标
        "adx_0": {"period": Param(14, min=5, max=30, step=1)},
    },
    "ohlcv_1h": {
        # 高时间框架趋势确认
        "ema_0": {"period": Param(55, min=20, max=100, step=10)},
    },
}

SIGNAL_PARAMS = {
    # RSI阈值
    "rsi_oversold": Param(30, min=20, max=40, step=5),
    "rsi_overbought": Param(70, min=60, max=80, step=5),
    # ADX阈值 (趋势/震荡分界)
    "adx_threshold": Param(25.0, min=15.0, max=40.0, step=1.0),
}

# 复杂嵌套策略信号模板
SIGNAL_TEMPLATE = SignalTemplate(
    # 做多入场信号
    # 逻辑：(ADX > 25 AND 趋势策略) OR (ADX < 25 AND 震荡策略)
    entry_long=SignalGroup(
        logic=LogicOp.OR,
        sub_groups=[
            # 1. 强趋势策略 (ADX > Threshold)
            SignalGroup(
                logic=LogicOp.AND,
                comparisons=[
                    "adx_0_adx, ohlcv_15m, 0 > $adx_threshold",  # 趋势强劲
                    "ema_0, ohlcv_15m, 0 > ema_1, ohlcv_15m, 0",  # 均线多头
                    "close, ohlcv_15m, 0 > ema_0, ohlcv_1h, 0",  # 收盘价 > 1小时EMA
                ],
                sub_groups=[
                    # 价格形态嵌套 (OR)
                    SignalGroup(
                        logic=LogicOp.OR,
                        comparisons=[
                            "close, ohlcv_15m, 0 > close, ohlcv_15m, &1/2",  # 收盘价 > 前两根收盘价
                            "close, ohlcv_15m, 0 > high, ohlcv_15m, 1",  # 收盘价 > 前一根最高价
                        ],
                    ),
                ],
            ),
            # 2. 震荡策略 (ADX < Threshold)
            SignalGroup(
                logic=LogicOp.AND,
                comparisons=[
                    "adx_0_adx, ohlcv_15m, 0 < $adx_threshold",  # 趋势疲弱
                    "rsi_0, ohlcv_15m, 0 < $rsi_oversold",  # RSI超卖
                ],
            ),
        ],
    ),
    # 做空入场信号
    # 逻辑：(ADX > 25 AND 趋势策略) OR (ADX < 25 AND 震荡策略)
    entry_short=SignalGroup(
        logic=LogicOp.OR,
        sub_groups=[
            # 1. 强趋势策略 (ADX > Threshold)
            SignalGroup(
                logic=LogicOp.AND,
                comparisons=[
                    "adx_0_adx, ohlcv_15m, 0 > $adx_threshold",  # 趋势强劲
                    "ema_0, ohlcv_15m, 0 < ema_1, ohlcv_15m, 0",  # 均线空头
                    "close, ohlcv_15m, 0 < ema_0, ohlcv_1h, 0",  # 收盘价 < 1小时EMA
                ],
                sub_groups=[
                    # 价格形态嵌套 (OR)
                    SignalGroup(
                        logic=LogicOp.OR,
                        comparisons=[
                            "close, ohlcv_15m, 0 < close, ohlcv_15m, &1/2",  # 收盘价 < 前两根收盘价
                            "close, ohlcv_15m, 0 < low, ohlcv_15m, 1",  # 收盘价 < 前一根最低价
                        ],
                    ),
                ],
            ),
            # 2. 震荡策略 (ADX < Threshold)
            SignalGroup(
                logic=LogicOp.AND,
                comparisons=[
                    "adx_0_adx, ohlcv_15m, 0 < $adx_threshold",  # 趋势疲弱
                    "rsi_0, ohlcv_15m, 0 > $rsi_overbought",  # RSI超买
                ],
            ),
        ],
    ),
    # 做多离场信号
    exit_long=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # 趋势反转
            "ema_0, ohlcv_15m, 0 < ema_1, ohlcv_15m, 0",
            # 止损 (RSI超买)
            "rsi_0, ohlcv_15m, 0 > $rsi_overbought",
        ],
    ),
    # 做空离场信号
    exit_short=SignalGroup(
        logic=LogicOp.OR,
        comparisons=[
            # 趋势反转
            "ema_0, ohlcv_15m, 0 > ema_1, ohlcv_15m, 0",
            # 止损 (RSI超卖)
            "rsi_0, ohlcv_15m, 0 < $rsi_oversold",
        ],
    ),
)
