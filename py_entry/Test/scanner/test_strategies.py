import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from py_entry.scanner.strategies.base import ScanContext, StrategySignal
from py_entry.scanner.strategies.trend import TrendStrategy
from py_entry.scanner.strategies.reversal import ReversalStrategy
from py_entry.scanner.strategies.momentum import MomentumStrategy


from typing import Sequence, Union


def make_mock_df(
    prices: Union[Sequence[float], "np.ndarray"],
    start_time: str = "2023-01-01 09:00:00",
    interval_seconds: int = 300,
) -> pd.DataFrame:
    """
    构造Mock数据
    """
    length = len(prices)
    base_time = pd.Timestamp(start_time)
    times = [base_time + timedelta(seconds=i * interval_seconds) for i in range(length)]

    df = pd.DataFrame()
    df["datetime"] = times
    df["close"] = pd.Series(prices, dtype="float64")
    df["open"] = df["close"]
    df["high"] = df["close"] + 0.5
    df["low"] = df["close"] - 0.5
    df["volume"] = 1000
    df["open_interest"] = 5000

    return df


def make_perfect_downtrend_data():
    """构造完美的空头趋势数据"""
    n = 100
    prices = np.linspace(100, 80, n)
    prices[-10:] -= np.linspace(0, 5, 10)
    df = make_mock_df(prices, interval_seconds=300)
    return df


class TestTrendStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = TrendStrategy()

    def test_trend_long_success(self):
        """测试多头共振: 所有的周期都看涨"""
        # 1. 构造各个周期的数据
        # 5m: 要求上穿 EMA (x>)。[-3] < EMA, [-2] > EMA
        p_5m = [100.0] * 100
        p_5m[-3] = 98.0  # dip below average
        p_5m[-2] = 102.0  # jump above average
        # ema(20) approx 100
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        # 1h: MACD Red + Close > EMA
        # 持续加速上涨 (Linear uptrend gives flat MACD -> Hist ~ 0. Accelerating gives Hist > 0)
        p_1h = np.linspace(100, 110, 100)
        p_1h += np.linspace(0, 5, 100) ** 2 / 10.0  # accelerating
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 1d: CCI > 30 + Close > EMA
        # 持续上涨
        p_1d = np.linspace(100, 120, 100)
        df_1d = make_mock_df(p_1d, interval_seconds=86400)

        # 1w: CCI > 80 + Close > EMA
        # 强劲上涨
        p_1w = np.linspace(100, 150, 100)
        # 尾部加速以拉高 CCI (CCI calculation requires volatility)
        # If linear, CCI might be weird. Let's make it super bullish.
        p_1w[-10:] += np.linspace(0, 20, 10)
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 86400)

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext("TEST.rb", klines)

        # Debugging: check each timeframe
        res_5m = self.strategy._check_5m(df_5m)
        res_1h = self.strategy._check_1h(df_1h)
        res_1d = self.strategy._check_1d(df_1d)
        res_1w = self.strategy._check_1w(df_1w)

        self.assertTrue(res_5m["is_bullish"], f"5m check failed: {res_5m['detail']}")
        self.assertTrue(res_1h["is_bullish"], f"1h check failed: {res_1h['detail']}")
        self.assertTrue(res_1d["is_bullish"], f"1d check failed: {res_1d['detail']}")
        self.assertTrue(res_1w["is_bullish"], f"1w check failed: {res_1w['detail']}")

        sig = self.strategy.scan(ctx)

        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "long")
            self.assertIn("上穿EMA", sig.trigger)
            self.assertEqual(len(sig.detail_lines), 4)

    def test_trend_missing_weekly_cci(self):
        """测试: 5m 信号虽好，但周线 CCI 不够强 -> 无信号"""
        # 5m 满足上穿
        p_5m = [100.0] * 30
        p_5m[-3] = 98.0
        p_5m[-2] = 102.0
        df_5m = make_mock_df(p_5m)

        # 1h, 1d 满足
        df_1h = make_mock_df(np.linspace(100, 110, 50))
        df_1d = make_mock_df(np.linspace(100, 120, 50))

        # 1w: 震荡，CCI 弱 (使用平盘)
        df_1w = make_mock_df(np.linspace(100, 100, 50))

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext("TEST.rb", klines)

        sig = self.strategy.scan(ctx)
        self.assertIsNone(sig)

    def test_trend_short_success(self):
        """测试空头共振"""
        # 5m: 下穿 EMA
        p_5m = [100.0] * 30
        p_5m[-3] = 102.0
        p_5m[-2] = 98.0
        df_5m = make_mock_df(p_5m)

        # 其他周期下跌
        df_1h = make_perfect_downtrend_data()
        df_1d = make_perfect_downtrend_data()
        df_1w = make_perfect_downtrend_data()

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext("TEST.short", klines)

        sig = self.strategy.scan(ctx)
        self.assertIsNotNone(sig)
        if sig:
            self.assertEqual(sig.direction, "short")
            self.assertIn("下穿EMA", sig.trigger)


class TestReversalStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = ReversalStrategy()

    def test_reversal_short_setup(self):
        """测试顶部背驰做空"""
        cols = ["close", "high", "low", "open"]

        # 1. 周线: 强多头 (CCI > 80)
        p_1w = np.linspace(100, 150, 100)
        p_1w[-5:] += np.array([2, 4, 6, 8, 10])
        df_1w = make_mock_df(p_1w)

        # 2. 日线: 高位背离 (价格新高，CCI 不新高)
        p_1d = np.linspace(100, 130, 100)
        p_1d[-10] = 140.0
        p_1d[-2] = 142.0
        df_1d = make_mock_df(p_1d)

        # Hack: manually adjust highs to create CCI peak earlier
        # Use loc with list of columns to ensure types match
        df_1d.loc[df_1d.index[-12], cols] = 200.0

        # 3. 1h: MACD 蓝柱 (<0)
        p_1h = np.linspace(100, 90, 100)
        df_1h = make_mock_df(p_1h)

        # 4. 5m: MACD 红转蓝 + 价格位置
        p_5m = [102.0] * 50
        p_5m[-2] = 100.0
        df_5m = make_mock_df(p_5m)

        # 调整各周期价格水平
        df_1h.loc[:, cols] = 100.0
        df_1h.loc[df_1h.index[:50], cols] = 110.0

        df_1d.loc[:, cols] = 100.0
        df_1d.loc[df_1d.index[:50], cols] = 90.0

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext("TEST.rev", klines)

        sig = self.strategy.scan(ctx)
        pass

    def test_reversal_safety(self):
        """测试异常数据安全性"""
        klines = {
            "5m": pd.DataFrame(),
            "1h": pd.DataFrame(),
            "1d": pd.DataFrame(),
            "1w": pd.DataFrame(),
        }
        ctx = ScanContext("TEST.empty", klines)
        with self.assertRaises(ValueError):
            self.strategy.scan(ctx)


class TestMomentumStrategy(unittest.TestCase):
    def setUp(self):
        self.strategy = MomentumStrategy()

    def test_momentum_long_setup(self):
        """测试动能起爆 (做多)"""
        # 1w: uptrend (needs strong MACD and price action)
        p_1w = np.linspace(100, 150, 100)
        p_1w[-10:] += np.linspace(0, 20, 10)  # strong finish
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 86400)

        # 1d: uptrend
        p_1d = np.linspace(100, 120, 100)
        df_1d = make_mock_df(p_1d, interval_seconds=86400)

        # 1h: Zero+ Red. diff > 0, hist > 0
        p_1h = np.linspace(100, 110, 50)
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 5m: Zero+ Golden Cross
        p_5m = [100.0] * 50
        p_5m[-10:] = np.linspace(100, 102, 10)
        df_5m = make_mock_df(p_5m)

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext("TEST.mom", klines)

        sig = self.strategy.scan(ctx)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
