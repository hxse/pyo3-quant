import polars as pl
import pytest
from pathlib import Path

from py_entry.strategy_hub.core.spec import SearchSpaceSpec, VariantPayload
from py_entry.strategy_hub.core.spec_loader import load_spec
from py_entry.strategy_hub.registry import RegistryResolvedItem
from py_entry.trading_bot import LiveStrategyCallbacks
from py_entry.types import LogicOp, SignalGroup, SignalTemplate

from .test_mocks import MockCallbacks


def _build_mock_ohlcv(rows: int = 300, *, step_minutes: int = 15) -> pl.DataFrame:
    """构造最小可运行 OHLCV 数据。"""
    base_ts = 1735689600000
    step_ms = step_minutes * 60 * 1000

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


def _patch_entries(monkeypatch, entries: list[SearchSpaceSpec]) -> None:
    """注入最小注册器加载逻辑，并补齐 meta/params_override 侧效果。"""

    def _loader(self, _path: str):
        loaded: list[SearchSpaceSpec] = []
        for entry in entries:
            data_cfg = self._require_ohlcv_data_config(entry)
            key = (data_cfg.symbol, data_cfg.base_data_key)
            self._entry_by_key[key] = entry
            self._entry_meta_by_key[key] = RegistryResolvedItem(
                strategy_name=entry.name,
                strategy_version=entry.version,
                strategy_module=f"py_entry.strategy_hub.search_spaces.{entry.name}",
                symbol=data_cfg.symbol,
                mode="backtest",
                param_source="backtest_default",
                params={},
                start_time_ms=0,
                base_data_key=data_cfg.base_data_key,
                enabled=True,
                position_size_pct=1.0,
                leverage=1,
            )
            self._params_override_by_key[key] = self._build_params_override(
                entry,
                {},
                ctx=(
                    f"strategy={entry.name}, symbol={data_cfg.symbol}, "
                    f"base_data_key={data_cfg.base_data_key}"
                ),
            )
            loaded.append(entry)
        return loaded

    monkeypatch.setattr(LiveStrategyCallbacks, "_load_entries_from_registry", _loader)


class TestLiveStrategyCallbacks:
    """live 注册策略到 bot 回调桥接测试。"""

    def test_get_strategy_params_from_registry(self, monkeypatch):
        """注册器加载后应返回一条参数。"""
        raw = load_spec("sma_2tf", "search")
        assert isinstance(raw, SearchSpaceSpec)
        spec = SearchSpaceSpec(
            name=raw.name,
            version=raw.version,
            data_config=raw.data_config.model_copy(update={"symbol": "BTC/USDT"}),
            variant=raw.variant,
            engine_settings=raw.engine_settings,
            performance_params=raw.performance_params,
            research=raw.research,
            source=raw.source,
        )
        _patch_entries(monkeypatch, [spec])
        callbacks = LiveStrategyCallbacks(
            inner=MockCallbacks(),
        )
        result = callbacks.get_strategy_params()

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0].symbol == "BTC/USDT"

    def test_run_backtest_should_reject_unknown_pair(self, monkeypatch):
        """未知 symbol/base_data_key 应被拒绝。"""
        # 中文注释：该测试只验证 key 匹配失败分支，不依赖真实注册器文件。
        raw = load_spec("sma_2tf", "search")
        assert isinstance(raw, SearchSpaceSpec)
        spec = SearchSpaceSpec(
            name=raw.name,
            version=raw.version,
            data_config=raw.data_config.model_copy(update={"symbol": "BTC/USDT"}),
            variant=raw.variant,
            engine_settings=raw.engine_settings,
            performance_params=raw.performance_params,
            research=raw.research,
            source=raw.source,
        )
        _patch_entries(monkeypatch, [spec])
        callbacks = LiveStrategyCallbacks(
            inner=MockCallbacks(),
        )
        from py_entry.trading_bot.strategy_params import StrategyParams

        params = StrategyParams(base_data_key="ohlcv_15m", symbol="ETH/USDT")
        df = _build_mock_ohlcv(rows=320, step_minutes=30)

        result = callbacks.run_backtest(params, df)
        assert result.success is False
        assert result.message is not None
        assert "未找到 symbol=ETH/USDT" in result.message

    def test_strategy_should_run_backtest(self, monkeypatch):
        """策略应进入执行链路并返回回测结果。"""
        # 中文注释：该用例只验证执行链路可运行，构造单周期 live 搜索策略避免多周期依赖。
        raw = load_spec("sma_2tf", "search")
        assert isinstance(raw, SearchSpaceSpec)
        slim_variant = VariantPayload(
            indicators_params={
                "ohlcv_30m": {
                    "sma_fast_base": raw.variant.indicators_params["ohlcv_30m"][
                        "sma_fast_base"
                    ],
                    "sma_slow_base": raw.variant.indicators_params["ohlcv_30m"][
                        "sma_slow_base"
                    ],
                }
            },
            signal_params=raw.variant.signal_params,
            backtest_params=raw.variant.backtest_params,
            signal_template=SignalTemplate(
                entry_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "sma_fast_base, ohlcv_30m, 0 > sma_slow_base, ohlcv_30m, 0"
                    ],
                ),
                entry_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "sma_fast_base, ohlcv_30m, 0 < sma_slow_base, ohlcv_30m, 0"
                    ],
                ),
                exit_long=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "sma_fast_base, ohlcv_30m, 0 < sma_slow_base, ohlcv_30m, 0"
                    ],
                ),
                exit_short=SignalGroup(
                    logic=LogicOp.AND,
                    comparisons=[
                        "sma_fast_base, ohlcv_30m, 0 > sma_slow_base, ohlcv_30m, 0"
                    ],
                ),
            ),
        )
        slim_spec = SearchSpaceSpec(
            name=raw.name,
            version=raw.version,
            data_config=raw.data_config.model_copy(
                update={
                    "symbol": "BTC/USDT",
                    "timeframes": ["30m"],
                    "base_data_key": "ohlcv_30m",
                }
            ),
            variant=slim_variant,
            engine_settings=raw.engine_settings,
            performance_params=raw.performance_params,
            research=raw.research,
            source=raw.source,
        )
        _patch_entries(monkeypatch, [slim_spec])
        callbacks = LiveStrategyCallbacks(
            inner=MockCallbacks(),
        )
        params_result = callbacks.get_strategy_params()
        assert params_result.success is True
        assert params_result.data is not None
        assert len(params_result.data) == 1

        params = params_result.data[0]
        df = _build_mock_ohlcv(rows=320, step_minutes=30)
        result = callbacks.run_backtest(params, df)
        assert result.success is True, result.message
        assert result.data is not None
        assert result.data.height == 320

    def test_should_not_repeat_symbol_validation_in_callbacks(self, monkeypatch):
        """同品种校验由注册器负责，callbacks 不重复校验。"""
        spec_a = load_spec("sma_2tf", "search")
        spec_b = load_spec("sma_2tf", "search")
        assert isinstance(spec_a, SearchSpaceSpec)
        assert isinstance(spec_b, SearchSpaceSpec)
        data_a = spec_a.data_config.model_copy(update={"symbol": "BTC/USDT"})
        spec_a = SearchSpaceSpec(
            name=spec_a.name,
            version=spec_a.version,
            data_config=data_a,
            variant=spec_a.variant,
            engine_settings=spec_a.engine_settings,
            performance_params=spec_a.performance_params,
            research=spec_a.research,
            source=spec_a.source,
        )
        data_b = spec_b.data_config.model_copy(
            update={"symbol": "BTC/USDT", "base_data_key": "ohlcv_4h"}
        )
        spec_b = SearchSpaceSpec(
            name=spec_b.name,
            version=spec_b.version,
            data_config=data_b,
            variant=spec_b.variant,
            engine_settings=spec_b.engine_settings,
            performance_params=spec_b.performance_params,
            research=spec_b.research,
            source=spec_b.source,
        )
        _patch_entries(monkeypatch, [spec_a, spec_b])
        callbacks = LiveStrategyCallbacks(inner=MockCallbacks())
        result = callbacks.get_strategy_params()
        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 2

    def test_should_raise_when_registry_path_missing(self, monkeypatch):
        """未配置注册器路径时必须直接报错。"""
        monkeypatch.setattr(
            LiveStrategyCallbacks,
            "_default_registry_path",
            lambda self: Path("/tmp/__not_exists_registry__.json"),
        )
        try:
            LiveStrategyCallbacks(inner=MockCallbacks())
            raise AssertionError("预期应抛出 ValueError，但未抛出")
        except ValueError as exc:
            assert "注册器文件不存在" in str(exc)

    def test_parse_signal_should_passthrough_inner(self, monkeypatch):
        """parse_signal 必须原样透传给 inner。"""

        raw = load_spec("sma_2tf", "search")
        assert isinstance(raw, SearchSpaceSpec)
        spec = SearchSpaceSpec(
            name=raw.name,
            version=raw.version,
            data_config=raw.data_config.model_copy(update={"symbol": "BTC/USDT"}),
            variant=raw.variant,
            engine_settings=raw.engine_settings,
            performance_params=raw.performance_params,
            research=raw.research,
            source=raw.source,
        )
        _patch_entries(monkeypatch, [spec])
        inner = MockCallbacks()
        callbacks = LiveStrategyCallbacks(inner=inner)
        params_result = callbacks.get_strategy_params()
        assert params_result.data is not None
        params = params_result.data[0]
        result = callbacks.parse_signal(_build_mock_ohlcv(rows=40), params, index=-2)

        assert result.success is True
        assert any(
            call["method"] == "parse_signal" and call["index"] == -2
            for call in inner.call_log
        )

    def test_getattr_should_delegate_to_inner(self, monkeypatch):
        """未覆写方法应通过 __getattr__ 委托给 inner。"""

        raw = load_spec("sma_2tf", "search")
        assert isinstance(raw, SearchSpaceSpec)
        spec = SearchSpaceSpec(
            name=raw.name,
            version=raw.version,
            data_config=raw.data_config.model_copy(update={"symbol": "BTC/USDT"}),
            variant=raw.variant,
            engine_settings=raw.engine_settings,
            performance_params=raw.performance_params,
            research=raw.research,
            source=raw.source,
        )
        _patch_entries(monkeypatch, [spec])
        inner = MockCallbacks()
        callbacks = LiveStrategyCallbacks(inner=inner)

        result = callbacks.fetch_balance("binance", "future", "sandbox")
        assert result.success is True
        assert any(call["method"] == "fetch_balance" for call in inner.call_log)

    def test_build_params_override_should_raise_contextual_error(self, monkeypatch):
        """参数名错误时应返回带上下文的可定位报错。"""

        raw = load_spec("sma_2tf", "search")
        assert isinstance(raw, SearchSpaceSpec)
        spec = SearchSpaceSpec(
            name=raw.name,
            version=raw.version,
            data_config=raw.data_config.model_copy(update={"symbol": "BTC/USDT"}),
            variant=raw.variant,
            engine_settings=raw.engine_settings,
            performance_params=raw.performance_params,
            research=raw.research,
            source=raw.source,
        )
        _patch_entries(monkeypatch, [spec])
        callbacks = LiveStrategyCallbacks(inner=MockCallbacks())

        data_key = next(iter(spec.variant.indicators_params))
        indicator_name = next(iter(spec.variant.indicators_params[data_key]))
        with pytest.raises(ValueError, match=r"registry\[0\].*indicators"):
            callbacks._build_params_override(
                spec,
                {
                    "indicators": {
                        data_key: {indicator_name: {"__bad_param__": 123}},
                    }
                },
                ctx="registry[0]",
            )

    def test_settlement_currency_should_follow_symbol(self, monkeypatch):
        """结算币种应从 symbol 推导，不能硬编码。"""

        raw = load_spec("sma_2tf", "search")
        assert isinstance(raw, SearchSpaceSpec)
        spec = SearchSpaceSpec(
            name=raw.name,
            version=raw.version,
            data_config=raw.data_config.model_copy(update={"symbol": "BTC/USD:BTC"}),
            variant=raw.variant,
            engine_settings=raw.engine_settings,
            performance_params=raw.performance_params,
            research=raw.research,
            source=raw.source,
        )
        _patch_entries(monkeypatch, [spec])
        callbacks = LiveStrategyCallbacks(inner=MockCallbacks())
        params_result = callbacks.get_strategy_params()
        assert params_result.data is not None
        params = params_result.data[0]

        assert params.settlement_currency == "BTC"
