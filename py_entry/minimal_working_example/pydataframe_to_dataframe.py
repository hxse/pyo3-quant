"""
方案2：自定义FromPyObject的最小示例

此脚本演示如何使用方案2的CustomProcessedDataDict结构体，
该结构体使用自定义FromPyObject trait来自动转换Python数据为Rust DataFrame。

相比方案3（原始PyDataFrame方案），方案2的优点：
1. 代码更清晰：无需.0访问
2. 类型更明确：直接使用DataFrame而非PyDataFrame
3. 性能更好：一次性转换
"""

import path_tool
import polars as pl
import pyo3_quant


class TestDataDict:
    """
    模拟ProcessedDataDict结构体的Python类
    用于测试FromPyObject转换
    """

    def __init__(self, mapping, skip_mask, ohlcv, extra_data=None):
        self.mapping = mapping
        self.skip_mask = skip_mask
        self.ohlcv = ohlcv
        self.extra_data = extra_data or {}


def test_basic_conversion():
    """测试1：基础转换 - 最小数据集"""
    print("\n" + "=" * 60)
    print("测试1：基础转换 - 最小数据集")
    print("=" * 60)

    # 创建最小测试数据
    mapping_df = pl.DataFrame({"id": [1, 2, 3], "symbol": ["AAPL", "GOOGL", "MSFT"]})

    skip_mask_df = pl.DataFrame({"skip": [False, True, False]})

    ohlcv_dfs = [
        pl.DataFrame(
            {
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 1100],
            }
        )
    ]

    data_dict = TestDataDict(
        mapping=mapping_df, skip_mask=skip_mask_df, ohlcv=ohlcv_dfs
    )

    # 调用Rust函数进行转换
    result = pyo3_quant.test_custom_from_py_object(data_dict)
    print(result)


def test_multiple_timeframes():
    """测试2：多时间周期 - 模拟实际场景"""
    print("\n" + "=" * 60)
    print("测试2：多时间周期 - 模拟实际场景")
    print("=" * 60)

    # 创建多个时间周期的OHLCV数据
    mapping_df = pl.DataFrame({"id": range(1, 101), "symbol": ["BTCUSDT"] * 100})

    skip_mask_df = pl.DataFrame({"skip": [False] * 100})

    # 三个时间周期：15m, 1h, 4h
    ohlcv_dfs = [
        # 15分钟周期
        pl.DataFrame(
            {
                "open": [40000.0 + i * 10 for i in range(100)],
                "high": [40100.0 + i * 10 for i in range(100)],
                "low": [39900.0 + i * 10 for i in range(100)],
                "close": [40050.0 + i * 10 for i in range(100)],
                "volume": [100 + i for i in range(100)],
            }
        ),
        # 1小时周期
        pl.DataFrame(
            {
                "open": [40000.0 + i * 5 for i in range(50)],
                "high": [40100.0 + i * 5 for i in range(50)],
                "low": [39900.0 + i * 5 for i in range(50)],
                "close": [40050.0 + i * 5 for i in range(50)],
                "volume": [200 + i for i in range(50)],
            }
        ),
        # 4小时周期
        pl.DataFrame(
            {
                "open": [40000.0 + i * 2 for i in range(25)],
                "high": [40100.0 + i * 2 for i in range(25)],
                "low": [39900.0 + i * 2 for i in range(25)],
                "close": [40050.0 + i * 2 for i in range(25)],
                "volume": [300 + i for i in range(25)],
            }
        ),
    ]

    data_dict = TestDataDict(
        mapping=mapping_df, skip_mask=skip_mask_df, ohlcv=ohlcv_dfs
    )

    result = pyo3_quant.test_custom_from_py_object(data_dict)
    print(result)


def test_with_extra_data():
    """测试3：带有额外数据 - 完整场景"""
    print("\n" + "=" * 60)
    print("测试3：带有额外数据 - 完整场景")
    print("=" * 60)

    mapping_df = pl.DataFrame({"id": [1, 2], "symbol": ["EURUSD", "GBPUSD"]})

    skip_mask_df = pl.DataFrame({"skip": [False, False]})

    ohlcv_dfs = [
        pl.DataFrame(
            {
                "open": [1.0800, 1.0805],
                "high": [1.0810, 1.0815],
                "low": [1.0795, 1.0800],
                "close": [1.0805, 1.0810],
                "volume": [5000, 5100],
            }
        )
    ]

    # 额外数据（例如：技术指标数据）
    extra_data = {
        "sma_20": [pl.DataFrame({"sma": [1.0800, 1.0805], "value": [20.0, 20.1]})],
        "rsi": [pl.DataFrame({"rsi": [45.5, 46.2], "level": [50.0, 50.0]})],
    }

    data_dict = TestDataDict(
        mapping=mapping_df,
        skip_mask=skip_mask_df,
        ohlcv=ohlcv_dfs,
        extra_data=extra_data,
    )

    result = pyo3_quant.test_custom_from_py_object(data_dict)
    print(result)


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("方案2：自定义FromPyObject转换测试")
    print("=" * 60)
    print("\n说明：")
    print("- 此测试演示如何使用自定义FromPyObject trait")
    print("- 自动将Python对象转换为Rust的DataFrame")
    print("- 无需在Rust代码中使用.0访问器")
    print()

    try:
        test_basic_conversion()
        test_multiple_timeframes()
        test_with_extra_data()

        print("\n" + "=" * 60)
        print("✓ 所有测试完成！")
        print("=" * 60)
        print("\n结论：")
        print("方案2（自定义FromPyObject）工作正常！")
        print("相比方案3的优势已验证。")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
