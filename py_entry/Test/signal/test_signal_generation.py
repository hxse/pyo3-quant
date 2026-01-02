"""
信号生成器集成测试 - 参数化多场景测试

本测试文件验证回测引擎信号生成模块的正确性，通过以下方式：
1. 加载多个测试场景
2. 对每个场景运行回测引擎获取信号结果
3. 使用手写计算函数计算期望结果
4. 比较两种方法的结果是否一致

测试覆盖：
- 偏移类型：AND范围、OR范围、AND列表、OR列表
- 交叉比较：向上突破、向下跌破
- 逻辑组合：AND、OR
- 参数引用：$param_name
"""

import pytest
from polars.testing import assert_frame_equal

from py_entry.data_generator import DataGenerationParams, OtherParams
from py_entry.runner import BacktestRunner, SetupConfig
from py_entry.types import SettingContainer, ExecutionStage

from py_entry.Test.signal.scenarios import get_all_scenarios
from py_entry.Test.signal.utils import (
    print_signal_statistics,
    print_comparison_details,
    prepare_mapped_data,
)


@pytest.fixture(scope="module")
def setting_container():
    """设置容器（所有场景共享）"""
    return SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,  # 使用PERFORMANCE而不是SIGNAL
    )


# 加载所有测试场景
all_scenarios = get_all_scenarios()


@pytest.mark.parametrize("scenario", all_scenarios, ids=[s.name for s in all_scenarios])
def test_signal_scenario(scenario, setting_container):
    """
    参数化测试：验证每个场景的信号生成正确性

    参数：
        scenario: TestScenario 对象
        data_gen_params: 数据生成参数 fixture
        setting_container: 设置容器 fixture
    """
    print("\n" + "=" * 60)
    print(f"测试场景: {scenario.name}")
    print(f"描述: {scenario.description}")
    print("=" * 60)

    data_gen_params = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=None,  # 使用默认时间
        num_bars=10000,  # 生成10000根K线
        fixed_seed=42,  # 使用固定种子保证可重现
        base_data_key="ohlcv_15m",  # 基础数据键
    )
    other_params = OtherParams(
        ha_timeframes=["15m", "1h", "4h"],
        renko_timeframes=["15m", "1h", "4h"],
    )

    # 1. 创建回测运行器
    runner = BacktestRunner()

    # 2. 根据是否有预期异常来决定测试逻辑
    if scenario.expected_exception is None:
        # 预期成功的场景

        runner.setup(
            SetupConfig(
                data_source=data_gen_params,
                other_params=other_params,
                indicators=scenario.indicators_params,
                signal=scenario.signal_params,
                signal_template=scenario.signal_template,
                engine_settings=setting_container,
            )
        )

        runner.run()
        assert runner.results is not None, "回测结果不应为空"
        backtest_summary = runner.results[0]

        # 2. 验证结果结构
        assert backtest_summary.signals is not None, "回测结果应包含signals数据"
        assert backtest_summary.indicators is not None, "回测结果应包含indicators数据"

        # 3. 提取引擎生成的信号
        engine_signals = backtest_summary.signals

        # 4. 准备映射后的数据（所有数据已映射到基准周期）

        data_container = runner.data_dict
        assert data_container is not None, "data_container 不应为空"

        # 准备原始和映射后的两组数据
        mapped_data_container, mapped_backtest_summary = prepare_mapped_data(
            data_container, backtest_summary
        )

        # 5. 使用场景的手写计算函数计算期望信号
        # 传入原始和映射后的两组数据
        manual_signals = scenario.manual_calculator(
            scenario.signal_params,
            data_container,
            backtest_summary,
            mapped_data_container,
            mapped_backtest_summary,
        )

        # 6. 打印统计信息
        print_signal_statistics(engine_signals, "引擎生成信号统计")
        print_signal_statistics(manual_signals, "手动计算信号统计")

        # 7. 对比结果（如果不一致，打印详情）
        try:
            # 临时移除 has_leading_nan 列进行对比，因为手动计算函数尚未适配此列
            engine_signals_to_compare = (
                engine_signals.drop("has_leading_nan")
                if "has_leading_nan" in engine_signals.columns
                else engine_signals
            )
            assert_frame_equal(engine_signals_to_compare, manual_signals)
            print(f"\n✓ 场景 {scenario.name} 测试通过！")
        except AssertionError:
            print(f"\n✗ 场景 {scenario.name} 测试失败！")
            print_comparison_details(engine_signals, manual_signals)
            raise
    else:
        # 预期报错的场景

        runner.setup(
            SetupConfig(
                data_source=data_gen_params,
                indicators=scenario.indicators_params,
                signal=scenario.signal_params,
                signal_template=scenario.signal_template,
                engine_settings=setting_container,
            )
        )

        # 3. 运行回测，预期会报错

        with pytest.raises(scenario.expected_exception) as exc_info:
            runner.run()

        # 4. 验证错误信息包含相关关键词
        error_message = str(exc_info.value)
        print(f"捕获到预期错误: {error_message}")

        # 根据场景类型验证错误信息
        if "mixed_logic" in scenario.name:
            assert "Invalid offset" in error_message, (
                "混合逻辑错误应该包含'Invalid offset'"
            )
            assert "combination" in error_message.lower(), (
                "混合逻辑错误应该包含'combination'"
            )
        elif "length_mismatch" in scenario.name:
            assert "Invalid offset" in error_message, (
                "长度不匹配错误应该包含'Invalid offset'"
            )
            assert "长度不匹配" in error_message, "长度不匹配错误应该包含'长度不匹配'"
        elif "negative" in scenario.name:
            # 负数offset可能在解析阶段就报错
            assert any(
                keyword in error_message.lower()
                for keyword in ["parse", "invalid", "negative"]
            ), "负数offset错误应该包含解析相关关键词"

        print(f"✓ 场景 {scenario.name} 错误验证通过！")


def test_all_scenarios_loaded():
    """验证至少加载了一些测试场景"""
    assert len(all_scenarios) > 0, "应该至少有一个测试场景"
    print(f"\n加载了 {len(all_scenarios)} 个测试场景:")
    for scenario in all_scenarios:
        print(f"  - {scenario.name}: {scenario.description}")
