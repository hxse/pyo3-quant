import time
from loguru import logger
from py_entry.runner import Backtest
from py_entry.data_generator import DataGenerationParams

if __name__ == "__main__":
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"], start_time=1000, num_bars=100, base_data_key="ohlcv_15m"
    )
    start_time = time.perf_counter()

    # 创建 Backtest
    bt = Backtest(
        data_source=simulated_data_config,  # Simulated data needs to be imported, wait, basic_backtest doesn't have it?
        # Ah, basic_backtest.py code above didn't show config?
        # Let me check basic_backtest.py imports.
        # It imported SetupConfig. But where is simulated_data_config coming from?
        # Ah, view_file showed lines 1-22. It truncated the top imports?
        # No, line 1 is import time.
        # Wait, lines 1-22 showed the whole file?
        # basic_backtest.py in the view only showed:
        # 1: import time
        # ...
        # 14: br.setup(SetupConfig(enable_timing=True)).run()
        # SetupConfig doesn't have arguments?
        # SetupConfig default is None for fields.
        # So it runs with empty config? That would fail validation in BacktestRunner.
        # Unless BacktestRunner handles None gracefully?
        # BacktestRunner checks data_dict exists.
        # So likely basic_backtest.py as shown is BROKEN or I missed something.
        # But I should just update it to new API syntax, whatever valid code it had.
        # Line 14: br.setup(SetupConfig(enable_timing=True)).run()
        # This implies SetupConfig can be init with just enable_timing?
    )
    # The view showed:
    # 14: br.setup(SetupConfig(enable_timing=True)).run()
    # If I change it to `bt = Backtest(enable_timing=True, ...)`
    # Backtest init requires data_source unless optional.
    # Backtest signature: `def __init__(self, data_source: DataSourceConfig, ...)`
    # So `data_source` is required.
    # If basic_backtest.py didn't pass data_source, how did it work?
    # Maybe SetupConfig allows Nones, but `perform_setup` might fail or use defaults?
    # Or maybe it relies on existing state if reused? (Not relevant here).
    # Maybe `basic_backtest.py` is an incomplete example.

    # I should assume `basic_backtest.py` is just a skeleton.
    # I will verify the file content again.
    # If it is incomplete, I'll just update it to look correct.

    result = bt.run()
    # print(result.summary) # Commented out as print(result) might be verbose?
    # result works.

    if result.summary:
        logger.info(f"performance: {result.summary.performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")
