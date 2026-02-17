import time
from loguru import logger

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
from py_entry.data_generator.time_utils import get_utc_timestamp_ms

from py_entry.io import (
    SaveConfig,
    UploadConfig,
)


# 创建 DataGenerationParams 对象
simulated_data_config = DataGenerationParams(
    timeframes=["15m", "1h", "4h"],
    start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
    num_bars=10000,
    fixed_seed=42,
    base_data_key="ohlcv_15m",
)

# 构建指标参数
indicators_params = {
    "ohlcv_15m": {
        "bbands": {
            "period": Param(14),
            "std": Param(2),
        }
    },
    "ohlcv_1h": {
        "rsi": {
            "period": Param(14),
        }
    },
    "ohlcv_4h": {
        "sma_0": {
            "period": Param(8),
        },
        "sma_1": {
            "period": Param(16),
        },
    },
}

# 自定义信号参数
signal_params = {
    # "rsi_upper": Param(70, 60, 80, 5),
    "rsi_center": Param(50, min=40, max=60, step=5),
    # "rsi_lower": Param(30, 20, 40, 5),
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
    sl_pct=Param(0.02),
    # tp_pct=Param(0.06),
    # tsl_pct=Param(0.02),
    # sl_atr=Param(2),
    tp_atr=Param(6),
    tsl_atr=Param(2),
    atr_period=Param(14),
    tsl_psar_af0=Param(0.02),
    tsl_psar_af_step=Param(0.02),
    tsl_psar_max_af=Param(0.2),
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
    execution_stage=ExecutionStage.Performance,
    return_only_final=False,
)


def run_custom_backtest(
    *,
    save_result: bool = True,
    upload_result: bool = True,
) -> RunResult:
    """
    运行自定义回测流程

    Args:
        save_result: 是否保存结果到本地目录。
        upload_result: 是否尝试上传结果到远端服务。
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

    # 运行并格式化（图表展示依赖导出缓存）
    result = bt.run()
    result = result.format_for_export(FormatResultsConfig(dataframe_format="csv"))

    if save_result:
        result.save(
            SaveConfig(
                output_dir="my_strategy",
            )
        )

    # 根据开关决定是否上传，避免在无网络/无凭证环境中产生副作用。
    if upload_result:
        try:
            from py_entry.io import load_local_config

            request_cfg = load_local_config()

            logger.info("正在上传结果...")
            result.upload(
                UploadConfig(
                    request_config=request_cfg,
                    server_dir="my_strategy",
                    zip_name="results.zip",
                )
            )
        except FileNotFoundError:
            logger.warning("跳过上传：未找到配置文件 config.json")
        except Exception as e:
            logger.error(f"上传失败: {e}")

    # 获取结果用于打印
    # RunResult.summary contains the summary
    if result.summary:
        logger.info(f"performance: {result.summary.performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")

    return result


def format_result_for_ai(result: RunResult, elapsed_seconds: float) -> str:
    """将回测结果整理为便于 AI 读取的纯文本摘要。"""
    lines: list[str] = []
    lines.append("=== CUSTOM_BACKTEST_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")

    # 统一输出 summary，避免 AI 读取日志时遗漏关键指标。
    if result.summary is None:
        lines.append("summary=None")
    else:
        lines.append("summary=present")
        lines.append(f"performance={result.summary.performance}")

    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑场景仅用于结果阅读，默认禁用保存/上传副作用。
    main_start_time = time.perf_counter()
    main_result = run_custom_backtest(save_result=False, upload_result=False)
    main_elapsed_seconds = time.perf_counter() - main_start_time
    print(format_result_for_ai(main_result, main_elapsed_seconds))
