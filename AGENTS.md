# AGENTS.md

This file provides guidance to agents when working with code in this repository.

- **混合项目架构**: 这是一个 Rust + Python (PyO3) 混合项目。Rust 模块 `pyo3_quant` 通过 `maturin` 直接导入到 Python 中。
- **构建与依赖**:
    - Python 的 `pandas-ta` 依赖直接从 Git 仓库的 `development` 分支安装。
    - `ta-lib` 的安装方式因操作系统而异 (Windows 使用 `.whl` 文件,其他系统使用 PyPI)。
- **并行计算**: Rust 回测引擎 (`src/backtest_engine/mod.rs`) 在多任务并行回测时,使用 `rayon` 进行任务并行,并通过 `utils::process_param_in_single_thread` 强制 `Polars` 在每个任务中以单线程模式运行,以避免 `rayon` 和 `Polars` 内部并行之间的冲突。
- **回测核心逻辑**: `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数目前仅为占位实现,返回一个空的 `DataFrame`,实际回测逻辑待实现。
- **指标计算细节**: Rust 指标计算 (`src/backtest_engine/indicators/calculator.rs`) 支持 SMA 和布林带。布林带的标准差计算 (`src/backtest_engine/indicators/bbands.rs`) 明确使用 `ddof=0`。
- **Python 回测配置**: Python 端的回测流程由 `py_entry/data_conversion/backtest_runner/BacktestRunner` 驱动,采用 Builder 模式进行配置。定制回测逻辑需要继承 `DefaultParamBuilder`、`DefaultSignalTemplateBuilder`、`DefaultRiskTemplateBuilder` 和 `DefaultEngineSettingsBuilder` 等类。
- **参数定义**: `py_entry/data_conversion/helpers/create_param` 是一个关键的辅助函数,用于定义回测参数。
- **内存优化**: `src/backtest_engine/utils/memory_optimizer.rs` 中的 `optimize_memory_by_stage` 函数用于根据执行阶段优化返回结果的内存占用。
- **指标测试容差**: 指标测试 (`py_entry/Test/indicators/`) 使用 `pytest` 和通用模板。布林带的 `_percent` 列在测试中具有较低的精度要求 (`custom_rtol: 1e-3, custom_atol: 1e-6`),表明其计算结果可能存在细微差异。
