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

if __name__ == "__main__":
    start_time = time.perf_counter()
    res = pyo3_quant.minimal_working_example.sum_as_string(5, 25)
    print("sum_as_string:", res)
    print("耗时", time.perf_counter() - start_time)

    start_time = time.perf_counter()

    # 创建启用时间测量的 BacktestRunner
    br = BacktestRunner(enable_timing=True)

    # 使用链式调用配置和执行回测
    logger.info("开始执行基础回测")
    br.setup().run()

    print(br.results)

    if br.results:
        logger.info(f"performance: {br.results[0].performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")
