# 项目结构说明文档

相关项目连接:
- <https://github.com/hxse/pyo3-quant>
- <https://github.com/hxse/ccxt-proxy2>
- <https://github.com/hxse/lwchart_demo3>

本文档详细展示了 `pyo3-quant` 项目的文件结构与功能说明。本项目是一个混合 Rust/Python 的高性能量化回测与交易系统。


## 1. 目录结构全览

以下包含项目的主要源代码文件，已排除编译产物（如 `target`, `__pycache__` 等）。

```text
pyo3-quant/
├── bin/                            # 辅助工具脚本
├── doc/                            # 项目文档
├── justfile                        # 任务管理入口 (build, test, run)
├── pyo3_quant.pyi                  # Rust 扩展模块的 Python 接口定义 (Type Stubs)
├── Cargo.toml                      # Rust 依赖配置
├── pyproject.toml                  # Python 依赖配置
├── scripts/                        # 环境配置脚本
│   └── setup_dev_env.sh            # 开发环境初始化
│
├── src/                            # [Rust] 核心计算引擎源码
│   ├── lib.rs                      # PyO3 模块入口，注册 Python 接口
│   ├── error/                      # 错误处理模块
│   │   ├── mod.rs
│   │   └── py_interface.rs         # 将 Rust 错误映射为 Python 异常
│   ├── types/                      # 通用类型定义 (DataContainer, ParamContainer 等)
│   └── backtest_engine/            # 回测引擎核心
│       ├── mod.rs                  # 引擎入口，调度并行任务
│       ├── backtester/             # 回测模拟器
│       │   ├── mod.rs
│       │   ├── main_loop.rs        # 回测主循环逻辑
│       │   ├── data_preparer.rs    # 数据切片与准备
│       │   ├── signal_preprocessor.rs # 信号预处理
│       │   ├── atr_calculator.rs   # 动态 ATR 计算
│       │   └── buffer_slices.rs    # 内存复用缓冲区
│       ├── indicators/             # 技术指标实现 (基于 Polars)
│       │   ├── mod.rs              # 指标计算入口
│       │   ├── adx.rs              # Average Directional Index
│       │   ├── atr.rs              # Average True Range
│       │   ├── bbands.rs           # Bollinger Bands
│       │   ├── ema.rs              # Exponential Moving Average
│       │   ├── macd.rs             # MACD
│       │   ├── rsi.rs              # Relative Strength Index
│       │   ├── sma.rs              # Simple Moving Average
│       │   └── ...                 # 其他指标
│       ├── signal_generator/       # 信号生成器
│       │   ├── mod.rs              # 信号生成入口
│       │   ├── parser.rs           # 信号表达式解析 DSL
│       │   ├── condition_evaluator.rs # 条件逻辑求值
│       │   └── operand_resolver.rs # 操作数解析
│       ├── performance_analyzer/   # 绩效分析
│       │   ├── mod.rs
│       │   ├── metrics.rs          # 核心指标计算 (Sharpe, Drawdown)
│       │   └── stats.rs            # 统计辅助工具
│       ├── optimizer/              # 参数优化器
│       │   └── mod.rs
│       └── walk_forward/           # 向前滚动分析
│           └── mod.rs
│
└── py_entry/                       # [Python] 业务逻辑与应用层
    ├── types/                      # Python 端类型定义
    ├── example/                    # 示例代码
    │   ├── basic_backtest.py       # 基础回测示例
    │   └── custom_backtest.py      # 自定义数据回测示例
    ├── trading_bot/                # 实盘交易机器人
    │   ├── bot.py                  # 机器人主程序 (State Machine)
    │   ├── order_executor.py       # 订单执行器 (Entry/Exit/Risk)
    │   ├── callbacks.py            # 交易所交互接口定义
    │   ├── config.py               # 机器人配置
    │   ├── signal_processor.py     # 实时信号处理
    │   └── state/                  # 状态持久化
    │       ├── manager.py          # 状态管理
    │       └── models.py           # 状态数据模型
    ├── runner/                     # 回测运行器
    │   ├── backtest.py             # Backtest 类 (统一入口)
    │   ├── setup_utils.py          # 参数组装工具
    │   ├── optuna_optimizer.py     # Optuna 优化集成
    │   └── results/                # 结果对象封装
    ├── data_generator/             # 数据加载与生成
    │   ├── data_generator.py       # 数据加载主类
    │   ├── ohlcv_generator.py      # K 线数据处理
    │   ├── heikin_ashi_generator.py # HA K 线生成
    │   └── renko_generator.py      # Renko 图生成
    ├── charts/                     # 图表绘制
    │   ├── generation.py           # 图表生成主逻辑 (Highcharts/Echarts)
    │   └── settings.py             # 图表配置
    └── Test/                       # 单元测试与集成测试
        ├── backtest/               # 回测逻辑测试
        │   ├── strategies/         # 具体策略测试
        │   └── ...
        ├── trading_bot/            # 实盘机器人测试 (状态, 订单, 反手)
        ├── signal/                 # 信号生成测试
        ├── optimizer_benchmark/    # 优化器基准测试
        └── indicators/             # 技术指标校对测试
```

## 2. 核心模块详解

### 2.1 Rust 层 (`src/`)

Rust 层负责计算密集型任务，通过 PyO3 暴露给 Python。

*   **`src/lib.rs`**:
    *   **作用**: 定义 Python 模块 `pyo3_quant`。
    *   **重点函数**: `register_py_module` 负责将所有子模块（引擎、错误、优化器）注册到 Python 环境中。

*   **`src/backtest_engine/mod.rs`**:
    *   **作用**: 回测引擎的总调度器。
    *   **重点函数**:
        *   `run_backtest_engine`: 处理批量请求，使用 `rayon` 实现多参数集的并行计算。
        *   `execute_single_backtest`: 执行单个回测任务，按序调度指标计算、信号生成、模拟回测和绩效分析四个阶段，并负责阶段间的内存回收。

*   **`src/backtest_engine/backtester/main_loop.rs`**:
    *   **作用**: 模拟交易的主循环。
    *   **逻辑**: 遍历时间序列，维护当前持仓状态、资金余额，处理开平仓逻辑、止损止盈（ATR/百分比）以及对冲逻辑。

*   **`src/backtest_engine/indicators/*.rs`**:
    *   **作用**: 各类技术指标的高性能实现。
    *   **特点**: 主要基于 `polars` 的表达式引擎或急切执行模式 (Eager Execution) 实现向量化计算，避免 Python 循环。

*   **`src/backtest_engine/signal_generator/parser.rs`**:
    *   **作用**: 解析基于字符串的信号逻辑模板（DSL）。
    *   **功能**: 将如 `"rsi_14 > 70 & close < bb_upper"` 这样的字符串解析为可执行的逻辑树。

### 2.2 Python 层 (`py_entry/`)

Python 层负责策略配置、数据管理、实盘逻辑和结果分析。

*   **`py_entry/runner/backtest.py`**:
    *   **作用**: 用户进行回测研究的核心入口类 `Backtest`。
    *   **重点函数**:
        *   `__init__`: 构建数据容器、参数集合和引擎设置。
        *   `run()`: 运行单次回测。
        *   `batch()`: 运行批量参数回测（并发）。
        *   `optimize()`: 调用 Rust 优化器或 Optuna 进行超参数搜索。

*   **`py_entry/trading_bot/bot.py`**:
    *   **作用**: 实盘交易机器人的核心。
    *   **逻辑**:
        *   采用**无状态/弱状态设计**，每次启动或新周期开始时，通过 `_try_init_and_verify` 校验本地状态与交易所实际持仓的一致性。
        *   `run_single_step`: 每个 K 线周期执行一次，完成“获取数据 -> 回测计算信号 -> 比较当前状态 -> 执行交易”的闭环。

*   **`py_entry/trading_bot/order_executor.py`**:
    *   **作用**: 负责将交易信号转化为具体的交易所订单请求。
    *   **重点函数**:
        *   `execute_entry`: 计算仓位大小，发送开仓单，并挂载相关联的止盈止损条件单。
        *   `execute_reversal`: 处理反手逻辑（先平掉相反方向的持仓，再开新仓）。
        *   `check_and_cancel_orphan_orders`: 保护机制，确保没有非预期的挂单残留。

*   **`py_entry/data_generator/data_generator.py`**:
    *   **作用**: 统一的数据加载接口。
    *   **功能**: 支持从 CSV、Parquet 等多种格式加载数据，并支持自动转换为 Heikin Ashi 或 Renko 等特殊格式。

### 2.3 测试模块 (`py_entry/Test/`)

项目包含全面的测试套件，涵盖了从数据验证到策略逻辑再到实盘模拟的各个环节。

*   **`backtest/` (回测逻辑测试)**:
    *   **`strategies/`**: 针对具体策略（如 Reversal, Reversal Extreme, Trend Following 等）的专项测试，确保不同市场条件下的开平仓逻辑符合预期。
    *   **`common_tests/`**: 通用回测功能测试。
    *   **`precision_tests/`**: 验证数据精度和计算准确性。
    *   **`correlation_analysis/`**: 策略相关性分析测试。

*   **`trading_bot/` (实盘机器人测试)**:
    *   **`test_state.py`**: 验证 `StateManager` 的状态持久化与恢复逻辑，确保机器人重启后能正确接管。
    *   **`test_entry_exit.py`**: 验证开仓和平仓的订单执行逻辑。
    *   **`test_reversal.py`**: 重点测试反手交易（Reverse Position）的原子性和正确性。
    *   **`test_conditional_orders.py`**: 验证止盈止损条件单的挂单、撤单和触发逻辑。
    *   **`test_capital_ratio.py`**: 验证多策略资金分配比例的正确性。

*   **`signal/` (信号生成测试)**:
    *   **`test_signal_generation.py`**: 验证 DSL 信号解析和生成的正确性。
    *   **`scenarios/`**: 包含大量具体的信号场景测试用例。

*   **`optimizer_benchmark/` (优化器基准测试)**:
    *   **`benchmark_*.py`**: 用于测试参数优化算法（如遗传算法、贝叶斯优化）的收敛速度和性能。
    *   **`test_layer2_financial.py`**: 针对真实金融数据的优化效果测试。

*   **`indicators/`**: 验证 Rust 核心计算出的技术指标数值与 Python TA-Lib 或 Pandas 实现的一致性。


*   **`pyo3_quant.pyi`**:
    *   **作用**: 极其重要的类型提示文件。它告诉 Python IDE (VS Code, PyCharm) Rust 编译出来的二进制模块里有哪些函数、参数类型是什么，是开发体验的关键。

## 3. 重要文件快速索引

*   **入口**: `py_entry/runner/backtest.py` (回测), `py_entry/trading_bot/bot.py` (实盘)
*   **核心逻辑**: `src/backtest_engine/mod.rs` (调度), `src/backtest_engine/backtester/main_loop.rs` (撮合)
*   **接口定义**: `pyo3_quant.pyi` (Rust -> Python)
*   **任务脚本**: `justfile` (常用命令)
