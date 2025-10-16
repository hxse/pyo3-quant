# AGENTS.md

This file provides guidance to agents when working with code in this repository.

- **Rust-Python 交互**: 在 Rust 和 Python 之间传递数据时,请注意 `pyo3-polars` 的使用,确保数据类型和结构兼容。
- **Polars 并行**: 在 Rust 中进行多任务并行计算时,如果使用 `rayon` 和 `Polars`,请务必通过 `utils::process_param_in_single_thread` 强制 `Polars` 在单线程模式下运行,以避免冲突。
- **回测逻辑实现**: `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数目前是占位符,需要在此处实现实际的回测逻辑。
- **Python 回测定制**: 编写 Python 回测逻辑时,通过继承 `py_entry/data_conversion/backtest_runner/` 下的 Builder 类来定制参数、信号、风险和引擎设置。
- **参数定义**: 使用 `py_entry/data_conversion/helpers/create_param` 辅助函数来定义回测参数。
- **指标计算**: 在 Rust 中添加新指标时,请遵循 `src/backtest_engine/indicators/calculator.rs` 中现有 SMA 和布林带的模式。
