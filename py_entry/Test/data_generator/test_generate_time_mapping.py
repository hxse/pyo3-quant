"""
测试 generate_time_mapping 函数
"""

import pytest

from py_entry.data_conversion.data_generator import generate_time_mapping


class TestGenerateTimeMapping:
    """generate_time_mapping 函数测试类"""

    def test_generate_time_mapping_perfect_match(
        self, sample_time_series, mock_dfs_factory
    ):
        """测试 generate_time_mapping 函数 - 完全匹配情况"""
        # 创建完全匹配的测试数据
        ohlcv_dfs = mock_dfs_factory([sample_time_series])
        ha_dfs = mock_dfs_factory([sample_time_series])
        renko_dfs = mock_dfs_factory([sample_time_series])

        source = {
            "ohlcv_0": ohlcv_dfs[0],
            "ha_0": ha_dfs[0],
            "renko_0": renko_dfs[0],
        }

        # 调用函数
        result, skip_mapping = generate_time_mapping(source, "ohlcv_0")

        # 验证基准列 ohlcv_0 被正确跳过
        assert skip_mapping.get("ohlcv_0") is True

        # 验证其他列也应该被跳过（因为完全匹配）
        assert skip_mapping.get("ha_0") is True
        assert skip_mapping.get("renko_0") is True

        # 验证结果为空（所有列都被跳过）
        assert len(result.columns) == 0

    def test_generate_time_mapping_partial_match(
        self,
        sample_time_series,
        partial_match_time_series,
        no_match_time_series,
        mock_dfs_factory,
    ):
        """测试 generate_time_mapping 函数 - 部分匹配情况"""
        # 创建部分匹配的测试数据
        ohlcv_dfs = mock_dfs_factory([sample_time_series])

        # HA 数据使用不同的时间戳（部分匹配）
        ha_dfs = mock_dfs_factory([partial_match_time_series])

        # Renko 数据使用完全不同的时间戳（不匹配）
        renko_dfs = mock_dfs_factory([no_match_time_series])

        source = {
            "ohlcv_0": ohlcv_dfs[0],
            "ha_0": ha_dfs[0],
            "renko_0": renko_dfs[0],
        }

        # 调用函数
        result, skip_mapping = generate_time_mapping(source, "ohlcv_0")

        # 验证基准列 ohlcv_0 被正确跳过
        assert skip_mapping.get("ohlcv_0") is True

        # 验证其他列的跳过状态
        assert skip_mapping.get("ha_0") is False  # 部分匹配，不应该被跳过
        assert skip_mapping.get("renko_0") is False  # 不匹配，不应该被跳过

        # 验证结果包含非跳过的列
        assert len(result.columns) == 2  # ha_0 和 renko_0
        assert "ha_0" in result.columns
        assert "renko_0" in result.columns

    def test_generate_time_mapping_empty_input(self):
        """测试 generate_time_mapping 函数 - 空输入情况"""
        # 调用函数，传入空字典
        result, skip_mapping = generate_time_mapping({}, "")

        # 验证结果
        assert len(result.columns) == 0
        assert len(skip_mapping) == 0

    def test_generate_time_mapping_single_ohlcv(
        self, sample_time_series, mock_dfs_factory
    ):
        """测试 generate_time_mapping 函数 - 只有一个 ohlcv 的情况（边界情况）"""
        # 只有一个 ohlcv DataFrame
        ohlcv_dfs = mock_dfs_factory([sample_time_series[:5]])

        source = {
            "ohlcv_0": ohlcv_dfs[0],
        }

        # 调用函数
        result, skip_mapping = generate_time_mapping(source, "ohlcv_0")

        # 验证基准列 ohlcv_0 被正确跳过
        assert skip_mapping.get("ohlcv_0") is True

        # 验证没有其他列
        assert len(skip_mapping) == 1
        assert len(result.columns) == 0

    def test_generate_time_mapping_multiple_ohlcv(
        self,
        sample_time_series,
        partial_match_time_series,
        no_match_time_series,
        mock_dfs_factory,
    ):
        """测试 generate_time_mapping 函数 - 多个 ohlcv 的情况"""
        # 创建多个 ohlcv DataFrame
        ohlcv_dfs = mock_dfs_factory(
            [
                sample_time_series,  # 基准
                partial_match_time_series,  # ohlcv_1，部分匹配
                no_match_time_series,  # ohlcv_2，不匹配
            ]
        )

        ha_dfs = mock_dfs_factory([partial_match_time_series])  # ha_0，部分匹配
        renko_dfs = mock_dfs_factory([no_match_time_series])  # renko_0，不匹配

        source = {
            "ohlcv_0": ohlcv_dfs[0],
            "ohlcv_1": ohlcv_dfs[1],
            "ohlcv_2": ohlcv_dfs[2],
            "ha_0": ha_dfs[0],
            "renko_0": renko_dfs[0],
        }

        # 调用函数
        result, skip_mapping = generate_time_mapping(source, "ohlcv_0")

        # 验证基准列 ohlcv_0 被正确跳过
        assert skip_mapping.get("ohlcv_0") is True

        # 验证其他 ohlcv 列的跳过状态
        assert skip_mapping.get("ohlcv_1") is False  # 部分匹配
        assert skip_mapping.get("ohlcv_2") is False  # 不匹配

        # 验证 HA 和 Renko 列的跳过状态
        assert skip_mapping.get("ha_0") is False  # 部分匹配
        assert skip_mapping.get("renko_0") is False  # 不匹配

        # 验证结果包含所有非跳过的列
        expected_columns = ["ohlcv_1", "ohlcv_2", "ha_0", "renko_0"]
        for col in expected_columns:
            assert col in result.columns

        assert len(result.columns) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
