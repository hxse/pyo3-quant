# AGENTS.md

This file provides guidance to agents when working with code in this repository.

- **Rust-Python 交互调试**: 调试 Rust 和 Python 之间的交互时,重点关注 `pyo3` 和 `pyo3-polars` 的数据类型转换和错误处理。
- **并行冲突调试**: 如果在多任务并行回测中遇到意外行为或崩溃,请检查 `src/backtest_engine/mod.rs` 中 `rayon` 和 `Polars` 的单线程限制 (`utils::process_param_in_single_thread`) 是否正确应用。
- **回测逻辑调试**: `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数目前是占位符。调试回测结果时,请注意此函数的当前状态,并确保实际逻辑实现后进行彻底测试。
- **指标精度调试**: 调试指标计算结果时,特别是布林带的 `_percent` 列,请记住 `py_entry/Test/indicators/test_bbands.py` 中定义的较低精度容差 (`custom_rtol: 1e-3, custom_atol: 1e-6`)。
- **内存优化调试**: 调试内存使用问题时,请检查 `src/backtest_engine/utils/memory_optimizer.rs` 中的 `optimize_memory_by_stage` 函数是否按预期工作,以根据执行阶段优化返回结果。
