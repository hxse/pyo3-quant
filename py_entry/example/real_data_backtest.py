"""
使用真实数据进行回测的示例

从 API 获取真实 OHLCV 数据，而不是使用模拟数据
"""

import time
from loguru import logger

from py_entry.runner import Backtest, RunResult, FormatResultsConfig
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
from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.io import load_local_config
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


def run_real_data_backtest() -> RunResult | None:
    """使用真实数据运行回测"""
    start_time = time.perf_counter()
    logger.info("开始执行真实数据回测")

    try:
        # 1. 加载配置
        request_config = load_local_config()
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        return None

    # 2. 配置真实数据源
    real_data_config = OhlcvDataFetchConfig(
        config=request_config,
        exchange_name="binance",
        market="future",
        symbol="BTC/USDT",
        timeframes=["15m", "1h", "4h"],
        since=get_utc_timestamp_ms("2025-12-01 00:00:00"),
        limit=5000,  # 只需要少量数据做演示
        enable_cache=True,
        mode="sandbox",
        base_data_key="ohlcv_15m",
    )

    # 3. 配置指标参数
    indicators_params = {
        "ohlcv_15m": {
            "bbands": {"period": Param(14), "std": Param(2)},
        },
        "ohlcv_1h": {
            "rsi": {"period": Param(14)},
        },
        "ohlcv_4h": {
            "sma_0": {"period": Param(8)},
            "sma_1": {"period": Param(16)},
        },
    }

    # 4. 配置信号参数
    signal_params = {"rsi_center": Param(50, min=40, max=60, step=5)}

    # 5. 配置回测参数
    backtest_params = BacktestParams(
        initial_capital=10000.0,
        fee_fixed=0.0,
        fee_pct=0.001,
        sl_pct=Param(0.02),
        tp_atr=Param(4),
        tsl_atr=Param(2),
        atr_period=Param(14),
    )

    # 6. 配置性能参数
    performance_params = PerformanceParams(
        metrics=[
            PerformanceMetric.TotalReturn,
            PerformanceMetric.MaxDrawdown,
            PerformanceMetric.CalmarRatio,
        ],
    )

    # 7. 配置信号模板
    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                "close > bbands_upper",
                "rsi,ohlcv_1h, > $rsi_center",
                "sma_0,ohlcv_4h, > sma_1,ohlcv_4h,",
            ],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[
                "close < bbands_lower",
                "rsi,ohlcv_1h, < $rsi_center",
                "sma_0,ohlcv_4h, < sma_1,ohlcv_4h,",
            ],
        ),
    )

    # 8. 创建并运行回测
    bt = Backtest(
        enable_timing=True,
        data_source=real_data_config,  # 使用真实数据配置
        indicators=indicators_params,
        signal=signal_params,
        backtest=backtest_params,
        performance=performance_params,
        signal_template=signal_template,
        engine_settings=SettingContainer(execution_stage=ExecutionStage.Performance),
    )

    result = bt.run()

    result.format_for_export(FormatResultsConfig(dataframe_format="csv"))

    if result.summary:
        logger.info(f"performance: {result.summary.performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")
    return result


def format_result_for_ai(result: RunResult | None, elapsed_seconds: float) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== REAL_DATA_BACKTEST_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")
    if result is None:
        lines.append("result=None")
    elif result.summary is None:
        lines.append("result=present")
        lines.append("summary=None")
    else:
        lines.append("result=present")
        lines.append(f"performance={result.summary.performance}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑用于 AI 调试与结果读取。
    main_start_time = time.perf_counter()
    main_result = run_real_data_backtest()
    main_elapsed_seconds = time.perf_counter() - main_start_time
    print(format_result_for_ai(main_result, main_elapsed_seconds))
