import pyo3_quant
from loguru import logger

from py_entry.data_generator import DataGenerationParams
from py_entry.runner import Backtest
from py_entry.types import Param


def run_exception_handling_demo() -> tuple[bool, str]:
    """运行异常处理示例，返回是否按预期捕获异常。"""
    logger.info("开始执行异常处理示例")

    # 自包含示例：只提供 15m/1h 数据。
    simulated_data_config = DataGenerationParams(
        timeframes=["15m", "1h"],
        start_time=1735689600000,
        num_bars=1000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )

    # 故意制造错误：指标引用了 ohlcv_4h，但数据源没有 4h。
    indicators_params = {
        "ohlcv_15m": {
            "sma_fast": {"period": Param(8)},
            "sma_slow": {"period": Param(21)},
        },
        "ohlcv_4h": {
            "rsi": {"period": Param(14)},
        },
    }

    try:
        Backtest(
            enable_timing=False,
            data_source=simulated_data_config,
            indicators=indicators_params,
        ).run()
    except pyo3_quant.errors.PyDataSourceNotFoundError as error:
        return True, str(error)
    return False, "未触发预期异常"


def format_result_for_ai(success: bool, message: str) -> str:
    """输出给 AI 读取的结构化摘要。"""
    lines: list[str] = []
    lines.append("=== EXCEPTION_HANDLING_DEMO_RESULT ===")
    lines.append(f"expected_exception_caught={success}")
    lines.append(f"message={message}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑用于 AI 调试与结果读取。
    is_success, result_message = run_exception_handling_demo()
    print(format_result_for_ai(is_success, result_message))
