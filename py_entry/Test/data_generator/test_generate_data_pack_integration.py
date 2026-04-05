"""
测试 generate_data_pack 函数的集成功能
"""

import pytest
from py_entry.data_generator import (
    DataGenerationParams,
    generate_data_pack,
)


class TestGenerateDataPackIntegration:
    """generate_data_pack 函数集成测试类"""

    def test_generate_data_pack_mapping_integration(self, data_pack):
        """测试 generate_data_pack 函数的映射集成功能"""

        # 验证 DataPack 的基本结构
        assert hasattr(data_pack, "mapping")
        assert hasattr(data_pack, "source")
        assert hasattr(data_pack, "base_data_key")

        # 获取基准键 (通常是第一个时间周期)
        base_key = data_pack.base_data_key
        assert base_key in data_pack.source

        # 验证映射表包含基准列与全部 source 列
        assert base_key in data_pack.mapping.columns
        for col_name in data_pack.source.keys():
            assert col_name in data_pack.mapping.columns, (
                f"列 {col_name} 不存在于映射 DataFrame 中"
            )

    def test_generate_data_pack_empty_timeframes(self, data_pack):
        """测试 generate_data_pack 函数 - 正常时间周期列表"""
        # 注意：原测试名称为 empty_timeframes 但实际测试的是正常情况

        # 验证结果包含 OHLCV 数据
        ohlcv_keys = [k for k in data_pack.source.keys() if "ohlcv" in k]
        assert len(ohlcv_keys) > 0

        base_key = data_pack.base_data_key
        assert base_key in data_pack.mapping.columns

    def test_generate_data_pack_small_num_bars(self, basic_start_time):
        """测试 generate_data_pack 函数 - 小数量 K 线"""
        # 生成少量 K 线数据
        timeframes = ["15m"]
        num_bars = 5  # 很小的数量

        # 创建模拟数据配置
        simulated_data_config = DataGenerationParams(
            timeframes=timeframes,
            start_time=basic_start_time,
            num_bars=num_bars,
            base_data_key="ohlcv_15m",
        )

        # 调用函数
        data_pack = generate_data_pack(data_source=simulated_data_config)

        # 验证结果
        assert "ohlcv_15m" in data_pack.source
        assert len(data_pack.source["ohlcv_15m"]) == num_bars

        base_key = "ohlcv_15m"
        assert base_key in data_pack.mapping.columns

    def test_generate_data_pack_with_ha_and_renko_rejects_duplicate_time_source(
        self, basic_start_time
    ):
        """测试 generate_data_pack 函数 - renko 重复时间戳 source 必须 fail-fast"""
        from py_entry.data_generator import OtherParams

        timeframes = ["15m", "1h"]
        # 使用更长样本，避免随机价格路径导致的 Renko 行数波动引发偶发失败
        num_bars = 200

        simulated_data_config = DataGenerationParams(
            timeframes=timeframes,
            start_time=basic_start_time,
            num_bars=num_bars,
            base_data_key="ohlcv_15m",
        )

        other_params = OtherParams(
            brick_size=2.0,
            ha_timeframes=["15m"],
            renko_timeframes=["1h"],
        )

        with pytest.raises(ValueError, match="首覆盖失败|time 列必须严格递增"):
            generate_data_pack(
                data_source=simulated_data_config, other_params=other_params
            )

    def test_generate_data_pack_invalid_timeframe(self, basic_start_time):
        """测试 generate_data_pack 函数 - 无效的时间周期"""
        from py_entry.data_generator import OtherParams

        timeframes = ["15m"]
        num_bars = 10

        simulated_data_config = DataGenerationParams(
            timeframes=timeframes,
            start_time=basic_start_time,
            num_bars=num_bars,
            base_data_key="ohlcv_15m",
        )

        # 请求不存在的 timeframe
        other_params = OtherParams(
            brick_size=2.0,
            ha_timeframes=["1h"],  # 1h 不在 ohlcv timeframes 中
            renko_timeframes=None,
        )

        with pytest.raises(
            ValueError, match="无法生成 HA 数据：找不到对应的 OHLCV 数据 ohlcv_1h"
        ):
            generate_data_pack(
                data_source=simulated_data_config, other_params=other_params
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
