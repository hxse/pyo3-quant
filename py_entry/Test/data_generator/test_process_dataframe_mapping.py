"""
测试 _process_dataframe_mapping 函数
"""

import pytest
import polars as pl
import numpy as np

from py_entry.data_generator import process_dataframe_mapping


class TestProcessDataframeMapping:
    """_process_dataframe_mapping 函数测试类"""

    def test_process_dataframe_mapping_perfect_match(
        self, sample_time_series, ohlcv_df_factory
    ):
        """测试 _process_dataframe_mapping 函数 - 完全匹配情况"""
        # 创建完全匹配的基准和目标 DataFrame
        base_df = ohlcv_df_factory(sample_time_series)
        df = ohlcv_df_factory(sample_time_series)

        result = pl.DataFrame()
        skip_mapping = {}

        # 调用函数
        result = process_dataframe_mapping(
            base_df, df, "test_col", result, skip_mapping
        )

        # 验证结果
        assert "test_col" in skip_mapping
        assert skip_mapping["test_col"] is True  # 应该被跳过，因为是自然序列
        assert len(result.columns) == 0  # 结果应该为空，因为被跳过了

    def test_process_dataframe_mapping_partial_match(
        self, sample_time_series, ohlcv_df_factory
    ):
        """测试 _process_dataframe_mapping 函数 - 部分匹配情况"""
        # 创建部分匹配的基准和目标 DataFrame
        base_df = ohlcv_df_factory(sample_time_series)

        # 目标 DataFrame 使用部分匹配的时间戳
        partial_times = np.arange(5) * 2000 + 500  # 500, 2500, 4500, 6500, 8500
        df = ohlcv_df_factory(partial_times)

        result = pl.DataFrame()
        skip_mapping = {}

        # 调用函数
        result = process_dataframe_mapping(
            base_df, df, "test_col", result, skip_mapping
        )

        # 验证结果
        assert "test_col" in skip_mapping
        assert skip_mapping["test_col"] is False  # 不应该被跳过，因为不是自然序列
        assert len(result.columns) == 1  # 结果应该包含一列
        assert "test_col" in result.columns

    def test_process_dataframe_mapping_empty_dataframe(self, empty_dataframe):
        """测试 _process_dataframe_mapping 函数 - 空 DataFrame 情况"""
        # 创建空的基准和目标 DataFrame
        base_df = empty_dataframe
        df = empty_dataframe

        result = pl.DataFrame()
        skip_mapping = {}

        # 调用函数
        result = process_dataframe_mapping(
            base_df, df, "test_col", result, skip_mapping
        )

        # 验证结果
        assert "test_col" in skip_mapping
        assert skip_mapping["test_col"] is True  # 空序列应该被认为是自然序列
        assert len(result.columns) == 0  # 结果应该为空


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
