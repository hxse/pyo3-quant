"""场景: 跨数据源和周期对比 - 配置

测试目标：验证不同数据源(ohlcv, ha, renko)和不同周期(15m, 1h, 4h)之间的指标对比
核心测试内容：
- OHLCV 15m SMA vs Renko 1h Close
- HA 15m Close vs OHLCV 4h EMA
- Renko 15m SMA vs HA 1h Close
"""

from py_entry.data_conversion.types import (
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
)

DESCRIPTION = "测试跨数据源和周期的指标对比：ohlcv vs ha vs renko"

# 为不同数据源配置指标
INDICATORS_PARAMS: IndicatorsParams = {
    # OHLCV数据源
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(20)},
    },
    "ohlcv_4h": {
        "ema_0": {"period": Param.create(10)},
    },
    # HA数据源
    # "ha_15m": {},  # 只用close
    # "ha_1h": {},  # 只用close
    # Renko数据源
    "renko_15m": {
        "sma_0": {"period": Param.create(20)},
    },
    # "renko_1h": {},  # 只用close
}

SIGNAL_PARAMS: SignalParams = {}

# 测试策略：
# Enter Long:
#   1. ohlcv_15m SMA > renko_1h close  (跨数据源跨周期)
#   2. ha_15m close > ohlcv_4h EMA     (跨数据源跨周期)
#   3. renko_15m SMA > ha_1h close     (跨数据源跨周期)
#
# Exit Long:
#   1. ohlcv_15m SMA < renko_1h close
#
# Enter Short:
#   1. ha_15m close < ohlcv_4h EMA
#
# Exit Short:
#   1. renko_15m SMA < ha_1h close

SIGNAL_TEMPLATE = SignalTemplate(
    name="cross_data_source_test",
    enter_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_0, ohlcv_15m, 0 > close, renko_1h, 0",  # ohlcv指标 vs renko价格
            "close, ha_15m, 0 > ema_0, ohlcv_4h, 0",  # ha价格 vs ohlcv指标
            "sma_0, renko_15m, 0 > close, ha_1h, 0",  # renko指标 vs ha价格
        ],
    ),
    exit_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_0, ohlcv_15m, 0 < close, renko_1h, 0",
        ],
    ),
    enter_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "close, ha_15m, 0 < ema_0, ohlcv_4h, 0",
        ],
    ),
    exit_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_0, renko_15m, 0 < close, ha_1h, 0",
        ],
    ),
)
