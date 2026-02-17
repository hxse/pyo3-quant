import time
from loguru import logger

from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.runner import Backtest, RunResult


def run_basic_backtest() -> RunResult:
    """运行基础回测，供 ipynb 导入调用。"""
    simulated_data_config = DataGenerationParams(
        timeframes=["15m", "1h"],
        start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
        num_bars=3000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    bt = Backtest(
        enable_timing=True,
        data_source=simulated_data_config,
    )
    return bt.run()


def format_result_for_ai(result: RunResult, elapsed_seconds: float) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== BASIC_BACKTEST_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")
    if result.summary is None:
        lines.append("summary=None")
    else:
        lines.append("summary=present")
        lines.append(f"performance={result.summary.performance}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑用于 AI 调试与结果读取。
    start_time = time.perf_counter()
    run_result = run_basic_backtest()
    elapsed_seconds = time.perf_counter() - start_time
    logger.info(f"总耗时 {elapsed_seconds:.4f}秒")
    print(format_result_for_ai(run_result, elapsed_seconds))
