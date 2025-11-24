"""
信号生成器集成测试

本测试文件验证回测引擎信号生成模块的正确性，通过以下方式：
1. 运行回测引擎获取信号结果
2. 使用相同的指标数据手动计算信号
3. 比较两种方法的结果是否一致

测试覆盖：
- 多时间框架指标（ohlcv_15m, ohlcv_1h, ohlcv_4h）
- 多种指标类型（SMA, RSI, BBands）
- 复杂信号逻辑（AND组合，OR组合）
- 多种比较操作符（GT, LT, CGT）
- 信号参数使用

运行方式：
pytest py_entry/Test/signal/test_signal_generation.py
"""

from polars.testing import assert_frame_equal

# 导入自定义构建器和辅助函数
from .conftest import (
    custom_signal_params,
)
from .signal_utils import (
    print_signal_statistics,
    calculate_signals_manually,
)


def test_signal_verification(signal_backtest_results):
    """
    测试信号生成器的正确性，通过手动计算验证引擎生成的信号
    """
    # 1. 解析返回的结果、数据字典和信号参数
    backtest_summary, data_container, signal_params = signal_backtest_results

    # 3. 验证结果结构
    assert backtest_summary.signals is not None, "回测结果应包含signals数据"
    assert backtest_summary.indicators is not None, "回测结果应包含indicators数据"

    # 4. 提取indicators和signals
    engine_signals = backtest_summary.signals

    # 5. 获取各时间框架的指标数据
    indicators_15m = backtest_summary.indicators["ohlcv_15m"]
    indicators_1h = backtest_summary.indicators["ohlcv_1h"]
    indicators_4h = backtest_summary.indicators["ohlcv_4h"]

    ohlcv_15m = data_container.source["ohlcv_15m"]
    ohlcv_1h = data_container.source["ohlcv_1h"]
    ohlcv_4h = data_container.source["ohlcv_4h"]

    manual_signals = calculate_signals_manually(
        data_container,
        signal_params,
        indicators_15m,
        indicators_1h,
        indicators_4h,
        ohlcv_15m,
        ohlcv_1h,
        ohlcv_4h,
    )

    # 7. 打印统计信息
    print_signal_statistics(engine_signals, "引擎生成信号统计")
    print_signal_statistics(manual_signals, "手动计算信号统计")

    assert_frame_equal(engine_signals, manual_signals)
