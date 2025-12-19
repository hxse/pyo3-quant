import time
from loguru import logger
import json

# 项目导入
import pyo3_quant

from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.types import (
    BacktestParams,
    IndicatorsParams,
    Param,
    PerformanceParams,
    LogicOp,
    SignalGroup,
    SignalParams,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)

from py_entry.data_conversion.data_generator import DataGenerationParams, OtherParams

from py_entry.data_conversion.file_utils import (
    SaveConfig,
    UploadConfig,
    RequestConfig,
)


# 创建 DataGenerationParams 对象
simulated_data_config = DataGenerationParams(
    timeframes=["15m", "1h", "4h"],
    start_time=1735689600000,
    num_bars=10000,
    fixed_seed=42,
    BaseDataKey="ohlcv_15m",
)

# 构建指标参数
indicators_params = {
    "ohlcv_15m": {
        "bbands": {
            "period": Param.create(14),
            "std": Param.create(2),
        }
    },
    "ohlcv_1h": {
        "rsi": {
            "period": Param.create(14),
        }
    },
    "ohlcv_4h": {
        "sma_0": {
            "period": Param.create(8),
        },
        "sma_1": {
            "period": Param.create(16),
        },
    },
}

# 自定义信号参数
signal_params = {
    # "rsi_upper": Param.create(70, 60, 80, 5),
    "rsi_center": Param.create(50, 40, 60, 5),
    # "rsi_lower": Param.create(30, 20, 40, 5),
}


# 自定义回测参数
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_fixed=0,
    fee_pct=0.003,
    pause_drawdown=Param.create(0),
    pause_sma=Param.create(0),
    pause_ema=Param.create(0),
    exit_in_bar=True,
    exit_in_bar_fallback=False,
    tsl_per_bar_update=False,
    sl_pct=Param.create(0.02),
    # tp_pct=Param.create(0.05),
    # tsl_pct=Param.create(0.02),
    # sl_atr=Param.create(2),
    tp_atr=Param.create(4),
    tsl_atr=Param.create(2),
    atr_period=Param.create(14),
)

# 自定义信号模板
enter_long_group = SignalGroup(
    logic=LogicOp.AND,
    comparisons=[
        "close > bbands_upper",
        "rsi,ohlcv_1h, > $rsi_center",
        "sma_0,ohlcv_4h, > sma_1,ohlcv_4h,",
    ],
)

enter_short_group = SignalGroup(
    logic=LogicOp.AND,
    comparisons=[
        "close < bbands_lower",
        "rsi,ohlcv_1h, < $rsi_center",
        "sma_0,ohlcv_4h, < sma_1,ohlcv_4h,",
    ],
)

signal_template = SignalTemplate(
    name="multi_timeframe_dynamic_strategy",
    enter_long=enter_long_group,
    enter_short=enter_short_group,
)

# 自定义引擎设置
engine_settings = SettingContainer(
    execution_stage=ExecutionStage.PERFORMANCE,
    return_only_final=False,
)

if __name__ == "__main__":
    # 配置logger

    start_time = time.perf_counter()

    # 创建启用时间测量的 BacktestRunner
    br = BacktestRunner(enable_timing=True)

    # 使用链式调用执行完整的回测流程
    logger.info("开始执行回测流程")

    # 读取配置文件
    with open("data/config.json", "r") as f:
        json_config = json.load(f)

    request_cfg = RequestConfig.create(
        username=json_config["username"],
        password=json_config["password"],
        server_url=json_config["server_url"],
    )

    # 完整的链式调用：配置 -> 运行 -> 添加索引 -> 保存 -> 上传
    br.setup(
        data_source=simulated_data_config,
        indicators_params=indicators_params,
        signal_params=signal_params,
        backtest_params=backtest_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    ).run().format_results_for_export(
        export_index=0, dataframe_format="csv"
    ).save_results(
        SaveConfig(
            output_dir="my_strategy",
        )
    ).upload_results(
        UploadConfig(
            request_config=request_cfg,
            server_dir="my_strategy",
            zip_name="results.zip",
        )
    )

    # 获取结果用于打印
    backtest_result = br.results

    print(backtest_result)
    if backtest_result:
        logger.info(f"performance: {backtest_result[0].performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")
