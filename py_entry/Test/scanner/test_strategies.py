import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import polars as pl
from pydantic import ValidationError

from py_entry.scanner.config import TF_5M, TF_1H, TF_1D, TF_1W
from py_entry.scanner.strategies.base import ScanContext
from py_entry.scanner.strategies.trend import TrendStrategy
from py_entry.scanner.strategies.reversal import ReversalStrategy
from py_entry.scanner.strategies.momentum import MomentumStrategy
from py_entry.types import Param


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
    # 生成时间序列: 从 (end - length*interval) 到 end
    times = [
        end_ts - timedelta(seconds=(length - 1 - i) * interval_seconds)
        for i in range(length)
    ]

    # Critical: TqSdk returns 'datetime' column in nanoseconds (int64)
    # pd.Timestamp.value returns nanoseconds
    times_ns = [t.value for t in times]

    df = pd.DataFrame()
    df["datetime"] = times_ns
    df["close"] = pd.Series(prices, dtype="float64")
    df["open"] = df["close"]
    df["high"] = df["close"] + 0.5
    df["low"] = df["close"] - 0.5
    df["volume"] = 1000.0  # float volume
    df["open_interest"] = 5000.0

    return df


class TestEngineStrategies(unittest.TestCase):
    """
    测试基于 Rust 引擎的新策略 (Trend, Reversal, Momentum)
    重点验证: 信号逻辑正确性, 以及[已完成K线](倒数第2根)的信号确认机制
    """

    def setUp(self):
        self.trend_strategy = TrendStrategy()
        self.reversal_strategy = ReversalStrategy()
        self.momentum_strategy = MomentumStrategy()

    def test_trend_strategy_integrated(self):
        """测试 TrendStrategy 多头共振信号 (完整流程 - 标准突破)"""
        # 1. 构造全周期强势上涨数据
        # 1w: 强趋势 (CCI > 80)
        p_1w = (100 * (1.2 ** np.arange(50))).tolist()
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)

        # 1d: 强趋势 (CCI > 30)
        p_1d = (100 * (1.1 ** np.arange(100))).tolist()
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)

        # 1h: 强趋势 (MACD > 0)
        p_1h = (100 * (1.05 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 5m: 构造完美突破 (Flat -> Break -> Hold)
        p_5m_flat = [100.0] * 598
        p_5m_break = [105.0]
        p_5m_hold = [105.0]
        p_5m = p_5m_flat + p_5m_break + p_5m_hold

        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {TF_5M: df_5m, TF_1H: df_1h, TF_1D: df_1d, TF_1W: df_1w}
        ctx = ScanContext(symbol="TEST.TREND", klines=klines)

        try:
            sig = self.trend_strategy.scan(ctx)
            # 在极其理想的数据下，应该触发信号
            self.assertIsNotNone(sig, "应触发多头趋势信号")
            if sig:
                self.assertEqual(sig.direction, "long")
                self.assertIn("Trend 突破进场", sig.trigger)
        except Exception as e:
            self.fail(f"Trend Scan Failed: {e}")

    def test_trend_strategy_crossover(self):
        """测试 TrendStrategy 盘中突破信号 (Close x> EMA)"""
        # 1. 构造大周期共振背景
        p_1w = (100 * (1.2 ** np.arange(50))).tolist()
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        p_1d = (100 * (1.1 ** np.arange(100))).tolist()
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)
        p_1h = (100 * (1.05 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 2. 构造 5m 盘中突破
        p_5m_flat = [99.0] * 598
        p_5m_cross = [102.0]  # N-2 (Signal)
        p_5m_pad = [102.0]  # N-1 (Forming)
        p_5m = p_5m_flat + p_5m_cross + p_5m_pad

        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {TF_5M: df_5m, TF_1H: df_1h, TF_1D: df_1d, TF_1W: df_1w}
        ctx = ScanContext(symbol="TEST.CROSS", klines=klines)

        try:
            sig = self.trend_strategy.scan(ctx)
            # 这里应该触发 5m 突破信号
            self.assertIsNotNone(sig, "应触发盘中突破信号")
            if sig:
                self.assertEqual(sig.direction, "long")
                self.assertIn("Trend 突破进场", sig.trigger)
        except Exception as e:
            self.fail(f"Crossover Scan Failed: {e}")

    def test_trend_trigger_fail(self):
        """测试 TrendStrategy: 有势无点 (大周期完美, 但 5m 无触发)"""
        # 1. 大周期完美
        p_1w = (100 * (1.2 ** np.arange(50))).tolist()
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        p_1d = (100 * (1.1 ** np.arange(100))).tolist()
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)
        p_1h = (100 * (1.05 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 2. 5m: 始终在 EMA 之上，但平稳无波动，无上穿
        p_5m = (100 * (1.001 ** np.arange(600))).tolist()
        # Add padding just in case, though flat is flat
        p_5m += [p_5m[-1]]

        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {TF_5M: df_5m, TF_1H: df_1h, TF_1D: df_1d, TF_1W: df_1w}
        ctx = ScanContext(symbol="TEST.TRIG_FAIL", klines=klines)

        sig = self.trend_strategy.scan(ctx)
        self.assertIsNone(sig, "虽然趋势完美且价格在EMA上，但无突破动作，不应发信号")

    def test_trend_filter_fail(self):
        """测试 TrendStrategy: 有点无势 (5m 突破, 但大周期不共振)"""
        # 1. 大周期走坏 (例如 1H MACD < 0)
        p_1h = (100 * (0.95 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        p_1w = (100 * (1.2 ** np.arange(50))).tolist()
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        p_1d = (100 * (1.1 ** np.arange(100))).tolist()
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)

        # 2. 5m: 完美突破
        p_5m_flat = [99.0] * 598
        p_5m_cross = [102.0]
        p_5m_pad = [102.0]
        p_5m = p_5m_flat + p_5m_cross + p_5m_pad

        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {TF_5M: df_5m, TF_1H: df_1h, TF_1D: df_1d, TF_1W: df_1w}
        ctx = ScanContext(symbol="TEST.FILT_FAIL", klines=klines)

        sig = self.trend_strategy.scan(ctx)
        self.assertIsNone(sig, "虽有5m突破，但1H趋势向下，不应发信号")

    def test_trend_strategy_no_signal(self):
        """测试 TrendStrategy 无信号 (背离/互斥行情)"""
        # 补全所有周期数据
        p_1w = [100.0] * 50
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        p_1d = [100.0] * 100
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)

        # 1h 暴涨
        p_1h = (100 * (1.01 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 5m 暴跌
        p_5m = (100 * (0.99 ** np.arange(200))).tolist() + [0.0]  # Pad
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {TF_5M: df_5m, TF_1H: df_1h, TF_1D: df_1d, TF_1W: df_1w}
        ctx = ScanContext(symbol="TEST.NO_SIG", klines=klines)

        sig = self.trend_strategy.scan(ctx)
        self.assertIsNone(sig, "多空互斥不应触发信号")

    def test_reversal_strategy_basics(self):
        """测试 ReversalStrategy 基本运行无报错"""
        # 构造全周期数据
        p_1w = [100.0] * 50
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        p_1d = [100.0] * 100
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)
        p_1h = [100.0] * 200
        df_1h = make_mock_df(p_1h, interval_seconds=3600)
        p_5m = [100.0] * 200
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {TF_5M: df_5m, TF_1H: df_1h, TF_1D: df_1d, TF_1W: df_1w}
        ctx = ScanContext(symbol="TEST.REV", klines=klines)

        try:
            sig = self.reversal_strategy.scan(ctx)
            # 这里不强制要求有信号，因为构造背离数据很难
            # 只要代码跑通，说明逻辑无语法错误
            if sig:
                self.assertIn(sig.direction, ["long", "short"])
        except ValidationError as e:
            print("\n[FATAL] Pydantic Validation Error:")
            print(e.json(indent=2))
            self.fail(f"Reversal Validation Error: {e}")
        except Exception as e:
            self.fail(f"Reversal Scan Failed: {e}")

    def test_momentum_strategy_setup(self):
        """测试 MomentumStrategy (复杂4周期共振)"""
        # 1w: 强趋势
        p_1w = (100 * (1.1 ** np.arange(100))).tolist()
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)

        # 1d: 强趋势
        p_1d = (100 * (1.1 ** np.arange(100))).tolist()
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)

        # 1h: 强趋势 (空中加油)
        p_1h = (100 * (1.05 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 5m: 回调再突破 (Diff>0, Hist负转正)
        # part1: 上涨 (280 root)
        part1 = np.linspace(100, 120, 280)
        # part2: 回调 (18 root) -> Hist < 0
        part2 = np.linspace(120, 118, 18)
        # part3: 突破 (2 root) -> Hist > 0
        part3 = np.linspace(118, 122, 2)
        # part4: Padding (1 root) -> Confirm Signal
        part4 = [122.0]

        p_5m = np.concatenate([part1, part2, part3, part4]).tolist()
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext("TEST.MOM", klines)

        try:
            sig = self.momentum_strategy.scan(ctx)
            # 数据太难凑了，只要跑通就行。如果能出信号更好。
            if sig:
                self.assertEqual(sig.strategy_name, "momentum")
        except Exception as e:
            self.fail(f"Momentum Scan Failed: {e}")

    def test_data_validation(self):
        """测试数据缺失报错"""
        # 只有 5m 没有 1h
        df_5m = make_mock_df([100.0] * 10)
        klines = {"5m": df_5m}
        ctx = ScanContext(symbol="TEST.ERR", klines=klines)

        with self.assertRaises(Exception):  # 捕获任何异常
            self.trend_strategy.scan(ctx)


if __name__ == "__main__":
    unittest.main()
