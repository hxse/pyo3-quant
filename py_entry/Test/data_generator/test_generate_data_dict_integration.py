"""
测试 generate_data_dict 函数的集成功能
"""

import pytest
from py_entry.data_conversion.data_generator import (
    generate_data_dict,
    DataGenerationParams,
)


class TestGenerateDataDictIntegration:
    """generate_data_dict 函数集成测试类"""

    def test_generate_data_dict_mapping_integration(self, data_container):
        """测试 generate_data_dict 函数的映射集成功能"""

        # 验证 DataContainer 的基本结构
        assert hasattr(data_container, "mapping")
        assert hasattr(data_container, "skip_mapping")
        assert hasattr(data_container, "source")
        assert hasattr(data_container, "BaseDataKey")

        # 获取基准键 (通常是第一个时间周期)
        base_key = data_container.BaseDataKey
        assert base_key in data_container.source

        # 验证基准列被正确跳过
        assert base_key in data_container.skip_mapping
        assert data_container.skip_mapping[base_key] is True

        # 验证基准列不在映射 DataFrame 中
        assert base_key not in data_container.mapping.columns

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

    def test_generate_data_dict_empty_timeframes(self, data_container):
        """测试 generate_data_dict 函数 - 正常时间周期列表"""
        # 注意：原测试名称为 empty_timeframes 但实际测试的是正常情况

        # 验证结果包含 OHLCV 数据
        ohlcv_keys = [k for k in data_container.source.keys() if "ohlcv" in k]
        assert len(ohlcv_keys) > 0

        base_key = data_container.BaseDataKey
        assert base_key in data_container.skip_mapping
        assert data_container.skip_mapping[base_key] is True
        assert base_key not in data_container.mapping.columns

    def test_generate_data_dict_small_num_bars(self, basic_start_time):
        """测试 generate_data_dict 函数 - 小数量 K 线"""
        # 生成少量 K 线数据
        timeframes = ["15m"]
        num_bars = 5  # 很小的数量

        # 创建模拟数据配置
        simulated_data_config = DataGenerationParams(
            timeframes=timeframes,
            start_time=basic_start_time,
            num_bars=num_bars,
            fixed_seed=False,
            BaseDataKey="ohlcv_15m",
        )

        # 调用函数
        data_container = generate_data_dict(data_source=simulated_data_config)

        # 验证结果
        assert "ohlcv_15m" in data_container.source
        assert len(data_container.source["ohlcv_15m"]) == num_bars

        base_key = "ohlcv_15m"
        assert base_key in data_container.skip_mapping
        assert data_container.skip_mapping[base_key] is True
        assert base_key not in data_container.mapping.columns

    def test_generate_data_dict_with_ha_renko(self, basic_start_time):
        """测试 generate_data_dict 函数 - 生成 HA 和 Renko 数据"""
        from py_entry.data_conversion.data_generator import OtherParams

        timeframes = ["15m", "1h"]
        num_bars = 10

        simulated_data_config = DataGenerationParams(
            timeframes=timeframes,
            start_time=basic_start_time,
            num_bars=num_bars,
            fixed_seed=False,
            BaseDataKey="ohlcv_15m",
        )

        other_params = OtherParams(
            brick_size=2.0,
            ha_timeframes=["15m"],
            renko_timeframes=["1h"],
        )

        data_container = generate_data_dict(
            data_source=simulated_data_config, other_params=other_params
        )

        # 验证 HA 数据
        assert "ha_15m" in data_container.source
        assert "ha_1h" not in data_container.source

        # 验证 Renko 数据
        assert "renko_1h" in data_container.source
        assert "renko_15m" not in data_container.source

    def test_generate_data_dict_invalid_timeframe(self, basic_start_time):
        """测试 generate_data_dict 函数 - 无效的时间周期"""
        from py_entry.data_conversion.data_generator import OtherParams

        timeframes = ["15m"]
        num_bars = 10

        simulated_data_config = DataGenerationParams(
            timeframes=timeframes,
            start_time=basic_start_time,
            num_bars=num_bars,
            fixed_seed=False,
            BaseDataKey="ohlcv_15m",
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
            generate_data_dict(
                data_source=simulated_data_config, other_params=other_params
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
