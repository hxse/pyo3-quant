import unittest
from datetime import timedelta

import pandas as pd

from py_entry.scanner._scan_runtime import _collect_updated_watch_klines
from py_entry.scanner._scan_runtime import build_runtime_specs
from py_entry.scanner._scan_runtime import scan_symbol
from py_entry.scanner.config import ScanLevel, ScannerConfig, TimeframeConfig
from py_entry.scanner.strategies.base import ScanContext
from py_entry.scanner.strategies.base import StrategyBase
from py_entry.scanner.strategies.dual_pair_minimal_scan import (
    DualPairMinimalScanStrategy,
)
from py_entry.scanner.timeframe_resolver import get_min_watch_timeframe


def make_mock_df(
    prices: list[float],
    end_time: str = "2023-01-01 09:00:00",
    interval_seconds: int = 300,
) -> pd.DataFrame:
    """构造用于 scanner runtime 测试的确定性 K 线数据。"""
    length = len(prices)
    end_ts = pd.Timestamp(end_time)
    times = [
        end_ts - timedelta(seconds=(length - 1 - i) * interval_seconds)
        for i in range(length)
    ]
    times_ns = [t.value for t in times]

    df = pd.DataFrame()
    df["datetime"] = times_ns
    df["close"] = pd.Series(prices, dtype="float64")
    df["open"] = df["close"]
    df["high"] = df["close"] + 0.5
    df["low"] = df["close"] - 0.5
    df["volume"] = 1000.0
    df["open_interest"] = 5000.0
    return df


class RecordingStrategy(StrategyBase):
    """测试专用策略：只记录 runtime 传入的上下文，不做真实回测。"""

    def __init__(
        self,
        name: str,
        watch_levels: list[ScanLevel] | None = None,
        timeframes: list[TimeframeConfig] | None = None,
    ):
        self.name = name
        self._watch_levels = watch_levels or [ScanLevel.TRIGGER]
        self._timeframes = timeframes
        self.updated_history: list[set[ScanLevel]] = []

    def get_timeframes(self, defaults: list[TimeframeConfig]) -> list[TimeframeConfig]:
        source = self._timeframes or defaults
        return [tf.model_copy(deep=True) for tf in source]

    def get_watch_levels(self) -> list[ScanLevel]:
        return list(self._watch_levels)

    def scan(self, ctx: ScanContext):
        self.updated_history.append(set(ctx.updated_levels))
        return None


class SpyDualPairMinimalScanStrategy(DualPairMinimalScanStrategy):
    """测试专用子类：截断真实回测，只观察配对分发是否正确。"""

    def __init__(self):
        self.called_pairs: list[tuple[ScanLevel, ScanLevel]] = []

    def _scan_pair(
        self,
        ctx: ScanContext,
        lower_level: ScanLevel,
        higher_level: ScanLevel,
    ):
        self.called_pairs.append((lower_level, higher_level))
        return None


class FakeDataSource:
    """测试专用数据源：记录取数调用，不访问外部网络。"""

    def __init__(self):
        self.calls: list[tuple[str, int, int]] = []

    def get_klines(
        self, symbol: str, duration_seconds: int, data_length: int = 200
    ) -> pd.DataFrame:
        self.calls.append((symbol, duration_seconds, data_length))
        prices = [100.0] * max(data_length, 200)
        return make_mock_df(prices, interval_seconds=duration_seconds)

    def wait(self, seconds: float) -> None:
        return None

    def get_underlying_symbol(self, symbol: str) -> str:
        return f"{symbol}.REAL"

    def close(self) -> None:
        return None


class SequenceDataSource(FakeDataSource):
    """测试专用数据源：按预设序列返回不同周期的时间戳。"""

    def __init__(self, sequences: dict[int, list[str]]):
        super().__init__()
        self._sequences = {
            duration: list(values) for duration, values in sequences.items()
        }
        self._indices: dict[int, int] = {duration: 0 for duration in sequences}

    def get_klines(
        self, symbol: str, duration_seconds: int, data_length: int = 200
    ) -> pd.DataFrame:
        self.calls.append((symbol, duration_seconds, data_length))
        values = self._sequences.get(duration_seconds)
        if not values:
            return make_mock_df(
                [100.0] * max(data_length, 200), interval_seconds=duration_seconds
            )

        index = self._indices[duration_seconds]
        if index < len(values) - 1:
            self._indices[duration_seconds] = index + 1
        return make_mock_df(
            [100.0] * max(data_length, 200),
            end_time=values[index],
            interval_seconds=duration_seconds,
        )


def build_context_for_strategy(
    config: ScannerConfig,
    strategy: StrategyBase,
    updated_levels: set[ScanLevel],
) -> ScanContext:
    """按策略画像构造上下文，便于直接测试 scan 分发逻辑。"""
    effective_timeframes = strategy.get_timeframes(config.timeframes)
    timeframes_by_key = {tf.storage_key: tf for tf in effective_timeframes}
    level_to_tf = {tf.level: tf.storage_key for tf in effective_timeframes}
    klines = {
        tf.storage_key: make_mock_df([100.0] * 240, interval_seconds=tf.seconds)
        for tf in effective_timeframes
    }
    return ScanContext(
        symbol="KQ.m@DCE.i",
        klines=klines,
        timeframes=timeframes_by_key,
        level_to_tf=level_to_tf,
        updated_levels=updated_levels,
    )


class TestScannerRuntime(unittest.TestCase):
    """覆盖 scanner runtime 的画像解析、并集取数与更新分发。"""

    def setUp(self):
        self.config = ScannerConfig()

    def test_build_runtime_specs_keeps_default_and_override_profiles(self):
        """默认策略继续使用 1h，minimal 策略单独覆盖为 30m。"""
        default_strategy = RecordingStrategy(name="default_profile")
        minimal_strategy = DualPairMinimalScanStrategy()

        runtime_specs, required_timeframes = build_runtime_specs(
            self.config, [default_strategy, minimal_strategy]
        )

        self.assertEqual(len(runtime_specs), 2)
        self.assertEqual(
            runtime_specs[0].level_to_tf[ScanLevel.WAVE],
            "1h_index",
        )
        self.assertEqual(
            runtime_specs[1].level_to_tf[ScanLevel.WAVE],
            "30m_main",
        )
        self.assertEqual(
            set(required_timeframes.keys()),
            {"5m_main", "30m_main", "1h_index", "1d_index", "1w_index"},
        )

        min_watch_tf = get_min_watch_timeframe(runtime_specs, required_timeframes)
        self.assertEqual(min_watch_tf.storage_key, "5m_main")

    def test_scan_symbol_fetches_required_union_once(self):
        """同一 symbol 的并集数据只拉一次，不按策略重复取数。"""
        default_strategy = RecordingStrategy(name="default_profile")
        override_timeframes = [
            TimeframeConfig(level=ScanLevel.TRIGGER, name="5m", seconds=5 * 60),
            TimeframeConfig(level=ScanLevel.WAVE, name="30m", seconds=30 * 60),
            TimeframeConfig(
                level=ScanLevel.TREND, name="1d", seconds=24 * 3600, use_index=True
            ),
            TimeframeConfig(
                level=ScanLevel.MACRO, name="1w", seconds=7 * 24 * 3600, use_index=True
            ),
        ]
        override_strategy = RecordingStrategy(
            name="override_profile",
            timeframes=override_timeframes,
        )
        runtime_specs, required_timeframes = build_runtime_specs(
            self.config, [default_strategy, override_strategy]
        )
        data_source = FakeDataSource()

        scan_symbol(
            symbol="KQ.m@DCE.i",
            config=self.config,
            data_source=data_source,
            runtime_specs=runtime_specs,
            required_timeframes=required_timeframes,
        )

        self.assertEqual(len(data_source.calls), 5)
        self.assertEqual(
            {duration for _, duration, _ in data_source.calls},
            {5 * 60, 30 * 60, 60 * 60, 24 * 3600, 7 * 24 * 3600},
        )
        self.assertEqual(
            {symbol for symbol, _, _ in data_source.calls},
            {"KQ.m@DCE.i", "KQ.i@DCE.i"},
        )

    def test_scan_symbol_only_fetches_missing_when_watch_klines_preloaded(self):
        """若外层已预取 watch 周期，scan_symbol 只补拉剩余缺失周期。"""
        default_strategy = RecordingStrategy(name="default_profile")
        override_timeframes = [
            TimeframeConfig(level=ScanLevel.TRIGGER, name="5m", seconds=5 * 60),
            TimeframeConfig(level=ScanLevel.WAVE, name="30m", seconds=30 * 60),
            TimeframeConfig(
                level=ScanLevel.TREND, name="1d", seconds=24 * 3600, use_index=True
            ),
            TimeframeConfig(
                level=ScanLevel.MACRO, name="1w", seconds=7 * 24 * 3600, use_index=True
            ),
        ]
        override_strategy = RecordingStrategy(
            name="override_profile",
            timeframes=override_timeframes,
        )
        runtime_specs, required_timeframes = build_runtime_specs(
            self.config, [default_strategy, override_strategy]
        )
        preloaded_klines = {
            storage_key: make_mock_df([100.0] * 240, interval_seconds=tf.seconds)
            for storage_key, tf in required_timeframes.items()
            if storage_key in {"5m_main", "30m_main"}
        }
        data_source = FakeDataSource()

        scan_symbol(
            symbol="KQ.m@DCE.i",
            config=self.config,
            data_source=data_source,
            runtime_specs=runtime_specs,
            required_timeframes=required_timeframes,
            preloaded_klines=preloaded_klines,
            updated_storage_keys={"5m_main"},
        )

        self.assertEqual(len(data_source.calls), 3)
        self.assertEqual(
            {duration for _, duration, _ in data_source.calls},
            {60 * 60, 24 * 3600, 7 * 24 * 3600},
        )

    def test_collect_updated_watch_klines_only_polls_min_watch_on_idle_cycle(self):
        """未出现最小周期新 bar 时，不应补查其他 watch 周期。"""
        base_tf = TimeframeConfig(level=ScanLevel.TRIGGER, name="5m", seconds=5 * 60)
        wave_tf = TimeframeConfig(level=ScanLevel.WAVE, name="30m", seconds=30 * 60)
        watch_timeframes = {
            base_tf.storage_key: base_tf,
            wave_tf.storage_key: wave_tf,
        }
        base_df = make_mock_df([100.0] * 240, interval_seconds=base_tf.seconds)
        last_times = {
            base_tf.storage_key: int(base_df.iloc[-1]["datetime"]),
            wave_tf.storage_key: 0,
        }
        data_source = SequenceDataSource(
            {
                5 * 60: ["2023-01-01 09:00:00"],
                30 * 60: ["2023-01-01 09:00:00"],
            }
        )

        preloaded_klines, updated_storage_keys = _collect_updated_watch_klines(
            symbol="KQ.m@DCE.i",
            config=self.config,
            data_source=data_source,
            base_watch_tf=base_tf,
            watch_timeframes=watch_timeframes,
            last_times=last_times,
        )

        self.assertEqual(preloaded_klines, {})
        self.assertEqual(updated_storage_keys, set())
        self.assertEqual(len(data_source.calls), 1)
        self.assertEqual(data_source.calls[0][1], 5 * 60)

    def test_collect_updated_watch_klines_fetches_other_watchs_after_min_tick(self):
        """最小周期出现新 bar 后，才补查其他 watch 周期并回传更新集合。"""
        base_tf = TimeframeConfig(level=ScanLevel.TRIGGER, name="5m", seconds=5 * 60)
        wave_tf = TimeframeConfig(level=ScanLevel.WAVE, name="30m", seconds=30 * 60)
        watch_timeframes = {
            base_tf.storage_key: base_tf,
            wave_tf.storage_key: wave_tf,
        }
        last_times = {
            base_tf.storage_key: int(
                make_mock_df(
                    [100.0] * 240,
                    end_time="2023-01-01 09:00:00",
                    interval_seconds=base_tf.seconds,
                ).iloc[-1]["datetime"]
            ),
            wave_tf.storage_key: int(
                make_mock_df(
                    [100.0] * 240,
                    end_time="2023-01-01 09:00:00",
                    interval_seconds=wave_tf.seconds,
                ).iloc[-1]["datetime"]
            ),
        }
        data_source = SequenceDataSource(
            {
                5 * 60: ["2023-01-01 09:05:00"],
                30 * 60: ["2023-01-01 09:30:00"],
            }
        )

        preloaded_klines, updated_storage_keys = _collect_updated_watch_klines(
            symbol="KQ.m@DCE.i",
            config=self.config,
            data_source=data_source,
            base_watch_tf=base_tf,
            watch_timeframes=watch_timeframes,
            last_times=last_times,
        )

        self.assertEqual(set(preloaded_klines.keys()), {"5m_main", "30m_main"})
        self.assertEqual(updated_storage_keys, {"5m_main", "30m_main"})
        self.assertEqual(
            [duration for _, duration, _ in data_source.calls], [5 * 60, 30 * 60]
        )

    def test_scan_symbol_dispatches_only_to_matching_watch_levels(self):
        """只有命中更新周期的策略才会被执行。"""
        trigger_strategy = RecordingStrategy(
            name="trigger_only",
            watch_levels=[ScanLevel.TRIGGER],
        )
        wave_strategy = RecordingStrategy(
            name="wave_only",
            watch_levels=[ScanLevel.WAVE],
            timeframes=[
                TimeframeConfig(level=ScanLevel.TRIGGER, name="5m", seconds=5 * 60),
                TimeframeConfig(level=ScanLevel.WAVE, name="30m", seconds=30 * 60),
                TimeframeConfig(
                    level=ScanLevel.TREND,
                    name="1d",
                    seconds=24 * 3600,
                    use_index=True,
                ),
                TimeframeConfig(
                    level=ScanLevel.MACRO,
                    name="1w",
                    seconds=7 * 24 * 3600,
                    use_index=True,
                ),
            ],
        )
        runtime_specs, required_timeframes = build_runtime_specs(
            self.config, [trigger_strategy, wave_strategy]
        )
        preloaded_klines = {
            storage_key: make_mock_df([100.0] * 240, interval_seconds=tf.seconds)
            for storage_key, tf in required_timeframes.items()
        }

        scan_symbol(
            symbol="KQ.m@DCE.i",
            config=self.config,
            data_source=FakeDataSource(),
            runtime_specs=runtime_specs,
            required_timeframes=required_timeframes,
            preloaded_klines=preloaded_klines,
            updated_storage_keys={"5m_main"},
        )

        self.assertEqual(trigger_strategy.updated_history, [{ScanLevel.TRIGGER}])
        self.assertEqual(wave_strategy.updated_history, [])

    def test_dual_pair_minimal_scan_only_evaluates_updated_pairs(self):
        """minimal 策略只评估本次刚更新的那一组周期组合。"""
        strategy = SpyDualPairMinimalScanStrategy()

        trigger_ctx = build_context_for_strategy(
            self.config,
            strategy,
            updated_levels={ScanLevel.TRIGGER},
        )
        strategy.scan(trigger_ctx)
        self.assertEqual(
            strategy.called_pairs,
            [(ScanLevel.TRIGGER, ScanLevel.TREND)],
        )

        strategy.called_pairs = []
        wave_ctx = build_context_for_strategy(
            self.config,
            strategy,
            updated_levels={ScanLevel.WAVE},
        )
        strategy.scan(wave_ctx)
        self.assertEqual(
            strategy.called_pairs,
            [(ScanLevel.WAVE, ScanLevel.MACRO)],
        )

        strategy.called_pairs = []
        both_ctx = build_context_for_strategy(
            self.config,
            strategy,
            updated_levels={ScanLevel.TRIGGER, ScanLevel.WAVE},
        )
        strategy.scan(both_ctx)
        self.assertEqual(
            strategy.called_pairs,
            [
                (ScanLevel.TRIGGER, ScanLevel.TREND),
                (ScanLevel.WAVE, ScanLevel.MACRO),
            ],
        )


if __name__ == "__main__":
    unittest.main()
