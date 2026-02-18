import polars as pl

from py_entry.private_strategies.live.base import LiveStrategyConfig
from py_entry.data_generator import DataGenerationParams
from py_entry.strategies.base import StrategyConfig
from py_entry.trading_bot import LiveStrategyCallbacks
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    Param,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
)

from .test_mocks import MockCallbacks


def _build_mock_ohlcv(rows: int = 300) -> pl.DataFrame:
    """构造最小可运行 OHLCV 数据。"""
    base_ts = 1735689600000
    data = []
    price = 100.0
    for i in range(rows):
        # 使用轻微波动，确保均线交叉类策略可以正常计算。
        close_price = price + ((i % 7) - 3) * 0.2
        open_price = price
        high_price = max(open_price, close_price) + 0.3
        low_price = min(open_price, close_price) - 0.3
        volume = 1000.0 + i
        data.append(
            [
                base_ts + i * 15 * 60 * 1000,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
            ]
        )
        price = close_price

    return pl.DataFrame(
        data,
        schema=["timestamp", "open", "high", "low", "close", "volume"],
        orient="row",
    )


class TestLiveStrategyCallbacks:
    """live 注册策略到 bot 回调桥接测试。"""

    def test_get_strategy_params_from_live_registry(self):
        """默认关闭的 live 策略不应进入机器人参数列表。"""
        callbacks = LiveStrategyCallbacks(
            inner=MockCallbacks(),
            strategy_names=["btc_sma15_live"],
        )
        result = callbacks.get_strategy_params()

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 0

    def test_run_backtest_should_reject_disabled_strategy(self):
        """关闭策略不应被执行，run_backtest 应返回失败。"""
        callbacks = LiveStrategyCallbacks(
            inner=MockCallbacks(),
            strategy_names=["btc_sma15_live"],
        )
        from py_entry.trading_bot.strategy_params import StrategyParams

        params = StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")
        df = _build_mock_ohlcv(rows=320)

        result = callbacks.run_backtest(params, df)
        assert result.success is False
        assert result.message is not None
        assert "未找到 symbol=BTC/USDT" in result.message

    def test_enabled_strategy_should_run_backtest(self, monkeypatch):
        """开启策略应进入执行链路并返回回测结果。"""
        entry = LiveStrategyConfig(
            strategy=StrategyConfig(
                name="enabled_demo",
                description="enabled demo",
                data_config=DataGenerationParams(
                    timeframes=["15m"],
                    start_time=None,
                    num_bars=320,
                    base_data_key="ohlcv_15m",
                ),
                indicators_params={
                    "ohlcv_15m": {
                        "sma_fast": {"period": Param(8)},
                        "sma_slow": {"period": Param(21)},
                    }
                },
                signal_params={},
                backtest_params=BacktestParams(),
                signal_template=SignalTemplate(
                    entry_long=SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=[
                            "sma_fast, ohlcv_15m, 0 x> sma_slow, ohlcv_15m, 0"
                        ],
                    ),
                    entry_short=SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=[
                            "sma_fast, ohlcv_15m, 0 x< sma_slow, ohlcv_15m, 0"
                        ],
                    ),
                ),
                engine_settings=SettingContainer(
                    execution_stage=ExecutionStage.Performance,
                ),
            ),
            enabled=True,
            base_data_key="ohlcv_15m",
            symbol="BTC/USDT",
        )

        monkeypatch.setattr(
            LiveStrategyCallbacks,
            "_load_live_entries",
            lambda self, _: [entry],
        )

        callbacks = LiveStrategyCallbacks(inner=MockCallbacks())
        params_result = callbacks.get_strategy_params()
        assert params_result.success is True
        assert params_result.data is not None
        assert len(params_result.data) == 1

        params = params_result.data[0]
        df = _build_mock_ohlcv(rows=320)
        result = callbacks.run_backtest(params, df)
        assert result.success is True, result.message
        assert result.data is not None
        assert result.data.height == 320

    def test_should_raise_when_duplicate_symbol_enabled(self, monkeypatch):
        """同一 symbol 多策略启用时必须直接报错。"""
        entry_a = LiveStrategyConfig(
            strategy=StrategyConfig(
                name="enabled_a",
                description="enabled a",
                data_config=DataGenerationParams(
                    timeframes=["15m"],
                    start_time=None,
                    num_bars=320,
                    base_data_key="ohlcv_15m",
                ),
                indicators_params={
                    "ohlcv_15m": {
                        "sma_fast": {"period": Param(8)},
                        "sma_slow": {"period": Param(21)},
                    }
                },
                signal_params={},
                backtest_params=BacktestParams(),
                signal_template=SignalTemplate(
                    entry_long=SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=[
                            "sma_fast, ohlcv_15m, 0 x> sma_slow, ohlcv_15m, 0"
                        ],
                    ),
                ),
                engine_settings=SettingContainer(
                    execution_stage=ExecutionStage.Performance,
                ),
            ),
            enabled=True,
            base_data_key="ohlcv_15m",
            symbol="BTC/USDT",
        )

        entry_b = LiveStrategyConfig(
            strategy=StrategyConfig(
                name="enabled_b",
                description="enabled b",
                data_config=DataGenerationParams(
                    timeframes=["1h"],
                    start_time=None,
                    num_bars=320,
                    base_data_key="ohlcv_1h",
                ),
                indicators_params={
                    "ohlcv_1h": {
                        "sma_fast": {"period": Param(8)},
                        "sma_slow": {"period": Param(21)},
                    }
                },
                signal_params={},
                backtest_params=BacktestParams(),
                signal_template=SignalTemplate(
                    entry_long=SignalGroup(
                        logic=LogicOp.AND,
                        comparisons=["sma_fast, ohlcv_1h, 0 x> sma_slow, ohlcv_1h, 0"],
                    ),
                ),
                engine_settings=SettingContainer(
                    execution_stage=ExecutionStage.Performance,
                ),
            ),
            enabled=True,
            base_data_key="ohlcv_1h",
            symbol="BTC/USDT",
        )

        monkeypatch.setattr(
            LiveStrategyCallbacks,
            "_load_live_entries",
            lambda self, _: [entry_a, entry_b],
        )

        try:
            LiveStrategyCallbacks(inner=MockCallbacks())
            raise AssertionError("预期应抛出 ValueError，但未抛出")
        except ValueError as exc:
            assert "同一 symbol 只能对应一个启用策略" in str(exc)
