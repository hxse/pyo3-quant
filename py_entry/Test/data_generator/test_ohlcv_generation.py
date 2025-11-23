"""
测试 generate_ohlcv 和 generate_multi_timeframe_ohlcv 函数
"""

import pytest
import polars as pl
import numpy as np

from py_entry.data_conversion.helpers.data_generator import (
    generate_ohlcv,
    generate_multi_timeframe_ohlcv,
    parse_timeframe,
)


class TestOhlcvGeneration:
    """OHLCV 数据生成测试类"""

    def test_generate_ohlcv_basic(self, basic_start_time, basic_num_bars):
        """测试 generate_ohlcv 函数的基本功能"""
        timeframe = "1h"
        start_time = basic_start_time
        num_bars = basic_num_bars

        df = generate_ohlcv(timeframe, start_time, num_bars)

        # 验证生成的DataFrame行数是否正确
        assert len(df) == num_bars

        # 验证生成的DataFrame是否包含必要的列
        expected_columns = ["time", "open", "high", "low", "close", "volume", "date"]
        for col in expected_columns:
            assert col in df.columns

        # 验证时间戳是否连续且间隔正确
        interval_ms = parse_timeframe(timeframe)
        expected_times = start_time + np.arange(num_bars) * interval_ms
        assert np.array_equal(df["time"].to_numpy(), expected_times)

        # 验证价格和成交量是否为浮点数类型
        assert df["open"].dtype == pl.Float64
        assert df["high"].dtype == pl.Float64
        assert df["low"].dtype == pl.Float64
        assert df["close"].dtype == pl.Float64
        assert df["volume"].dtype == pl.Float64

    def test_generate_ohlcv_empty_num_bars(self, basic_start_time):
        """测试 generate_ohlcv 函数 num_bars 为 0 的情况"""
        timeframe = "1h"
        start_time = basic_start_time
        num_bars = 0

        df = generate_ohlcv(timeframe, start_time, num_bars)

        # 验证生成的DataFrame行数是否为0
        assert len(df) == 0

        # 验证列是否存在
        expected_columns = ["time", "open", "high", "low", "close", "volume", "date"]
        for col in expected_columns:
            assert col in df.columns

    def test_generate_multi_timeframe_ohlcv_basic(
        self,
        basic_timeframes,
        basic_start_time,
        basic_num_bars,
        multi_timeframe_ohlcv_data,
    ):
        """测试 generate_multi_timeframe_ohlcv 函数的基本功能"""
        timeframes = basic_timeframes
        start_time = basic_start_time
        num_bars = basic_num_bars  # 最小时间周期 (15m) 的 K 线数量

        dfs = multi_timeframe_ohlcv_data

        # 验证返回的 DataFrame 列表数量是否正确
        assert len(dfs) == len(timeframes)

        # 验证每个 DataFrame 的行数和列
        min_interval_ms = parse_timeframe(timeframes[0])
        for i, tf in enumerate(timeframes):
            df = dfs[i]
            interval_ms = parse_timeframe(tf)
            expected_num_bars = int(np.ceil(num_bars * min_interval_ms / interval_ms))

            assert len(df) == expected_num_bars

            expected_columns = [
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "date",
            ]
            for col in expected_columns:
                assert col in df.columns

            # 验证时间戳是否连续且间隔正确
            expected_times = start_time + np.arange(expected_num_bars) * interval_ms
            assert np.array_equal(df["time"].to_numpy(), expected_times)

    def test_generate_multi_timeframe_ohlcv_empty_timeframes(
        self, basic_start_time, basic_num_bars
    ):
        """测试 generate_multi_timeframe_ohlcv 函数 timeframes 为空的情况"""
        timeframes = []
        start_time = basic_start_time
        num_bars = basic_num_bars

        dfs = generate_multi_timeframe_ohlcv(timeframes, start_time, num_bars)

        # 验证返回空列表
        assert len(dfs) == 0

    def test_generate_multi_timeframe_ohlcv_single_timeframe(self, basic_start_time):
        """测试 generate_multi_timeframe_ohlcv 函数单个时间周期的情况"""
        timeframes = ["1h"]
        start_time = basic_start_time
        num_bars = 50

        dfs = generate_multi_timeframe_ohlcv(timeframes, start_time, num_bars)

        assert len(dfs) == 1
        df = dfs[0]
        assert len(df) == num_bars
        expected_columns = ["time", "open", "high", "low", "close", "volume", "date"]
        for col in expected_columns:
            assert col in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
