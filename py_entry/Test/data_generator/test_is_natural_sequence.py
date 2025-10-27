"""
测试 is_natural_sequence 函数
"""

import pytest
import polars as pl
import numpy as np

from py_entry.data_conversion.helpers.data_generator import is_natural_sequence


class TestIsNaturalSequence:
    """is_natural_sequence 函数测试类"""

    def test_is_natural_sequence(self):
        """测试 is_natural_sequence 函数"""
        # 测试自然数序列
        natural_series = pl.Series("test", np.arange(5))
        assert is_natural_sequence(natural_series) is True

        # 测试非自然数序列
        non_natural_series = pl.Series("test", np.array([0, 1, 3, 4]))
        assert is_natural_sequence(non_natural_series) is False

        # 测试包含 null 值的序列
        null_series = pl.Series("test", np.array([0, 1, None, 3]))
        assert is_natural_sequence(null_series) is False

        # 测试空序列
        empty_series = pl.Series("test", np.array([]))
        assert is_natural_sequence(empty_series) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])