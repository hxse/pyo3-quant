"""
信号生成器集成测试

本测试文件验证回测引擎信号生成模块的正确性，通过以下方式：
1. 运行回测引擎获取信号结果
2. 使用相同的指标数据手动计算信号
3. 比较两种方法的结果是否一致

测试覆盖：
- 多时间框架指标（ohlcv_0, ohlcv_1, ohlcv_2）
- 多种指标类型（SMA, RSI, BBands）
- 复杂信号逻辑（AND组合，OR组合）
- 多种比较操作符（GT, LT, CGT）
- 信号参数使用

运行方式：
pytest py_entry/Test/signal/test_signal_generation.py
"""

from polars.testing import assert_frame_equal

from py_entry.data_conversion.backtest_runner import (
    BacktestRunner,
    DefaultDataBuilder,
)
from py_entry.data_conversion.helpers.data_generator import DataGenerationParams

# 导入自定义构建器和辅助函数
from .custom_builders import (
    CustomParamBuilder,
    CustomSignalTemplateBuilder,
    CustomEngineSettingsBuilder,
)
from .signal_utils import (
    print_signal_statistics,
    calculate_signals_manually,
)


def test_signal_verification():
    """
    测试信号生成器的正确性，通过手动计算验证引擎生成的信号
    """
    # 1. 运行回测获取结果
    runner = BacktestRunner()

    # 配置数据但先不运行，获取DataContainer用于手动计算
    simulated_data_config = DataGenerationParams(
        timeframes=["15m", "1h", "4h"],
        start_time=1735689600000,
        num_bars=5000,
    )

    runner.with_data(
        simulated_data_config=simulated_data_config,
        data_builder=DefaultDataBuilder(),
    )

    # 获取DataContainer用于手动计算
    data_container = runner._data_dict
    assert data_container is not None, "DataContainer不应为None"

    # 继续配置其他参数并运行回测
    backtest_results = (
        runner.with_param_set(param_builder=CustomParamBuilder())
        .with_templates(
            signal_template_builder=CustomSignalTemplateBuilder(),
        )
        .with_engine_settings(engine_settings_builder=CustomEngineSettingsBuilder())
        .run()
    )

    # 2. 提取第一个回测结果
    backtest_summary = backtest_results[0]

    # 3. 验证结果结构
    assert backtest_summary.signals is not None, "回测结果应包含signals数据"
    assert backtest_summary.indicators is not None, "回测结果应包含indicators数据"

    # 4. 提取indicators和signals
    engine_signals = backtest_summary.signals
    indicators = backtest_summary.indicators["ohlcv"]

    # 5. 获取各时间框架的指标数据
    indicators_0 = indicators[0]  # ohlcv_0
    indicators_1 = indicators[1]  # ohlcv_1
    indicators_2 = indicators[2]  # ohlcv_2

    ohlcv_0 = data_container.source["ohlcv"][0]
    ohlcv_1 = data_container.source["ohlcv"][1]
    ohlcv_2 = data_container.source["ohlcv"][2]

    # 6. 获取信号参数
    param_set = runner._param_set
    assert param_set is not None, "参数集不应为None"
    signal_params = param_set[0].signal

    # 8. 手动计算信号
    # 暂时简化测试，只验证前两个条件，忽略第三个条件
    manual_signals = calculate_signals_manually(
        data_container,
        signal_params,
        indicators_0,
        indicators_1,
        indicators_2,
        ohlcv_0,
        ohlcv_1,
        ohlcv_2,
    )

    # 8. 打印统计信息
    print_signal_statistics(engine_signals, "引擎生成信号统计")
    print_signal_statistics(manual_signals, "手动计算信号统计")

    assert_frame_equal(engine_signals, manual_signals)


if __name__ == "__main__":
    test_signal_verification()
