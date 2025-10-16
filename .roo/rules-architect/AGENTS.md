# AGENTS.md

This file provides guidance to agents when working with code in this repository.

- **混合架构设计**: 在设计新功能或修改现有功能时,请始终考虑 Rust 和 Python 之间的职责划分。Rust 负责高性能计算和数据处理,Python 负责业务逻辑编排、参数配置和结果分析。
- **数据流设计**: 在 Rust 和 Python 之间传递数据时,优先使用 `pyo3-polars` 提供的机制,以确保高效且类型安全的数据交换。
- **并行策略**: 架构设计应充分利用 Rust 的 `rayon` 库进行任务并行,但要特别注意 `Polars` 在多线程环境下的行为,并通过 `utils::process_param_in_single_thread` 确保兼容性。
- **回测引擎扩展**: 扩展回测引擎时,请注意 `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数是核心扩展点。
- **可配置性**: Python 端的回测配置应通过继承 `py_entry/data_conversion/backtest_runner/` 下的 Builder 类来实现,以保持高度的可配置性和灵活性。
- **指标扩展**: 在 Rust 中添加新指标时,请遵循 `src/backtest_engine/indicators/calculator.rs` 中现有 SMA 和布林带的模式,确保一致性和可维护性。
- **内存管理**: 架构设计应考虑内存优化,特别是 `src/backtest_engine/utils/memory_optimizer.rs` 中的 `optimize_memory_by_stage` 函数,以根据执行阶段控制返回结果的内存占用。
