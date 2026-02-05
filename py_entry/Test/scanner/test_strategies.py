import unittest
import pandas as pd
import numpy as np
from datetime import timedelta
import polars as pl

from py_entry.scanner.config import ScanLevel, ScannerConfig
from py_entry.scanner.strategies.base import ScanContext
from py_entry.scanner.strategies.trend import TrendStrategy
from py_entry.scanner.strategies.reversal import ReversalStrategy
from py_entry.scanner.strategies.momentum import MomentumStrategy
from py_entry.scanner.strategies.pullback import PullbackStrategy


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
        # 建立基于配置的默认映射
        self.level_to_tf = {tf.level: tf.name for tf in self.config.timeframes}

    def create_context(
        self, symbol: str, prices_dict: dict[ScanLevel, list[float]]
    ) -> ScanContext:
        """助手函数：根据逻辑级别自动构造 ScanContext"""
        klines = {}
        for level, prices in prices_dict.items():
            # 查找物理周期配置
            tf_conf = next(tf for tf in self.config.timeframes if tf.level == level)
            df = make_mock_df(prices, interval_seconds=tf_conf.seconds)
            klines[tf_conf.name] = df

        return ScanContext(symbol=symbol, klines=klines, level_to_tf=self.level_to_tf)

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

    def test_data_validation(self):
        """测试数据缺失报错"""
        # 故意只提供 Trigger 级别
        ctx = self.create_context("TEST.ERR", {ScanLevel.TRIGGER: [100.0] * 10})

        with self.assertRaises(ValueError):
            self.trend_strategy.scan(ctx)


if __name__ == "__main__":
    unittest.main()
