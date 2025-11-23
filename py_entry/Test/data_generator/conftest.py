import pytest
import numpy as np
import polars as pl
from py_entry.data_conversion.helpers.data_generator import (
    generate_data_dict,
    DataGenerationParams,
    generate_ohlcv,
    parse_timeframe,
)


@pytest.fixture(scope="module")
def basic_timeframes():
    """基本的时间周期列表"""
    return ["15m", "1h", "4h"]


@pytest.fixture(scope="module")
def basic_start_time():
    """基本的开始时间"""
    return 1609459200000  # 2021-01-01 00:00:00 UTC


@pytest.fixture(scope="module")
def basic_num_bars():
    """基本的K线数量"""
    return 100


@pytest.fixture(scope="module")
def data_generation_params(basic_timeframes, basic_start_time, basic_num_bars):
    """数据生成参数配置"""
    return DataGenerationParams(
        timeframes=basic_timeframes,
        start_time=basic_start_time,
        num_bars=basic_num_bars,
    )


@pytest.fixture(scope="module")
def sample_data_dict(data_generation_params):
    """示例数据字典"""
    return generate_data_dict(data_source=data_generation_params)


@pytest.fixture(scope="module")
def data_container(data_generation_params):
    """数据容器，用于测试"""
    return generate_data_dict(data_source=data_generation_params)


@pytest.fixture(scope="module")
def multi_timeframe_ohlcv_data(basic_timeframes, basic_start_time, basic_num_bars):
    """多时间周期 OHLCV 数据，用于测试"""
    from py_entry.data_conversion.helpers.data_generator import (
        generate_multi_timeframe_ohlcv,
    )

    return generate_multi_timeframe_ohlcv(
        basic_timeframes, basic_start_time, basic_num_bars
    )


@pytest.fixture(scope="module")
def sample_ohlcv_data():
    """示例OHLCV数据"""
    return pl.DataFrame(
        {
            "time": np.arange(10) * 1000,
            "open": np.random.rand(10) * 100,
            "high": np.random.rand(10) * 100 + 10,
            "low": np.random.rand(10) * 100 - 10,
            "close": np.random.rand(10) * 100,
            "volume": np.random.rand(10) * 1000000,
        }
    )


@pytest.fixture(scope="module")
def sample_time_series():
    """示例时间序列"""
    return pl.Series("time", np.arange(10) * 1000)


@pytest.fixture(scope="module")
def sample_natural_series():
    """示例自然数序列"""
    return pl.Series("natural", np.arange(5))


@pytest.fixture(scope="module")
def sample_non_natural_series():
    """示例非自然数序列"""
    return pl.Series("non_natural", np.array([0, 1, 3, 4]))


@pytest.fixture(scope="module")
def sample_ohlcv_dataframe():
    """示例完整的 OHLCV DataFrame"""
    return pl.DataFrame(
        {
            "time": np.arange(10) * 1000,
            "open": np.random.rand(10) * 100,
            "high": np.random.rand(10) * 100 + 10,
            "low": np.random.rand(10) * 100 - 10,
            "close": np.random.rand(10) * 100,
            "volume": np.random.rand(10) * 1000000,
        }
    )


@pytest.fixture(scope="module")
def partial_match_time_series():
    """部分匹配的时间序列"""
    return np.arange(5) * 2000 + 500  # 500, 2500, 4500, 6500, 8500


@pytest.fixture(scope="module")
def no_match_time_series():
    """完全不匹配的时间序列"""
    return np.arange(3) * 3000 + 1000  # 1000, 4000, 7000


@pytest.fixture(scope="module")
def partial_match_ohlcv_dataframe(partial_match_time_series):
    """部分匹配的 OHLCV DataFrame"""
    return pl.DataFrame(
        {
            "time": partial_match_time_series,
            "open": np.random.rand(5) * 100,
            "high": np.random.rand(5) * 100 + 10,
            "low": np.random.rand(5) * 100 - 10,
            "close": np.random.rand(5) * 100,
            "volume": np.random.rand(5) * 1000000,
        }
    )


@pytest.fixture(scope="module")
def no_match_ohlcv_dataframe(no_match_time_series):
    """完全不匹配的 OHLCV DataFrame"""
    return pl.DataFrame(
        {
            "time": no_match_time_series,
            "open": np.random.rand(3) * 100,
            "high": np.random.rand(3) * 100 + 10,
            "low": np.random.rand(3) * 100 - 10,
            "close": np.random.rand(3) * 100,
            "volume": np.random.rand(3) * 1000000,
        }
    )


@pytest.fixture(scope="module")
def empty_dataframe():
    """空的 DataFrame"""
    return pl.DataFrame({"time": np.array([])})


@pytest.fixture(scope="module")
def sample_null_series():
    """包含 null 值的序列"""
    return pl.Series("test", np.array([0, 1, None, 3]))


@pytest.fixture(scope="module")
def ohlcv_df_factory():
    """生成 OHLCV DataFrame 的工厂 fixture"""

    def _create_ohlcv_df(time_series, num_bars=None):
        if num_bars is None:
            num_bars = len(time_series)
        
        # 如果 time_series 是 numpy array，直接使用
        if isinstance(time_series, np.ndarray):
            times = time_series
        # 如果是 list，转换为 numpy array
        elif isinstance(time_series, list):
            times = np.array(time_series)
        # 如果是 polars Series，转换为 numpy array
        elif isinstance(time_series, pl.Series):
            times = time_series.to_numpy()
        else:
            raise ValueError("Unsupported time_series type")

        return pl.DataFrame(
            {
                "time": times,
                "open": np.random.rand(num_bars) * 100,
                "high": np.random.rand(num_bars) * 100 + 10,
                "low": np.random.rand(num_bars) * 100 - 10,
                "close": np.random.rand(num_bars) * 100,
                "volume": np.random.rand(num_bars) * 1000000,
            }
        )

    return _create_ohlcv_df


@pytest.fixture(scope="module")
def mock_dfs_factory(ohlcv_df_factory):
    """生成 DataFrame 列表的工厂 fixture"""

    def _create_dfs(time_series_list):
        return [ohlcv_df_factory(ts) for ts in time_series_list]

    return _create_dfs


# 辅助函数
def assert_dataframe_structure(df, expected_columns, expected_length=None):
    """验证 DataFrame 结构的辅助函数"""
    # 验证列是否存在
    for col in expected_columns:
        assert col in df.columns, f"缺少列: {col}"

    # 验证行数（如果指定）
    if expected_length is not None:
        assert len(df) == expected_length, (
            f"期望行数 {expected_length}，实际行数 {len(df)}"
        )

    # 验证价格和成交量数据类型
    if "open" in df.columns:
        assert df["open"].dtype == pl.Float64, "open 列应为 Float64 类型"
    if "high" in df.columns:
        assert df["high"].dtype == pl.Float64, "high 列应为 Float64 类型"
    if "low" in df.columns:
        assert df["low"].dtype == pl.Float64, "low 列应为 Float64 类型"
    if "close" in df.columns:
        assert df["close"].dtype == pl.Float64, "close 列应为 Float64 类型"
    if "volume" in df.columns:
        assert df["volume"].dtype == pl.Float64, "volume 列应为 Float64 类型"


def assert_time_series_continuity(df, start_time, interval_ms, expected_length=None):
    """验证时间序列连续性的辅助函数"""
    if expected_length is None:
        expected_length = len(df)

    expected_times = start_time + np.arange(expected_length) * interval_ms
    assert np.array_equal(df["time"].to_numpy(), expected_times), (
        "时间序列不连续或不正确"
    )


def assert_skip_mapping_result(
    skip_mapping, expected_skip_columns, expected_include_columns
):
    """验证跳过映射结果的辅助函数"""
    # 验证应该跳过的列
    for col in expected_skip_columns:
        assert col in skip_mapping, f"列 {col} 应在 skip_mapping 中"
        assert skip_mapping[col] is True, f"列 {col} 应被标记为跳过"

    # 验证不应该跳过的列
    for col in expected_include_columns:
        if col in skip_mapping:  # 列可能在 skip_mapping 中但不应被跳过
            assert skip_mapping[col] is False, f"列 {col} 不应被标记为跳过"
