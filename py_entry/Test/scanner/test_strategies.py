import unittest
import pandas as pd
import numpy as np
from datetime import timedelta
import polars as pl

from py_entry.scanner.config import ScanLevel, ScannerConfig
from py_entry.scanner.strategies.base import ScanContext
from py_entry.scanner.strategies.base import StrategyBase
from py_entry.scanner.strategies.trend import TrendStrategy
from py_entry.scanner.strategies.reversal import ReversalStrategy
from py_entry.scanner.strategies.momentum import MomentumStrategy
from py_entry.scanner.strategies.pullback import PullbackStrategy
from py_entry.scanner.strategies.macd_resonance import MacdResonanceStrategy
from py_entry.scanner.strategies.macd_fallback import MacdFallbackStrategy
from py_entry.scanner.strategies.topdown_ema_bias import TopdownEmaBiasStrategy
from py_entry.scanner.strategies.topdown_ema_alignment_long import (
    TopdownEmaAlignmentLongStrategy,
)
from py_entry.scanner.strategies.dual_pair_minimal_scan import (
    DualPairMinimalScanStrategy,
)


def make_mock_df(
    prices: list[float],
    end_time: str = "2023-01-01 09:00:00",
    interval_seconds: int = 300,
) -> pd.DataFrame:
    """
    构造Mock数据 (以结束时间对齐)
    """
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


class TestEngineStrategies(unittest.TestCase):
    """
    测试基于 Level 架构的新策略
    """

    def setUp(self):
        self.config = ScannerConfig()
        self.trend_strategy = TrendStrategy()
        self.reversal_strategy = ReversalStrategy()
        self.momentum_strategy = MomentumStrategy()
        self.pullback_strategy = PullbackStrategy()
        self.macd_resonance_strategy = MacdResonanceStrategy()
        self.macd_fallback_strategy = MacdFallbackStrategy()
        self.topdown_ema_bias_strategy = TopdownEmaBiasStrategy()
        self.topdown_ema_alignment_long_strategy = TopdownEmaAlignmentLongStrategy()
        self.dual_pair_minimal_scan_strategy = DualPairMinimalScanStrategy()

    def create_context(
        self,
        symbol: str,
        prices_dict: dict[ScanLevel, list[float]],
        strategy: StrategyBase | None = None,
    ) -> ScanContext:
        """助手函数：根据逻辑级别自动构造 ScanContext"""
        effective_timeframes = (
            strategy.get_timeframes(self.config.timeframes)
            if strategy is not None
            else [tf.model_copy(deep=True) for tf in self.config.timeframes]
        )
        level_to_tf = {tf.level: tf.storage_key for tf in effective_timeframes}
        timeframes_by_key = {tf.storage_key: tf for tf in effective_timeframes}

        klines = {}
        for level, prices in prices_dict.items():
            # 查找物理周期配置
            tf_conf = next(tf for tf in effective_timeframes if tf.level == level)
            df = make_mock_df(prices, interval_seconds=tf_conf.seconds)
            klines[tf_conf.storage_key] = df

        return ScanContext(
            symbol=symbol,
            klines=klines,
            timeframes=timeframes_by_key,
            level_to_tf=level_to_tf,
            updated_levels=set(prices_dict.keys()),
        )

    def test_trend_strategy_integrated(self):
        """测试 TrendStrategy 多头共振信号"""
        # 1. 准备各级别的价格数组
        p_macro = (100 * (1.2 ** np.arange(50))).tolist()
        p_trend = (100 * (1.1 ** np.arange(100))).tolist()
        p_wave = (100 * (1.05 ** np.arange(200))).tolist()

        p_trigger_flat = [100.0] * 598
        p_trigger_break = [105.0]
        p_trigger_hold = [105.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        # 2. 语义化构造 Context
        ctx = self.create_context(
            "TEST.TREND",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
        )

        # 3. 运行扫描
        sig = self.trend_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_trend_strategy_crossover(self):
        """测试 TrendStrategy 盘中突破信号"""
        p_macro = (100 * (1.2 ** np.arange(50))).tolist()
        p_trend = (100 * (1.1 ** np.arange(100))).tolist()
        p_wave = (100 * (1.05 ** np.arange(200))).tolist()

        p_trigger_flat = [99.0] * 598
        p_trigger_cross = [102.0]
        p_trigger_pad = [102.0]
        p_trigger = p_trigger_flat + p_trigger_cross + p_trigger_pad

        ctx = self.create_context(
            "TEST.CROSS",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
        )

        sig = self.trend_strategy.scan(ctx)
        self.assertIsNotNone(sig)

    def test_trend_trigger_fail(self):
        """测试 TrendStrategy: 有势无点"""
        p_macro = (100 * (1.2 ** np.arange(50))).tolist()
        p_trend = (100 * (1.1 ** np.arange(100))).tolist()
        p_wave = (100 * (1.05 ** np.arange(200))).tolist()

        p_trigger = (100 * (1.001 ** np.arange(601))).tolist()

        ctx = self.create_context(
            "TEST.TRIG_FAIL",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
        )

        sig = self.trend_strategy.scan(ctx)
        self.assertIsNone(sig)

    def test_reversal_strategy_basics(self):
        """测试 ReversalStrategy 运行无报错"""
        ctx = self.create_context(
            "TEST.REV",
            {
                ScanLevel.TRIGGER: [100.0] * 200,
                ScanLevel.WAVE: [100.0] * 200,
                ScanLevel.TREND: [100.0] * 100,
                ScanLevel.MACRO: [100.0] * 50,
            },
        )
        self.reversal_strategy.scan(ctx)

    def test_momentum_strategy_setup(self):
        """测试 MomentumStrategy"""
        ctx = self.create_context(
            "TEST.MOM",
            {
                ScanLevel.TRIGGER: [100.0] * 200,
                ScanLevel.WAVE: [100.0] * 200,
                ScanLevel.TREND: [100.0] * 100,
                ScanLevel.MACRO: [100.0] * 50,
            },
        )
        self.momentum_strategy.scan(ctx)

    def test_pullback_strategy_setup(self):
        """测试 PullbackStrategy"""
        ctx = self.create_context(
            "TEST.PULL",
            {
                ScanLevel.TRIGGER: [100.0] * 200,
                ScanLevel.WAVE: [100.0] * 200,
                ScanLevel.TREND: [100.0] * 100,
                ScanLevel.MACRO: [100.0] * 50,
            },
        )
        self.pullback_strategy.scan(ctx)

    def test_macd_resonance_strategy_setup(self):
        """测试 MacdResonanceStrategy"""
        ctx = self.create_context(
            "TEST.MACD",
            {
                ScanLevel.TRIGGER: [100.0] * 200,
                ScanLevel.WAVE: [100.0] * 200,
                ScanLevel.TREND: [100.0] * 100,
            },
        )
        self.macd_resonance_strategy.scan(ctx)

    def test_topdown_ema_bias_strategy_weekly_long(self):
        """测试 TopdownEmaBiasStrategy 周线直接定多"""
        p_macro = np.linspace(50.0, 90.0, 120).tolist()
        p_trend = np.linspace(70.0, 110.0, 180).tolist()
        p_wave = np.linspace(100.0, 140.0, 240).tolist()

        p_trigger_flat = [140.0] * 598
        p_trigger_break = [145.0]
        p_trigger_hold = [145.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.TOPDOWN.WEEKLY.LONG",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
        )

        sig = self.topdown_ema_bias_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_topdown_ema_bias_strategy_daily_fallback_long(self):
        """测试 TopdownEmaBiasStrategy 周线不明朗时由日线定多"""
        p_macro = [130.0] * 120
        p_trend = np.linspace(80.0, 120.0, 180).tolist()
        p_wave = np.linspace(100.0, 140.0, 240).tolist()

        p_trigger_flat = [129.0] * 598
        p_trigger_break = [132.0]
        p_trigger_hold = [132.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.TOPDOWN.DAILY.LONG",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
        )

        sig = self.topdown_ema_bias_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_topdown_ema_bias_strategy_weekly_short(self):
        """测试 TopdownEmaBiasStrategy 周线直接定空"""
        p_macro = np.linspace(120.0, 80.0, 120).tolist()
        p_trend = np.linspace(110.0, 70.0, 180).tolist()
        p_wave = np.linspace(100.0, 60.0, 240).tolist()

        p_trigger_flat = [60.0] * 598
        p_trigger_break = [55.0]
        p_trigger_hold = [55.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.TOPDOWN.WEEKLY.SHORT",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
        )

        sig = self.topdown_ema_bias_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "short")

    def test_topdown_ema_alignment_long_strategy_daily_long(self):
        """测试 TopdownEmaAlignmentLongStrategy 日线方向 + 5m 上穿触发"""
        p_macro = [100.0] * 120
        p_trend = np.linspace(80.0, 120.0, 180).tolist()
        p_wave = np.linspace(100.0, 140.0, 240).tolist()

        p_trigger_flat = [99.0] * 598
        p_trigger_break = [130.0]
        p_trigger_hold = [130.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.TOPDOWN.EMA.ALIGN.DAILY",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.topdown_ema_alignment_long_strategy,
        )

        sig = self.topdown_ema_alignment_long_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_topdown_ema_alignment_long_strategy_weekly_long(self):
        """测试 TopdownEmaAlignmentLongStrategy 周线方向 + 5m 上穿触发"""
        p_macro = np.linspace(80.0, 120.0, 120).tolist()
        p_trend = [100.0] * 180
        p_wave = np.linspace(100.0, 140.0, 240).tolist()

        p_trigger_flat = [99.0] * 598
        p_trigger_break = [130.0]
        p_trigger_hold = [130.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.TOPDOWN.EMA.ALIGN.WEEKLY",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.topdown_ema_alignment_long_strategy,
        )

        sig = self.topdown_ema_alignment_long_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_topdown_ema_alignment_long_strategy_opening_bar_long(self):
        """测试 TopdownEmaAlignmentLongStrategy 支持开盘首根站上 EMA20 触发"""
        p_macro = [100.0] * 120
        p_trend = np.linspace(80.0, 120.0, 180).tolist()
        p_wave = np.linspace(100.0, 140.0, 240).tolist()
        # 中文注释：倒数第三根已经在 5m EMA20 上方，避免把这条用例误打成 x> 分支。
        p_trigger = [99.0] * 597 + [115.0, 130.0, 130.0]

        ctx = self.create_context(
            "TEST.TOPDOWN.EMA.ALIGN.OPENING",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.topdown_ema_alignment_long_strategy,
        )

        trigger_storage_key = ctx.get_storage_key(ScanLevel.TRIGGER)
        trigger_df = ctx.klines[trigger_storage_key].copy()
        trigger_df.loc[len(trigger_df) - 2, "datetime"] = trigger_df.loc[
            len(trigger_df) - 3, "datetime"
        ] + int(2 * 60 * 60 * 1e9)
        trigger_df.loc[len(trigger_df) - 1, "datetime"] = trigger_df.loc[
            len(trigger_df) - 2, "datetime"
        ] + int(5 * 60 * 1e9)
        ctx.klines[trigger_storage_key] = trigger_df

        sig = self.topdown_ema_alignment_long_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_topdown_ema_alignment_long_strategy_requires_topdown_bias(self):
        """测试 TopdownEmaAlignmentLongStrategy 在日线和周线都不满足时返回空"""
        ctx = self.create_context(
            "TEST.TOPDOWN.EMA.ALIGN.NONE",
            {
                ScanLevel.MACRO: [100.0] * 120,
                ScanLevel.TREND: [100.0] * 180,
                ScanLevel.WAVE: np.linspace(100.0, 140.0, 240).tolist(),
                ScanLevel.TRIGGER: [99.0] * 598 + [110.0, 110.0],
            },
            strategy=self.topdown_ema_alignment_long_strategy,
        )

        sig = self.topdown_ema_alignment_long_strategy.scan(ctx)
        self.assertIsNone(sig)

    def test_topdown_ema_alignment_long_strategy_requires_hour_filter(self):
        """测试 TopdownEmaAlignmentLongStrategy 在 1h 过滤不满足时返回空"""
        p_macro = [100.0] * 120
        p_trend = np.linspace(80.0, 120.0, 180).tolist()
        p_wave = [100.0] * 240

        p_trigger_flat = [99.0] * 598
        p_trigger_break = [130.0]
        p_trigger_hold = [130.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.TOPDOWN.EMA.ALIGN.HOUR_FAIL",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.topdown_ema_alignment_long_strategy,
        )

        sig = self.topdown_ema_alignment_long_strategy.scan(ctx)
        self.assertIsNone(sig)

    def test_macd_fallback_strategy_weekly_long(self):
        """测试 MacdFallbackStrategy 周线直接定多"""
        p_macro = (100 * (1.02 ** np.arange(120))).tolist()
        p_trend = [100.0] * 180
        p_wave = np.linspace(100.0, 140.0, 240).tolist()

        p_trigger_flat = [100.0] * 598
        p_trigger_break = [110.0]
        p_trigger_hold = [110.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.MACD_FALLBACK.WEEKLY.LONG",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.macd_fallback_strategy,
        )

        sig = self.macd_fallback_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_macd_fallback_strategy_daily_fallback_long(self):
        """测试 MacdFallbackStrategy 周线中性时由日线定多"""
        p_macro = [100.0] * 120
        p_trend = np.linspace(80.0, 140.0, 180).tolist()
        p_wave = np.linspace(100.0, 140.0, 240).tolist()

        p_trigger_flat = [140.0] * 598
        p_trigger_break = [145.0]
        p_trigger_hold = [145.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.MACD_FALLBACK.DAILY.LONG",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.macd_fallback_strategy,
        )

        sig = self.macd_fallback_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")

    def test_macd_fallback_strategy_weekly_short(self):
        """测试 MacdFallbackStrategy 周线直接定空"""
        p_macro = np.linspace(140.0, 80.0, 120).tolist()
        p_trend = [100.0] * 180
        p_wave = np.linspace(140.0, 100.0, 240).tolist()

        p_trigger_flat = [100.0] * 598
        p_trigger_break = [95.0]
        p_trigger_hold = [95.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.MACD_FALLBACK.WEEKLY.SHORT",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.macd_fallback_strategy,
        )

        sig = self.macd_fallback_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "short")

    def test_macd_fallback_strategy_daily_fallback_short(self):
        """测试 MacdFallbackStrategy 周线中性时由日线定空"""
        p_macro = [100.0] * 100 + np.linspace(100.0, 95.0, 20).tolist()
        p_trend = np.linspace(140.0, 80.0, 180).tolist()
        p_wave = np.linspace(140.0, 100.0, 240).tolist()

        p_trigger_flat = [100.0] * 598
        p_trigger_break = [95.0]
        p_trigger_hold = [95.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.MACD_FALLBACK.DAILY.SHORT",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.macd_fallback_strategy,
        )

        sig = self.macd_fallback_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "short")

    def test_dual_pair_minimal_scan_trigger_daily_long(self):
        """测试 DualPairMinimalScanStrategy 的 5m + 1d 组合触发"""
        p_macro = [100.0] * 120
        p_trend = np.linspace(80.0, 110.0, 180).tolist()
        p_wave = [100.0] * 240

        p_trigger_flat = [99.0] * 598
        p_trigger_break = [112.0]
        p_trigger_hold = [112.0]
        p_trigger = p_trigger_flat + p_trigger_break + p_trigger_hold

        ctx = self.create_context(
            "TEST.MINIMAL.DAILY.LONG",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.dual_pair_minimal_scan_strategy,
        )

        sig = self.dual_pair_minimal_scan_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")
            self.assertIn("5m + 1d", sig.trigger)

    def test_dual_pair_minimal_scan_wave_weekly_long(self):
        """测试 DualPairMinimalScanStrategy 的 30m + 1w 组合触发"""
        p_macro = np.linspace(80.0, 105.0, 120).tolist()
        p_trend = [100.0] * 180

        p_wave_flat = [99.0] * 238
        p_wave_break = [110.0]
        p_wave_hold = [110.0]
        p_wave = p_wave_flat + p_wave_break + p_wave_hold

        p_trigger = [100.0] * 600

        ctx = self.create_context(
            "TEST.MINIMAL.WEEKLY.LONG",
            {
                ScanLevel.MACRO: p_macro,
                ScanLevel.TREND: p_trend,
                ScanLevel.WAVE: p_wave,
                ScanLevel.TRIGGER: p_trigger,
            },
            strategy=self.dual_pair_minimal_scan_strategy,
        )

        sig = self.dual_pair_minimal_scan_strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")
            self.assertIn("30m + 1w", sig.trigger)

    def test_dual_pair_minimal_scan_no_signal(self):
        """测试 DualPairMinimalScanStrategy 在两组都不满足时返回空"""
        ctx = self.create_context(
            "TEST.MINIMAL.NONE",
            {
                ScanLevel.MACRO: [100.0] * 120,
                ScanLevel.TREND: [100.0] * 180,
                ScanLevel.WAVE: [100.0] * 240,
                ScanLevel.TRIGGER: [100.0] * 600,
            },
            strategy=self.dual_pair_minimal_scan_strategy,
        )

        sig = self.dual_pair_minimal_scan_strategy.scan(ctx)
        self.assertIsNone(sig)

    def test_data_validation(self):
        """测试数据缺失报错"""
        # 故意只提供 Trigger 级别
        ctx = self.create_context("TEST.ERR", {ScanLevel.TRIGGER: [100.0] * 10})

        with self.assertRaises(ValueError):
            self.trend_strategy.scan(ctx)


if __name__ == "__main__":
    unittest.main()
