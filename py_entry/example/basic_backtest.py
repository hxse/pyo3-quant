import path_tool
import time
from py_entry.data_conversion.backtest_runner import BacktestRunner
import pyo3_quant
from loguru import logger

if __name__ == "__main__":
    print("-" * 30)
    start_time = time.perf_counter()
    res = pyo3_quant.minimal_working_example.sum_as_string(5, 25)
    print("sum_as_string:", res)
    print("耗时", time.perf_counter() - start_time)

    print("-" * 30)
    start_time = time.perf_counter()
    br = BacktestRunner()
    backtest_result = (
        br.with_data(
            {
                "timeframes": ["15m", "1h"],
                "start_time": 1735689600000,
                "num_bars": 200,
            },
        )
        .with_param_set()
        .with_templates()
        .with_engine_settings()
        .run()
    )

    print(backtest_result)

    logger.info(f"performance: {backtest_result[0].performance}")

    logger.info(f"耗时 {time.perf_counter() - start_time}")
