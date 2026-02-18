from py_entry.types import (
    ExecutionStage,
    Param,
    SignalGroup,
    LogicOp,
    SignalTemplate,
)
from py_entry.data_generator import DataGenerationParams
from py_entry.Test.shared import (
    make_backtest_runner,
    make_engine_settings,
)


def test_leading_nan_tracking():
    """
    测试 has_leading_nan 列的正确性。
    使用不同周期的指标，验证前导 NaN 掩码是否正确合并。
    """
    # 1. 准备数据生成参数
    # 生成足够长的数据以平摊指标预热期
    num_bars = 100
    data_gen_params = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=1735689600000,
        num_bars=num_bars,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 2. 构建指标参数
    # sma_0 (ohlcv_15m, period=10) -> 需要 9 个前导 NaN (如果 polars 实现是这样)
    # sma_1 (ohlcv_15m, period=20) -> 需要 19 个前导 NaN
    # rsi (ohlcv_1h, period=14) -> 需要 13 个 1h bar，对应到 15m 就是 13 * 4 = 52 个 bar (如果 1h 对齐到 15m)
    # 我们保持简单，先用同一个周期的指标
    indicators_params = {
        "ohlcv_15m": {
            "sma_10": {
                "period": Param(10),
            },
            "sma_20": {
                "period": Param(20),
            },
        }
    }

    # 3. 定义信号模板
    # 使用这两个指标进行比较
    entry_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_10 > sma_20",
        ],
    )

    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_10 < sma_20",
        ],
    )

    signal_template = SignalTemplate(
        entry_long=entry_long_group,
        exit_long=exit_long_group,
    )

    # 4. 运行回测引擎
    # 4. 运行回测引擎
    runner = make_backtest_runner(
        data_source=data_gen_params,
        indicators=indicators_params,
        signal_template=signal_template,
        engine_settings=make_engine_settings(
            execution_stage=ExecutionStage.Performance
        ),
    )
    result = runner.run()

    # 5. 验证结果
    assert result.summary is not None, "回测结果不应为空"
    backtest_summary = result.summary

    signals = backtest_summary.signals
    indicators = backtest_summary.indicators

    assert signals is not None, "signals 不应为空"
    assert indicators is not None, "indicators 不应为空"
    assert "has_leading_nan" in signals.columns, "输出结果中应包含 has_leading_nan 列"

    # 获取原始指标数据来确认 NaN 范围
    sma_10 = indicators["ohlcv_15m"]["sma_10"]
    sma_20 = indicators["ohlcv_15m"]["sma_20"]

    # 计算预期的 has_leading_nan
    # 只要任意一个指标是 NaN，has_leading_nan 就应该是 True
    expected_mask = sma_10.is_nan() | sma_20.is_nan()

    # 获取引擎生成的 mask
    actual_mask = signals["has_leading_nan"]

    # 打印一些调试信息
    nan_count = actual_mask.sum()

    # 验证掩码一致性（矢量化检查）
    # 注意：我们的逻辑中还包含 is_null()，但在当前数据生成器下通常只有 NaN
    mismatch = actual_mask != expected_mask
    if mismatch.any():
        # 只在有不匹配时才定位具体位置
        first_mismatch_idx = mismatch.arg_true().to_list()[0]
        raise AssertionError(
            f"Mismatch at index {first_mismatch_idx}: "
            f"expected {expected_mask[first_mismatch_idx]}, "
            f"got {actual_mask[first_mismatch_idx]}"
        )

    # 额外验证：sma_20 的周期是 20，如果是 eager 计算，前 19 个应该是 NaN
    # 验证前 19 个 bar 的 has_leading_nan 为 True
    assert actual_mask[:19].all(), "前 19 个 bar 应该包含前导 NaN"
    assert not actual_mask[19], "第 20 个 bar 开始不应该有前导 NaN"


if __name__ == "__main__":
    test_leading_nan_tracking()
