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

from py_entry.data_generator import (
    DataGenerationParams,
    DirectDataConfig,
    OtherParams,
    generate_data_pack,
)
from py_entry.types import ExecutionStage
from py_entry.Test.shared import (
    make_backtest_runner,
    make_engine_settings,
)

from py_entry.Test.signal.scenarios import get_all_scenarios
from py_entry.Test.signal.utils import (
    print_signal_statistics,
    print_comparison_details,
    prepare_mapped_data,
)


@pytest.fixture(scope="module")
def setting_container():
    """设置容器（所有场景共享）"""
    return make_engine_settings(
        execution_stage=ExecutionStage.Performance,  # 使用PERFORMANCE而不是SIGNAL
    )


# 加载所有测试场景
all_scenarios = get_all_scenarios()


@pytest.fixture(scope="module")
def shared_data_source():
    """模块级共享数据源（一次生成，多场景复用）。"""
    data_gen_params = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=1735689600000,
        num_bars=10000,  # 保持原数据规模，不改变测试语义
        fixed_seed=42,  # 保持可重现
        base_data_key="ohlcv_15m",
    )
    other_params = OtherParams(
        ha_timeframes=["15m", "1h", "4h"],
        # 中文注释：03-10 最终口径已明确不再支持 renko 重复时间戳 source，
        # 信号总场景共享数据只保留正式支持的 OHLCV / HA。
        renko_timeframes=None,
    )
    # 中文注释：先完整生成一次（含 OHLCV / Heikin-Ashi），后续场景复用同一份源数据。
    data_pack = generate_data_pack(
        data_source=data_gen_params, other_params=other_params
    )
    source_data = {k: v.clone() for k, v in data_pack.source.items()}
    return DirectDataConfig(
        data=source_data, base_data_key=data_gen_params.base_data_key
    )


@pytest.mark.parametrize("scenario", all_scenarios, ids=[s.name for s in all_scenarios])
def test_signal_scenario(scenario, setting_container, shared_data_source):
    """
    参数化测试：验证每个场景的信号生成正确性

    参数：
        scenario: TestScenario 对象
        data_gen_params: 数据生成参数 fixture
        setting_container: 设置容器 fixture
    """
    # 1. 创建回测运行器
    # 1. (已移除提前创建 runner)

    # 2. 根据是否有预期异常来决定测试逻辑
    if scenario.expected_exception is None:
        # 预期成功的场景

        runner = make_backtest_runner(
            data_source=shared_data_source,
            indicators=scenario.indicators_params,
            signal=scenario.signal_params,
            signal_template=scenario.signal_template,
            engine_settings=setting_container,
        )

        result = runner.run()
        backtest_result = result.result

        # 2. 验证结果结构
        assert backtest_result.signals is not None, "回测结果应包含signals数据"
        assert backtest_result.indicators is not None, "回测结果应包含indicators数据"

        # 3. 提取引擎生成的信号
        engine_signals = backtest_result.signals

        # 4. 准备映射后的数据（所有数据已映射到基准周期）

        data_pack = result.data_pack
        assert data_pack is not None, "data_pack 不应为空"

        # 准备原始和映射后的两组数据
        mapped_data_pack, mapped_result_pack = prepare_mapped_data(
            data_pack, backtest_result
        )

        # 5. 使用场景的手写计算函数计算期望信号
        # 传入原始和映射后的两组数据
        manual_signals = scenario.manual_calculator(
            scenario.signal_params,
            data_pack,
            backtest_result,
            mapped_data_pack,
            mapped_result_pack,
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
        except AssertionError:
            print_comparison_details(engine_signals, manual_signals)
            raise
    else:
        # 预期报错的场景

        # 3. 运行回测，预期会报错
        with pytest.raises(scenario.expected_exception) as exc_info:
            runner = make_backtest_runner(
                data_source=shared_data_source,
                indicators=scenario.indicators_params,
                signal=scenario.signal_params,
                signal_template=scenario.signal_template,
                engine_settings=setting_container,
            )
            runner.run()

        # 4. 验证错误信息包含相关关键词
        error_message = str(exc_info.value)

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


def test_all_scenarios_loaded():
    """验证至少加载了一些测试场景"""
    assert len(all_scenarios) > 0, "应该至少有一个测试场景"
