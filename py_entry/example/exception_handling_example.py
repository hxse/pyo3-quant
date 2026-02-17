import pyo3_quant
from loguru import logger

from py_entry.data_generator import DataGenerationParams
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.runner import Backtest
from py_entry.types import Param


# 创建 DataGenerationParams 对象
simulated_data_config = DataGenerationParams(
    timeframes=["15m", "1h"],
    start_time=get_utc_timestamp_ms("2025-01-01 00:00:00"),
    num_bars=10000,
    fixed_seed=42,
    base_data_key="ohlcv_15m",
)

# 构建指标参数
indicators_params = {
    "ohlcv_15m": {
        "sma_0": {"period": Param(14, min=5, max=50, step=1)},
        "sma_1": {
            "period": Param(200, min=100, max=300, step=10),
        },
    },
    "ohlcv_4h": {  # 数据没有4h, 预期报错
        "sma_0": {"period": Param(14, min=5, max=50, step=1)},
    },
}


def run_exception_handling_demo() -> tuple[bool, str]:
    """运行异常处理示例，返回是否按预期捕获异常。"""
    logger.info("开始执行异常处理示例")
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
