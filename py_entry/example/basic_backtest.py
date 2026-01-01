import time
from loguru import logger
from py_entry.runner import BacktestRunner

if __name__ == "__main__":
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
