# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## 通用规则

- **混合项目架构**: 这是一个 Rust + Python (PyO3) 混合项目。Rust 模块 `pyo3_quant` 通过 `maturin` 直接导入到 Python 中。
- **构建与依赖**:
    - Python 的 `pandas-ta` 依赖直接从 Git 仓库的 `development` 分支安装。
    - `ta-lib` 的安装方式因操作系统而异 (Windows 使用 `.whl` 文件,其他系统使用 PyPI)。
- **并行计算**: Rust 回测引擎 (`src/backtest_engine/mod.rs`) 在多任务并行回测时,使用 `rayon` 进行任务并行,并通过 `utils::process_param_in_single_thread` 强制 `Polars` 在每个任务中以单线程模式运行,以避免 `rayon` 和 `Polars` 内部并行之间的冲突。
- **回测核心逻辑**: `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数目前仅为占位实现,返回一个空的 `DataFrame`,实际回测逻辑待实现。
- **指标计算细节**: Rust 指标计算 (`src/backtest_engine/indicators/calculator.rs`) 支持 SMA 和布林带。布林带的标准差计算 (`src/backtest_engine/indicators/bbands.rs`) 明确使用 `ddof=0`。
- **Python 回测配置**: Python 端的回测流程由 `py_entry/data_conversion/backtest_runner/BacktestRunner` 驱动,采用 Builder 模式进行配置。定制回测逻辑需要继承 `DefaultParamBuilder`、`DefaultSignalTemplateBuilder` 和 `DefaultEngineSettingsBuilder` 等类。
- **参数定义**: `py_entry/data_conversion/helpers/create_param` 是一个关键的辅助函数,用于定义回测参数。
- **内存优化**: `src/backtest_engine/utils/memory_optimizer.rs` 中的 `optimize_memory_by_stage` 函数用于根据执行阶段优化返回结果的内存占用。
- **指标测试容差**: 指标测试 (`py_entry/Test/indicators/`) 使用 `pytest` 和通用模板。布林带的 `_percent` 列在测试中具有较低的精度要求 (`custom_rtol: 1e-3, custom_atol: 1e-6`),表明其计算结果可能存在细微差异。
- **源代码参考目录 (`source_ref`)**:
    - `source_ref` 目录包含多个第三方库的源代码参考,包括但不限于:
      - Polars
      - pandas-ta
      - talib
      - 其他依赖库
    - 此目录**仅用于分析和理解这些库的 API 使用方法**。
    - **严禁在项目代码中直接引用或导入** `source_ref` 目录中的任何内容。
    - 当遇到相关库的编译错误或 API 使用问题时,可以参考此目录中的源代码来理解正确的使用方式。
    - 最终代码必须使用项目依赖中的官方模块,而不是 `source_ref` 中的源代码。
    - **注意**: 如果在 RooCode 中检测不到 `source_ref` 目录,可能是 `.gitignore` 中启用了忽略。可以与用户讨论是否需要临时取消注释 `.gitignore` 中的 `source_ref/` 行以便访问源代码进行分析。

## 架构规则

- **混合架构设计**: 在设计新功能或修改现有功能时,请始终考虑 Rust 和 Python 之间的职责划分。Rust 负责高性能计算和数据处理,Python 负责业务逻辑编排、参数配置和结果分析。
- **数据流设计**: 在 Rust 和 Python 之间传递数据时,优先使用 `pyo3-polars` 提供的机制,以确保高效且类型安全的数据交换。
- **并行策略**: 架构设计应充分利用 Rust 的 `rayon` 库进行任务并行,但要特别注意 `Polars` 在多线程环境下的行为,并通过 `utils::process_param_in_single_thread` 确保兼容性。
- **回测引擎扩展**: 扩展回测引擎时,请注意 `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数是核心扩展点。
- **可配置性**: Python 端的回测配置应通过继承 `py_entry/data_conversion/backtest_runner/` 下的 Builder 类来实现,以保持高度的可配置性和灵活性。
- **指标扩展**: 在 Rust 中添加新指标时,请遵循 `src/backtest_engine/indicators/calculator.rs` 中现有 SMA 和布林带的模式,确保一致性和可维护性。
- **内存管理**: 架构设计应考虑内存优化,特别是 `src/backtest_engine/utils/memory_optimizer.rs` 中的 `optimize_memory_by_stage` 函数,以根据执行阶段控制返回结果的内存占用。

## 提问规则

- **文档上下文**: 提问时,请明确指出是关于 Rust 部分 (例如,Polars 数据处理、PyO3 绑定) 还是 Python 部分 (例如,回测配置、pandas-ta 集成)。
- **性能相关问题**: 如果问题与性能相关,请提及并行计算 (`rayon` 和 `Polars` 单线程模式) 的上下文。

## 编码规则

- **Rust-Python 交互**: 在 Rust 和 Python 之间传递数据时,请注意 `pyo3-polars` 的使用,确保数据类型和结构兼容。
- **Polars 并行**: 在 Rust 中进行多任务并行计算时,如果使用 `rayon` 和 `Polars`,请务必通过 `utils::process_param_in_single_thread` 强制 `Polars` 在单线程模式下运行,以避免冲突。
- **回测逻辑实现**: `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数目前是占位符,需要在此处实现实际的回测逻辑。
- **Python 回测定制**: 编写 Python 回测逻辑时,通过继承 `py_entry/data_conversion/backtest_runner/` 下的 Builder 类来定制参数、信号和引擎设置。
- **参数定义**: 使用 `py_entry/data_conversion/helpers/create_param` 辅助函数来定义回测参数。
- **指标计算**: 在 Rust 中添加新指标时,请遵循 `src/backtest_engine/indicators/calculator.rs` 中现有 SMA 和布林带的模式。**为确保指标测试通过,实现时必须严格遵循pandas-ta的逻辑细节**:
  - **验证标准优先级**:
    - 一般以 `pandas-ta` 作为对比标准。
    - 当 `pandas-ta` 开启 `talib` 时,如果两者结果不一致,以 `talib` 为优先标准。
    - 如果 `pandas-ta` 没有该指标或无法获取源代码,需与用户讨论验证方式和实现方式。
  - **测试配置说明**:
    - `enable_talib`: 控制 `pandas-ta` 是否使用 `talib` 实现。
    - `assert_mode_talib`: 是否验证与 `talib` 的一致性。
    - `assert_mode_pandas_ta`: 是否验证与 `pandas-ta` 的一致性。
    - 当 `talib` 和 `pandas-ta` 结果冲突时,设置 `assert_mode_talib=True, assert_mode_pandas_ta=False`,以 `talib` 为准。
    - 当 `talib` 和 `pandas-ta` 结果一致时,设置 `assert_mode_talib=True, assert_mode_pandas_ta=True`。
    - `talib` 是 `pandas-ta` 内的一个选项,无需单独使用,但需要用户安装 `ta-lib`。
  - **前导NaN数量**: 确保结果序列前导NaN的数量与pandas-ta完全一致。例如,EMA的前`period-1`个值应为NaN。
  - **初始值计算**: 某些指标(如EMA)需要特定的初始值。EMA使用前`period`个值的SMA作为初始EMA值(第`period`个位置,索引`period-1`)。
  - **计算逻辑细节**: 严格复现pandas-ta的计算公式和参数。例如,EMA使用`alpha = 2 / (span + 1)`而不是其他变体。
  - **参考源码**: 实现前务必查看pandas-ta的源代码,理解其`presma`、`adjust`等参数的影响,以及特殊情况的处理逻辑。**如果无法获取pandas-ta的源代码,请与用户讨论验证方式。**
  - **测试验证**: 使用`py_entry/Test/indicators/`中的测试模板验证实现,确保与pandas-ta(talib模式和pandas_ta模式)的结果一致。

## 调试规则

- **Rust-Python 交互调试**: 调试 Rust 和 Python 之间的交互时,重点关注 `pyo3` 和 `pyo3-polars` 的数据类型转换和错误处理。
- **并行冲突调试**: 如果在多任务并行回测中遇到意外行为或崩溃,请检查 `src/backtest_engine/mod.rs` 中 `rayon` 和 `Polars` 的单线程限制 (`utils::process_param_in_single_thread`) 是否正确应用。
- **回测逻辑调试**: `src/backtest_engine/backtester.rs` 中的 `run_backtest` 函数目前是占位符。调试回测结果时,请注意此函数的当前状态,并确保实际逻辑实现后进行彻底测试。
- **指标精度调试**: 调试指标计算结果时,特别是布林带的 `_percent` 列,请记住 `py_entry/Test/indicators/test_bbands.py` 中定义的较低精度容差 (`custom_rtol: 1e-3, custom_atol: 1e-6`)。
- **内存优化调试**: 调试内存使用问题时,请检查 `src/backtest_engine/utils/memory_optimizer.rs` 中的 `optimize_memory_by_stage` 函数是否按预期工作,以根据执行阶段优化返回结果。

# None和NaN处理
## None 和 NaN 在 Polars 中的区别
  * 在 Polars 中：
  * None 表示数据的缺失值，是一个逻辑概念，不占用实际的存储空间
  * NaN (Not a Number) 是一个特殊的浮点数值，表示无效的数值计算结果
  * 计算指标的过程中, 尽量用None, 避免NaN传播, 影响计算逻辑, 计算结尾的时候把None统一转换成NaN
  * 我已经定义好了None和NaN处理工具函数, 在计算指标的过程中直接使用`src/backtest_engine/indicators/utils.rs`
  * 优先在lazy计算函数结尾处把None转换为NaN, 然后eager计算函数直接调用lazy计算函数就行了, 不用再转换了
  * 内部计算优先用None, 最后输出时转换成NaN

# 搜索源代码
  * 可以尝试利用搜索工具搜索 `source_ref/polars/crates/polars-core/src/`
  * 或者 `source_ref/ta-lib`
  * 或者 `source_ref/pandas-ta`

# 关于polars clone成本的调查
源代码路径 `source_ref/polars/crates/polars-core/src/frame/column/mod.rs`
## Polars DataFrame 和 Series 的内部实现分析

### 1. DataFrame 结构（第172-176行）
```rust
#[derive(Clone)]
pub struct DataFrame {
    height: usize,
    pub(crate) columns: Vec<Column>,
    cached_schema: OnceLock<SchemaRef>,
}
```

### 2. Series 结构（第153行）
```rust
#[derive(Clone)]
pub struct Series(pub Arc<dyn SeriesTrait>);
```

### 3. Column 结构（第43-47行）
```rust
#[derive(Debug, Clone)]
pub enum Column {
    Series(SeriesColumn),
    Partitioned(PartitionedColumn),
    Scalar(ScalarColumn),
}
```

### 4. 关键发现：Arc 的使用

从这些源码可以确认：

1. **DataFrame 使用 `Vec<Column>`** - 这是普通向量，不是 Arc
2. **Series 使用 `Arc<dyn SeriesTrait>`** - 这是智能指针，支持浅拷贝
3. **Column 使用 `#[derive(Clone)]`** - 但主要是枚举的 clone

## 性能影响分析

### DataFrame 的 Clone 成本
- `Vec<Column>` 的 clone：需要复制整个向量
- 每个 `Column` 的 clone：根据枚举变体决定
  - `Series(SeriesColumn)`：会调用 `Series::clone()`（Arc clone，浅拷贝）
  - `Partitioned` 和 `Scalar`：通常是简单的值拷贝

### Series 的 Clone 成本
- `Arc<dyn SeriesTrait>` 的 clone：**只是增加引用计数**，O(1) 操作
