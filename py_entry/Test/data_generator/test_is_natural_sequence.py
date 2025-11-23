"""
测试 is_natural_sequence 函数
"""

import pytest
import polars as pl

from py_entry.data_conversion.helpers.data_generator import is_natural_sequence


class TestIsNaturalSequence:
    """is_natural_sequence 函数测试类"""

    def test_is_natural_sequence(
        self,
        sample_natural_series,
        sample_non_natural_series,
        sample_null_series,
        empty_dataframe,
    ):
        """测试 is_natural_sequence 函数"""
        # 测试自然数序列
        assert is_natural_sequence(sample_natural_series) is True

        # 测试非自然数序列
        assert is_natural_sequence(sample_non_natural_series) is False

        # 测试包含 null 值的序列
        assert is_natural_sequence(sample_null_series) is False

        # 测试空序列
        # 从 empty_dataframe 中提取一个空 Series，或者直接创建一个空 Series
        # 这里为了复用 fixture，我们假设 empty_dataframe 有一个列，或者我们直接创建一个空 Series
        # 因为 empty_dataframe fixture 返回的是 pl.DataFrame({"time": []})
        empty_series = empty_dataframe["time"]
        assert is_natural_sequence(empty_series) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
