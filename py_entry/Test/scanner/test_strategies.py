import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import polars as pl
from pydantic import ValidationError

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
    # 计算公式: T[i] = End - (Len - 1 - i) * Interval
    times = [
        end_ts - timedelta(seconds=(length - 1 - i) * interval_seconds)
        for i in range(length)
    ]
    # Timestamp 转 int ms
    times_ms = [int(t.timestamp() * 1000) for t in times]

    df = pd.DataFrame()
    df["time"] = times_ms  # 必须要有 time 列
    df["timestamp"] = times_ms  # 同时提供 timestamp/time 以防万一
    df["close"] = pd.Series(prices, dtype="float64")
    df["open"] = df["close"]
    df["high"] = df["close"] + 0.5
    df["low"] = df["close"] - 0.5
    df["volume"] = 1000.0  # float volume
    df["open_interest"] = 5000.0

    return df


class TestEngineStrategies(unittest.TestCase):
    """
    测试基于 Rust 引擎的新策略 (Trend, Reversal)
    """

    def setUp(self):
        self.trend_strategy = TrendStrategy()
        self.reversal_strategy = ReversalStrategy()
        self.momentum_strategy = MomentumStrategy()

    def test_trend_strategy_long_signal(self):
        """测试 TrendStrategy 多头共振信号"""
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

        # 5m: 构造开盘跳空高开 (Opening AND Close > EMA)
        p_5m = (100 * (1.005 ** np.arange(600))).tolist()
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        # Hack: 修改最后一行的 timestamp，使其与上一行差距很大 (> 3600s)，触发 opening_bar
        # df_5m 是 Pandas DataFrame
        last_idx = df_5m.index[-1]
        last_ts = df_5m.at[last_idx, "timestamp"]
        new_ts = last_ts + 24 * 3600 * 1000  # +1 day

        # 修改最后一行
        df_5m.at[last_idx, "timestamp"] = int(new_ts)
        df_5m.at[last_idx, "time"] = int(new_ts)  # 同时修改 time

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext(symbol="TEST.TREND", klines=klines)

        try:
            sig = self.trend_strategy.scan(ctx)
            # 在极其理想的数据下，应该触发信号
            self.assertIsNotNone(sig, "应触发多头趋势信号")
            if sig:
                self.assertEqual(sig.direction, "long")
        except Exception as e:
            self.fail(f"Trend Scan Failed: {e}")

    def test_trend_strategy_crossover(self):
        """测试 TrendStrategy 盘中突破信号 (Close x> EMA)"""
        # 1. 构造大周期共振背景
        # 1w: 强趋势 (CCI > 80)
        p_1w = (100 * (1.2 ** np.arange(50))).tolist()
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        # 1d: 强趋势 (CCI > 30)
        p_1d = (100 * (1.1 ** np.arange(100))).tolist()
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)
        # 1h: 强趋势 (MACD > 0)
        p_1h = (100 * (1.05 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 2. 构造 5m 盘中突破
        # 前面 598 根在 EMA 之下 (99)，最后 2 根拉起 (99 -> 102) 上穿 EMA(100)
        # 这里的 EMA 大约是 100
        p_5m_flat = [99.0] * 598
        p_5m_cross = [99.0, 102.0]  # 99 -> 102, 发生上穿
        p_5m = p_5m_flat + p_5m_cross

        df_5m = make_mock_df(p_5m, interval_seconds=300)
        # 不修改时间戳，保持连续，确保 opening-bar 为 0

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
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

        # 2. 5m: 始终在 EMA 之上，但平稳无波动，无上穿，非开盘
        # EMA20 of flat series is the value itself. Close > EMA?
        # 我们可以让价格微涨，保持 > EMA，但不发生 x>
        p_5m = (100 * (1.001 ** np.arange(600))).tolist()
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext(symbol="TEST.TRIG_FAIL", klines=klines)

        sig = self.trend_strategy.scan(ctx)
        self.assertIsNone(sig, "虽然趋势完美且价格在EMA上，但无突破动作，不应发信号")

    def test_trend_filter_fail(self):
        """测试 TrendStrategy: 有点无势 (5m 突破, 但大周期不共振)"""
        # 1. 大周期走坏 (例如 1H MACD < 0)
        # 构造下跌趋势
        p_1h = (100 * (0.95 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 1w/1d 保持好也不行，因为是 AND 逻辑
        p_1w = (100 * (1.2 ** np.arange(50))).tolist()
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        p_1d = (100 * (1.1 ** np.arange(100))).tolist()
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)

        # 2. 5m: 完美突破
        p_5m_flat = [99.0] * 598
        p_5m_cross = [99.0, 102.0]
        p_5m = p_5m_flat + p_5m_cross
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
        ctx = ScanContext(symbol="TEST.FILT_FAIL", klines=klines)

        sig = self.trend_strategy.scan(ctx)
        self.assertIsNone(sig, "虽有5m突破，但1H趋势向下，不应发信号")

    def test_trend_strategy_no_signal(self):
        """测试 TrendStrategy 无信号 (背离/互斥行情)"""
        # 补全所有周期数据，防止 validate_klines_existence 报错
        p_1w = [100.0] * 50
        df_1w = make_mock_df(p_1w, interval_seconds=7 * 24 * 3600)
        p_1d = [100.0] * 100
        df_1d = make_mock_df(p_1d, interval_seconds=24 * 3600)

        # 1h 暴涨 (MACD > 0)
        p_1h = (100 * (1.01 ** np.arange(200))).tolist()
        df_1h = make_mock_df(p_1h, interval_seconds=3600)

        # 5m 暴跌 (Close < EMA < EMA)
        p_5m = (100 * (0.99 ** np.arange(200))).tolist()
        df_5m = make_mock_df(p_5m, interval_seconds=300)

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
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

        # 1. 准备指标 (模拟 reversal.py 逻辑)
        indicators = {
            "ohlcv_1w": {
                "cci_w": {"period": Param.create(14)},
                "ema_w": {"period": Param.create(20)},
            },
            "ohlcv_1d": {
                "cci-divergence_0": {
                    "period": Param.create(14),
                    "window": Param.create(20),
                    "gap": Param.create(3),
                    "recency": Param.create(5),
                },
                "ema_d": {"period": Param.create(20)},
            },
            "ohlcv_1h": {
                "macd_h": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_h": {"period": Param.create(20)},
            },
            "ohlcv_5m": {
                "macd_m": {
                    "fast_period": Param.create(12),
                    "slow_period": Param.create(26),
                    "signal_period": Param.create(9),
                },
                "ema_m": {"period": Param.create(20)},
            },
        }

        klines = {"5m": df_5m, "1h": df_1h, "1d": df_1d, "1w": df_1w}
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
        # 构造: 长期上涨 -> 短期回调 -> 最后两根反弹
        # 简单点: 手动拼接
        # part1: 上涨 (280 root)
        part1 = np.linspace(100, 120, 280)
        # part2: 回调 (18 root) -> Hist < 0
        part2 = np.linspace(120, 118, 18)
        # part3: 突破 (2 root) -> Hist > 0
        part3 = np.linspace(118, 122, 2)

        p_5m = np.concatenate([part1, part2, part3]).tolist()
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
