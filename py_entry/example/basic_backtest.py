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
import pyo3_quant
from loguru import logger
from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.helpers.data_generator import DataGenerationParams

if __name__ == "__main__":
    print("-" * 30)
    start_time = time.perf_counter()
    res = pyo3_quant.minimal_working_example.sum_as_string(5, 25)
    print("sum_as_string:", res)
    print("耗时", time.perf_counter() - start_time)

    print("-" * 30)
    start_time = time.perf_counter()
    br = BacktestRunner()

    # 创建 DataGenerationParams 对象
    simulated_data_config = DataGenerationParams(
        timeframes=["15m", "1h"],
        start_time=1735689600000,
        num_bars=200,
    )

    backtest_result = (
        br.with_data(simulated_data_config=simulated_data_config)
        .with_param_set()
        .with_templates()
        .with_engine_settings()
        .run()
    )

    print(backtest_result)

    logger.info(f"performance: {backtest_result[0].performance}")

    logger.info(f"耗时 {time.perf_counter() - start_time}")
