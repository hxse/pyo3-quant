"""
使用真实数据进行回测的示例

从 API 获取真实 OHLCV 数据，而不是使用模拟数据
"""

import time
from loguru import logger

from py_entry.runner import Backtest, RunResult, FormatResultsConfig
from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.io import load_local_config
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.strategies import get_strategy
from py_entry.strategies.base import StrategyConfig


def get_real_data_backtest_config() -> StrategyConfig:
    """
    获取 real_data_backtest 示例的完整策略配置。

    说明：
    1. example 层对外返回统一 StrategyConfig；
    2. 仅覆盖数据源为真实数据，其余参数复用公共示例策略。
    """
    # 1. 加载请求配置（失败即报错，避免静默返回 None）。
    request_config = load_local_config()

    # 2. 配置真实数据源。
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

    # 3. 从公共策略读取其余配置，保证示例口径一致。
    base_cfg = get_strategy("mtf_bbands_rsi_sma")
    return StrategyConfig(
        name="real_data_backtest",
        description="真实数据回测示例（复用 mtf_bbands_rsi_sma 参数）",
        data_config=real_data_config,
        indicators_params=base_cfg.indicators_params,
        signal_params=base_cfg.signal_params,
        backtest_params=base_cfg.backtest_params,
        signal_template=base_cfg.signal_template,
        engine_settings=base_cfg.engine_settings,
        performance_params=base_cfg.performance_params,
    )


def run_real_data_backtest(*, config: StrategyConfig | None = None) -> RunResult:
    """使用真实数据运行回测。"""
    start_time = time.perf_counter()
    logger.info("开始执行真实数据回测")

    # 统一复用 StrategyConfig：未传入时使用默认真实数据配置。
    cfg = config if config is not None else get_real_data_backtest_config()

    # 4. 创建并运行回测。
    bt = Backtest(
        enable_timing=True,
        data_source=cfg.data_config,
        indicators=cfg.indicators_params,
        signal=cfg.signal_params,
        backtest=cfg.backtest_params,
        performance=cfg.performance_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
    )

    result = bt.run()

    result.format_for_export(FormatResultsConfig(dataframe_format="csv"))

    if result.summary:
        logger.info(f"performance: {result.summary.performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")
    return result


def format_result_for_ai(result: RunResult, elapsed_seconds: float) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== REAL_DATA_BACKTEST_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")
    if result.summary is None:
        lines.append("result=present")
        lines.append("summary=None")
    else:
        lines.append("result=present")
        lines.append(f"performance={result.summary.performance}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑用于 AI 调试与结果读取。
    main_start_time = time.perf_counter()
    main_cfg = get_real_data_backtest_config()
    main_result = run_real_data_backtest(config=main_cfg)
    main_elapsed_seconds = time.perf_counter() - main_start_time
    print(format_result_for_ai(main_result, main_elapsed_seconds))
