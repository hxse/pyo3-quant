import polars as pl

from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.io.types import RequestConfig
from py_entry.strategies.base import LiveMeta, StrategyConfig
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
    step_ms = 15 * 60 * 1000

    # 中文注释：先构造逐 bar 的增量，再用累计和得到 close；open 用 close.shift(1) 对齐。
    delta_df = pl.DataFrame({"i": pl.int_range(0, rows, eager=True)}).with_columns(
        (((pl.col("i") % 7) - 3).cast(pl.Float64) * 0.2).alias("__delta")
    )
    close_df = delta_df.with_columns(
        (100.0 + pl.col("__delta").cum_sum()).alias("close"),
        (pl.lit(base_ts) + pl.col("i") * step_ms).alias("timestamp"),
        (1000.0 + pl.col("i").cast(pl.Float64)).alias("volume"),
    )
    ohlcv = close_df.with_columns(
        pl.col("close").shift(1).fill_null(100.0).alias("open")
    ).with_columns(
        pl.max_horizontal(["open", "close"]).add(0.3).alias("high"),
        pl.min_horizontal(["open", "close"]).sub(0.3).alias("low"),
    )
    return ohlcv.select(["timestamp", "open", "high", "low", "close", "volume"])


def _build_live_fetch_config(
    *,
    symbol: str,
    base_data_key: str,
    timeframe: str,
) -> OhlcvDataFetchConfig:
    """构造 live 侧最小 OhlcvDataFetchConfig。"""
    return OhlcvDataFetchConfig(
        config=RequestConfig.create(),
        exchange_name="binance",
        market="future",
        symbol=symbol,
        timeframes=[timeframe],
        since=None,
        limit=320,
        enable_cache=False,
        mode="live",
        base_data_key=base_data_key,
    )


class TestLiveStrategyCallbacks:
    """live 注册策略到 bot 回调桥接测试。"""

    def test_get_strategy_params_from_live_registry(self):
        """默认关闭的 live 策略不应进入机器人参数列表。"""
        callbacks = LiveStrategyCallbacks(
            inner=MockCallbacks(),
            strategy_names=["sma_2tf"],
        )
        result = callbacks.get_strategy_params()

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 0

    def test_run_backtest_should_reject_disabled_strategy(self):
        """关闭策略不应被执行，run_backtest 应返回失败。"""
        callbacks = LiveStrategyCallbacks(
            inner=MockCallbacks(),
            strategy_names=["sma_2tf"],
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
        entry = StrategyConfig(
            name="enabled_demo",
            description="enabled demo",
            data_config=_build_live_fetch_config(
                symbol="BTC/USDT",
                base_data_key="ohlcv_15m",
                timeframe="15m",
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
                    comparisons=["sma_fast, ohlcv_15m, 0 x> sma_slow, ohlcv_15m, 0"],
                ),
                entry_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=["sma_fast, ohlcv_15m, 0 x< sma_slow, ohlcv_15m, 0"],
                ),
            ),
            engine_settings=SettingContainer(
                execution_stage=ExecutionStage.Performance,
            ),
            live_meta=LiveMeta(enabled=True),
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
        entry_a = StrategyConfig(
            name="enabled_a",
            description="enabled a",
            data_config=_build_live_fetch_config(
                symbol="BTC/USDT",
                base_data_key="ohlcv_15m",
                timeframe="15m",
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
                    comparisons=["sma_fast, ohlcv_15m, 0 x> sma_slow, ohlcv_15m, 0"],
                ),
            ),
            engine_settings=SettingContainer(
                execution_stage=ExecutionStage.Performance,
            ),
            live_meta=LiveMeta(enabled=True),
        )

        entry_b = StrategyConfig(
            name="enabled_b",
            description="enabled b",
            data_config=_build_live_fetch_config(
                symbol="BTC/USDT",
                base_data_key="ohlcv_1h",
                timeframe="1h",
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
            live_meta=LiveMeta(enabled=True),
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
