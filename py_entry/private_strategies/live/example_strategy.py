"""
示例 live 策略注册。

该策略在 private live 内自定义参数，默认关闭交易（enabled=False）。
"""

from py_entry.private_strategies.live import register_live_strategy
from py_entry.private_strategies.live.base import LiveStrategyConfig
from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.io import load_local_config
from py_entry.strategies.base import StrategyConfig
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    Param,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
)

BASE_DATA_KEY = "ohlcv_15m"


@register_live_strategy("btc_sma15_live")
def get_live_config() -> LiveStrategyConfig:
    """返回一个最小可运行的 live 策略配置。"""
    # 研究/回测统一走真实数据源，避免模拟数据偏差。
    request_config = load_local_config()
    real_data_config = OhlcvDataFetchConfig(
        config=request_config,
        exchange_name="binance",
        market="future",
        symbol="BTC/USDT",
        timeframes=["15m"],
        since=get_utc_timestamp_ms("2025-12-01 00:00:00"),
        limit=5000,
        enable_cache=True,
        mode="live",
        base_data_key=BASE_DATA_KEY,
    )

    indicators = {
        BASE_DATA_KEY: {
            "sma_fast": {"period": Param(8)},
            "sma_slow": {"period": Param(21)},
        }
    }
    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast, {BASE_DATA_KEY}, 0 x> sma_slow, {BASE_DATA_KEY}, 0"
            ],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                f"sma_fast, {BASE_DATA_KEY}, 0 x< sma_slow, {BASE_DATA_KEY}, 0"
            ],
        ),
    )
    strategy = StrategyConfig(
        name="btc_sma15_live",
        description="BTC 15m SMA 交叉 live 策略示例（默认关闭）",
        data_config=real_data_config,
        indicators_params=indicators,
        signal_params={},
        backtest_params=BacktestParams(),
        signal_template=signal_template,
        engine_settings=SettingContainer(execution_stage=ExecutionStage.Performance),
    )
    return LiveStrategyConfig(
        strategy=strategy,
        enabled=False,
        base_data_key=BASE_DATA_KEY,
        symbol="BTC/USDT",
        exchange_name="binance",
        market="future",
        mode="live",
        position_size_pct=0.2,
        leverage=2,
        settlement_currency="USDT",
    )
