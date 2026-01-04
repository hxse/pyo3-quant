import time
from loguru import logger
import json
from pathlib import Path

# 项目导入

from py_entry.runner import (
    Backtest,
    RunResult,
    FormatResultsConfig,
)
from py_entry.types import (
    BacktestParams,
    Param,
    PerformanceParams,
    PerformanceMetric,
    LogicOp,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)

from py_entry.data_generator import DataGenerationParams

from py_entry.io import (
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
    base_data_key="ohlcv_15m",
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
    "rsi_center": Param.create(50, min=40, max=60, step=5),
    # "rsi_lower": Param.create(30, 20, 40, 5),
}


# 自定义回测参数
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_fixed=0,
    fee_pct=0.001,
    sl_exit_in_bar=True,
    tp_exit_in_bar=True,
    sl_trigger_mode=True,
    tp_trigger_mode=True,
    tsl_trigger_mode=True,
    sl_anchor_mode=False,
    tp_anchor_mode=False,
    tsl_anchor_mode=False,
    tsl_atr_tight=True,
    sl_pct=Param.create(0.02),
    # tp_pct=Param.create(0.06),
    # tsl_pct=Param.create(0.02),
    # sl_atr=Param.create(2),
    tp_atr=Param.create(6),
    tsl_atr=Param.create(2),
    atr_period=Param.create(14),
    tsl_psar_af0=Param.create(0.02),
    tsl_psar_af_step=Param.create(0.02),
    tsl_psar_max_af=Param.create(0.2),
)

# 自定义性能参数
performance_params = PerformanceParams(
    metrics=[
        PerformanceMetric.TotalReturn,
        PerformanceMetric.MaxDrawdown,
        PerformanceMetric.CalmarRatio,
        PerformanceMetric.AnnualizationFactor,
        PerformanceMetric.HasLeadingNanCount,
    ],
    leverage_safety_factor=0.8,
)

# 自定义信号模板
entry_long_group = SignalGroup(
    logic=LogicOp.AND,
    comparisons=[
        "close > bbands_upper",
        "rsi,ohlcv_1h, > $rsi_center",
        "sma_0,ohlcv_4h, > sma_1,ohlcv_4h,",
    ],
)

entry_short_group = SignalGroup(
    logic=LogicOp.AND,
    comparisons=[
        "close < bbands_lower",
        "rsi,ohlcv_1h, < $rsi_center",
        "sma_0,ohlcv_4h, < sma_1,ohlcv_4h,",
    ],
)

signal_template = SignalTemplate(
    entry_long=entry_long_group,
    entry_short=entry_short_group,
)

# 自定义引擎设置
engine_settings = SettingContainer(
    execution_stage=ExecutionStage.PERFORMANCE,
    return_only_final=False,
)


def run_custom_backtest() -> RunResult:
    """
    运行自定义回测流程
    """
    # 配置logger

    start_time = time.perf_counter()

    # 使用链式调用执行完整的回测流程
    logger.info("开始执行回测流程")

    # 创建 Backtest
    bt = Backtest(
        enable_timing=True,
        data_source=simulated_data_config,
        indicators=indicators_params,
        signal=signal_params,
        backtest=backtest_params,
        performance=performance_params,
        signal_template=signal_template,
        engine_settings=engine_settings,
    )

    # 运行 -> 格式化 -> 保存
    result = bt.run()

    result.format_for_export(FormatResultsConfig(dataframe_format="csv")).save(
        SaveConfig(
            output_dir="my_strategy",
        )
    )

    # 尝试读取配置文件并上传
    config_path = "data/config.json"
    if not Path(config_path).exists():
        # 尝试相对于当前文件的路径
        current_file_path = Path(__file__).resolve().parent
        config_path = current_file_path / "data/config.json"

    if Path(config_path).exists():
        with open(config_path, "r") as f:
            json_config = json.load(f)

        request_cfg = RequestConfig.create(
            username=json_config["username"],
            password=json_config["password"],
            server_url=json_config["server_url"],
        )

        logger.info("正在上传结果...")
        result.upload(
            UploadConfig(
                request_config=request_cfg,
                server_dir="my_strategy",
                zip_name="results.zip",
            )
        )
    else:
        logger.warning(f"跳过上传：未找到配置文件 {config_path}")

    # 获取结果用于打印
    # RunResult.summary contains the summary
    if result.summary:
        logger.info(f"performance: {result.summary.performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")

    return result


if __name__ == "__main__":
    run_custom_backtest()
