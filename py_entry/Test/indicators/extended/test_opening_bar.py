import polars as pl
from py_entry.types import ArtifactRetention, ExecutionStage, Param
from py_entry.data_generator import DirectDataConfig
from py_entry.Test.shared import make_backtest_runner, make_engine_settings


def test_opening_bar_logic_alignment():
    """
    逻辑验证：测试 opening-bar 指标是否能正确识别时间断层。
    """
    # 1. 构造带时间断层的数据 (5分钟周期)
    # T0: 09:00
    # T1: 09:05 (gap 300s)
    # T2: 09:10 (gap 300s)
    # T3: 09:25 (gap 900s, 即 15m 休息结束)
    # T4: 13:30 (gap 大间隙)
    base_time = 1735693200000  # 2025-01-01 09:00:00 MS
    times = [
        base_time,
        base_time + 5 * 60 * 1000,
        base_time + 10 * 60 * 1000,
        base_time + 25 * 60 * 1000,  # 这里的间隙是 15m (900s)
        base_time + 120 * 60 * 1000,  # 这里的间隙是 大于 15m
    ]

    df = pl.DataFrame(
        {
            "time": times,
            "date": ["2025-01-01"] * 5,
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "volume": [1000.0] * 5,
        }
    )

    # 使用 DirectDataConfig 包装数据
    data_config = DirectDataConfig(data={"ohlcv_5m": df}, base_data_key="ohlcv_5m")

    # 2. 测试场景 1: 判定 15 分钟休息不算开盘 (threshold = 900)
    # 预期: T0, T4 是开盘; T1, T2, T3 不是
    indicator_configs = {
        "ohlcv_5m": {
            "opening-bar_0": {
                "threshold": Param(900.0)  # 刚好 15 分钟
            }
        }
    }

    bt = make_backtest_runner(
        data_source=data_config,
        indicators=indicator_configs,
        engine_settings=make_engine_settings(
            stop_stage=ExecutionStage.Indicator,
            artifact_retention=ArtifactRetention.StopStageOnly,
        ),
    )
    result = bt.run()

    indicators_results = result.raw.indicators
    assert indicators_results is not None
    res_df = indicators_results["ohlcv_5m"]
    signals = res_df.get_column("opening-bar_0").cast(pl.Float64, strict=False)

    # T1(300s), T2(300s), T3(900s) 不是开盘 (因为 900 不大于 900)
    # T4(大间隙) 是开盘
    expected_1 = pl.Series("expected_1", [0.0, 0.0, 0.0, 0.0, 1.0], dtype=pl.Float64)
    assert bool((signals == expected_1).all())

    # 3. 测试场景 2: 判定 15 分钟休息也是开盘 (threshold = 899)
    # 预期: T0, T3, T4 是开盘
    indicator_configs_2 = {
        "ohlcv_5m": {
            "opening-bar_1": {
                "threshold": Param(899.0)  # 小于 15 分钟
            }
        }
    }
    bt2 = make_backtest_runner(
        data_source=data_config,
        indicators=indicator_configs_2,
        engine_settings=make_engine_settings(
            stop_stage=ExecutionStage.Indicator,
            artifact_retention=ArtifactRetention.StopStageOnly,
        ),
    )
    result2 = bt2.run()

    indicators_results2 = result2.raw.indicators
    assert indicators_results2 is not None
    res_df2 = indicators_results2["ohlcv_5m"]
    signals2 = res_df2.get_column("opening-bar_1").cast(pl.Float64, strict=False)

    # T0(第一根) 为 0.0, T3(900 > 899), T4 是开盘
    expected_2 = pl.Series("expected_2", [0.0, 0.0, 0.0, 1.0, 1.0], dtype=pl.Float64)
    assert bool((signals2 == expected_2).all())
