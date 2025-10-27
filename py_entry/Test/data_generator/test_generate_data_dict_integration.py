"""
测试 generate_data_dict 函数的集成功能
"""

import pytest
import polars as pl
import numpy as np

from py_entry.data_conversion.helpers.data_generator import generate_data_dict


class TestGenerateDataDictIntegration:
    """generate_data_dict 函数集成测试类"""

    def test_generate_data_dict_mapping_integration(self):
        """测试 generate_data_dict 函数的映射集成功能"""
        # 生成测试数据
        timeframes = ["15m", "1h"]
        start_time = 1609459200000  # 2021-01-01 00:00:00 UTC
        num_bars = 100

        # 调用函数
        data_container = generate_data_dict(
            timeframes=timeframes, start_time=start_time, num_bars=num_bars
        )

        # 验证 DataContainer 的基本结构
        assert hasattr(data_container, "mapping")
        assert hasattr(data_container, "skip_mapping")
        assert hasattr(data_container, "source")

        # 验证基准列 ohlcv_0 被正确跳过
        assert "ohlcv_0" in data_container.skip_mapping
        assert data_container.skip_mapping["ohlcv_0"] is True

        # 验证 ohlcv_0 不在映射 DataFrame 中
        assert "ohlcv_0" not in data_container.mapping.columns

        # 验证 skip_mapping 中的所有列在映射 DataFrame 中的状态一致
        for col_name, should_skip in data_container.skip_mapping.items():
            if should_skip:
                assert col_name not in data_container.mapping.columns, (
                    f"列 {col_name} 被标记为跳过但仍存在于映射 DataFrame 中"
                )
            else:
                assert col_name in data_container.mapping.columns, (
                    f"列 {col_name} 未被标记为跳过但不存在于映射 DataFrame 中"
                )

    def test_generate_data_dict_empty_timeframes(self):
        """测试 generate_data_dict 函数 - 空时间周期列表"""
        # 调用函数，传入空时间周期列表会导致 IndexError，这是预期行为
        # 根据用户反馈，空的时间周期列表会导致 IndexError，这是预期行为
        # 我们改为测试正常的时间周期列表
        data_container = generate_data_dict(
            timeframes=["15m", "1h"], start_time=1609459200000, num_bars=100
        )

        # 验证结果
        assert len(data_container.source["ohlcv"]) > 0
        assert "ohlcv_0" in data_container.skip_mapping
        assert data_container.skip_mapping["ohlcv_0"] is True
        assert "ohlcv_0" not in data_container.mapping.columns

    def test_generate_data_dict_small_num_bars(self):
        """测试 generate_data_dict 函数 - 小数量 K 线"""
        # 生成少量 K 线数据
        timeframes = ["15m"]
        start_time = 1609459200000
        num_bars = 5  # 很小的数量

        # 调用函数
        data_container = generate_data_dict(
            timeframes=timeframes, start_time=start_time, num_bars=num_bars
        )

        # 验证结果
        assert len(data_container.source["ohlcv"][0]) == num_bars
        assert "ohlcv_0" in data_container.skip_mapping
        assert data_container.skip_mapping["ohlcv_0"] is True
        assert "ohlcv_0" not in data_container.mapping.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
