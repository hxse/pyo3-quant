import sys
from pathlib import Path

root_path = next(
    (p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file()),
    None,
)
if root_path:
    sys.path.insert(0, str(root_path))

# 所有导入必须在 sys.path 修改之后立即进行
import time
from loguru import logger

# 项目导入
import pyo3_quant

from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
)
from py_entry.data_conversion.types import (
    BacktestParams,
    CompareOp,
    IndicatorsParams,
    LogicOp,
    Param,
    PerformanceParams,
    SignalGroup,
    SignalParams,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)
from py_entry.Test.utils.backtest_data_exporter import export_backtest_data_to_csv

from py_entry.data_conversion.data_generator import DataGenerationParams

# 创建 DataGenerationParams 对象
simulated_data_config = DataGenerationParams(
    timeframes=["15m", "1h", "4h"],
    start_time=1735689600000,
    num_bars=10000,
    fixed_seed=True,
)

# 构建指标参数
indicators_params = {
    "ohlcv": [
        {
            "bbands_0": {
                "period": Param.create(14),
                "std": Param.create(2),
            }
        },
        {
            "rsi_0": {
                "period": Param.create(14),
            }
        },
        {
            "sma_0": {
                "period": Param.create(8),
            },
            "sma_1": {
                "period": Param.create(16),
            },
        },
    ]
}

# 自定义信号参数
signal_params = {"rsi_midline": Param.create(20, 10, 90, 5)}

# 自定义回测参数
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_fixed=1,
    fee_pct=0.001,
    pause_drawdown=Param.create(0, 0, 0, 0),
    pause_sma=Param.create(0, 0, 0, 0),
    pause_ema=Param.create(0, 0, 0, 0),
    exit_in_bar=False,
    exit_in_bar_fallback=False,
    tsl_per_bar_update=False,
    sl_pct=Param.create(2, 0.5, 5, 0.1),
    tp_pct=Param.create(2, 0.5, 5, 0.1),
    tsl_pct=Param.create(1, 0.5, 3, 0.1),
    sl_atr=Param.create(2, 1, 5, 0.5),
    tp_atr=Param.create(3, 1, 5, 0.5),
    tsl_atr=Param.create(2, 1, 4, 0.5),
    atr_period=Param.create(14, 7, 21, 1),
)

# 自定义信号模板
enter_long_group = SignalGroup(
    logic=LogicOp.AND,
    conditions=[
        signal_data_vs_data(
            compare=CompareOp.GT,
            a_name="sma_0",
            a_source="ohlcv_2",
            a_offset=0,
            b_name="sma_1",
            b_source="ohlcv_2",
            b_offset=0,
        ),
        signal_data_vs_param(
            compare=CompareOp.GT,
            a_name="rsi_0",
            a_source="ohlcv_1",
            a_offset=0,
            b_param="rsi_midline",
        ),
        signal_data_vs_data(
            compare=CompareOp.CGT,
            a_name="close",
            a_source="ohlcv_0",
            a_offset=0,
            b_name="bbands_0_upper",
            b_source="ohlcv_0",
            b_offset=0,
        ),
    ],
)

signal_template = SignalTemplate(
    name="multi_timeframe_dynamic_strategy", enter_long=[enter_long_group]
)

# 自定义引擎设置
engine_settings = SettingContainer(
    execution_stage=ExecutionStage.PERFORMANCE,
    return_only_final=False,
)

if __name__ == "__main__":
    print("-" * 30)
    start_time = time.perf_counter()
    res = pyo3_quant.minimal_working_example.sum_as_string(5, 25)
    print("sum_as_string:", res)
    print("耗时", time.perf_counter() - start_time)

    print("-" * 30)
    start_time = time.perf_counter()

    br = BacktestRunner()

    # 使用新的 setup 方法一次性配置所有参数
    br.setup(
        data_source=simulated_data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    # 执行回测
    backtest_result = br.run()

    print(backtest_result)
    logger.info(f"performance: {backtest_result[0].performance}")

    logger.info(f"耗时 {time.perf_counter() - start_time}")

    # 导出回测数据到CSV文件
    print("\n" + "=" * 50)
    print("开始导出回测数据...")
    # 获取数据容器，确保不为None
    data_container = br.data_dict  # type: ignore[attr-defined]
    if data_container is not None:
        export_backtest_data_to_csv(
            backtest_summary=backtest_result[0], data_container=data_container
        )
    print("=" * 50)
