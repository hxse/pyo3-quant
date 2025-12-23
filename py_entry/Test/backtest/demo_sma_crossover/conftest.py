"""
demo_sma_crossover 的配置文件

此测试用例使用硬编码的 OHLCV 数据和预期输出，验证回测引擎的正确性。

策略：双均线交叉
- 快线：SMA(5)
- 慢线：SMA(10)
- 进场：金叉做多，死叉做空
- 离场：反向交叉
"""

import pytest
from pathlib import Path

from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.data_generator import DataGenerationParams
from py_entry.data_conversion.types import (
    BacktestParams,
    IndicatorsParams,
    SignalParams,
    SignalTemplate,
    SignalGroup,
    LogicOp,
    Param,
    SettingContainer,
    ExecutionStage,
    PerformanceParams,
    PerformanceMetric,
)


@pytest.fixture(scope="module")
def demo_dir():
    """返回当前demo目录的路径"""
    return Path(__file__).parent


def run_sma_crossover_backtest():
    """
    执行 SMA 交叉策略回测 (完全封装，不依赖 pytest)

    Returns:
        BacktestRunner: 包含回测结果的 runner 实例
    """
    br = BacktestRunner()

    # 创建 DataGenerationParams 对象代替读取 CSV
    data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1735689600000,
        num_bars=300,
        fixed_seed=42,
        BaseDataKey="ohlcv_15m",
    )

    # 配置指标参数：SMA(5) 和 SMA(10)
    indicators_params: IndicatorsParams = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param.create(5)},
            "sma_slow": {"period": Param.create(20)},
        },
    }

    # 信号参数：无自定义参数
    signal_params: SignalParams = {}

    # 回测参数：无风控
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=1,
        fee_pct=0.001,  # 0.1%手续费
        pause_drawdown=Param.create(0),
        pause_sma=Param.create(0),
        pause_ema=Param.create(0),
        exit_in_bar=False,
        use_extrema_for_exit=False,
        sl_pct=Param.create(0),
        tp_pct=Param.create(0),
        tsl_pct=Param.create(0),
        sl_atr=Param.create(0),
        tp_atr=Param.create(0),
        tsl_atr=Param.create(0),
        atr_period=Param.create(14),
    )

    # 包含所有性能指标
    performance_params = PerformanceParams(
        metrics=[metric for metric in PerformanceMetric]
    )

    # 信号模板：双均线交叉策略
    enter_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0",
        ],
    )

    enter_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0",
        ],
    )

    exit_long_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 < sma_slow, ohlcv_15m, 0",
        ],
    )

    exit_short_group = SignalGroup(
        logic=LogicOp.AND,
        comparisons=[
            "sma_fast, ohlcv_15m, 0 > sma_slow, ohlcv_15m, 0",
        ],
    )

    signal_template = SignalTemplate(
        enter_long=enter_long_group,
        enter_short=enter_short_group,
        exit_long=exit_long_group,
        exit_short=exit_short_group,
    )

    # 引擎设置
    engine_settings = SettingContainer(
        execution_stage=ExecutionStage.PERFORMANCE,
        return_only_final=False,
    )

    # 执行回测
    br.setup(
        data_source=data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        performance_params=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    br.run()

    # 预先格式化以便 ipynb 仪表板使用
    br.format_results_for_export(export_index=0, dataframe_format="parquet")

    return br


@pytest.fixture(scope="module")
def backtest_result():
    """执行回测并返回结果"""
    br = run_sma_crossover_backtest()
    return br.results


@pytest.fixture
def backtest_df(backtest_result):
    """从回测结果中提取DataFrame"""
    if not backtest_result or not hasattr(backtest_result[0], "backtest_result"):
        return None
    return backtest_result[0].backtest_result
