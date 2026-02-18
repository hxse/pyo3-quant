import time
from loguru import logger

from py_entry.runner import Backtest, FormatResultsConfig, RunResult
from py_entry.strategies import get_strategy
from py_entry.strategies.base import StrategyConfig


def get_reversal_extreme_config() -> StrategyConfig:
    """获取 reversal_extreme 示例的完整策略配置。"""
    return get_strategy("reversal_extreme")


def run_reversal_extreme_backtest(*, config: StrategyConfig | None = None) -> RunResult:
    """运行 reversal_extreme 示例回测。"""
    start_time = time.perf_counter()
    logger.info("开始执行 reversal_extreme 示例回测")

    cfg = config if config is not None else get_reversal_extreme_config()
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
    result = bt.run().format_for_export(FormatResultsConfig(dataframe_format="csv"))
    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")
    return result


def format_result_for_ai(result: RunResult, elapsed_seconds: float) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== REVERSAL_EXTREME_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")
    if result.summary is None:
        lines.append("summary=None")
    else:
        lines.append(f"performance={result.summary.performance}")
    return "\n".join(lines)


if __name__ == "__main__":
    start_time = time.perf_counter()
    run_result = run_reversal_extreme_backtest()
    elapsed_seconds = time.perf_counter() - start_time
    print(format_result_for_ai(run_result, elapsed_seconds))
