# 基准测试方法论 (Benchmark Methodology)

本文档详细说明了 `pyo3-quant` 与 `VectorBT` 性能对比测试的计时范围和一致性保证。

## 1. 计时范围 (Timing Scope)

我们的基准测试旨在衡量**核心回测引擎**的计算性能。因此，计时器的启动和停止点经过精心设计，以确保涵盖完整的计算链路，同时排除无关的 I/O 操作。

### 包含的环节 (Included)

*   **参数采样 (Parameter Sampling)**:
    *   **pyo3-quant**: 包含在 `bt.optimize()` 内部，由 Rust 侧的高性能随机数生成器处理。
    *   **VectorBT**: 包含在 Python 侧使用 `np.random` 生成大量随机参数组合的时间。
*   **指标计算 (Indicator Calculation)**:
    *   **pyo3-quant**: 包含 Rust 实现的指标计算（如 SMA, EMA, RSI）。
    *   **VectorBT**: 包含 `vbt.MA.run` / `vbt.RSI.run` 的执行时间（涉及 NumPy 广播或 Numba JIT 循环）。
*   **信号生成 (Signal Generation)**:
    *   **pyo3-quant**: 包含 Rust 侧的信号逻辑判定（LogicOp）。
    *   **VectorBT**: 包含 Python 侧的 NumPy 布尔矩阵运算。
*   **资金模拟 (Portfolio Simulation)**:
    *   **pyo3-quant**: 包含逐 K 线（Event-driven）的资金并在 Rust 中更新状态。
    *   **VectorBT**: 包含 `vbt.Portfolio.from_signals` 的向量化回测模拟。
    *   **关键点**: 所有测试均开启了 **移动止损 (TSL)**。这是因为 VectorBT 在处理简单的固定止盈止损时可能使用纯向量化 NumPy 路径，**只有开启 TSL/TP/SL 等复杂逻辑时，才会强制触发 Numba 编译的逐行仿真内核**。开启 TSL 确保了我们是在对比双方的**回测引擎核心仿真能力**，而不仅仅是矩阵运算。
*   **指标统计 (Metric Calculation)**:
    *   **pyo3-quant**: 包含计算 Calmar Ratio 等目标指标。
    *   **VectorBT**: 包含访问 `pf.total_return()` 触发计算。

### 排除的环节 (Excluded)

*   **数据生成 (Data Generation)**:
    *   测试开始前，使用 `data_utils.py` 预先生成统一的 OHLCV 数据（分别转换为 Polars 和 Pandas 格式）。
    *   **理由**: 纯粹的数据 I/O 或生成通常取决于硬盘/内存速度，不属于回测引擎的核心算法性能。
*   **数据加载 (Data Loading)**:
    *   将 DataFrame 传递给引擎的时间不计入（或占比极小）。
*   **结果打印/日志 (Logging)**:
    *   计时器仅包裹计算函数，不包含 `print` 或 `logger` 输出。

## 2. 一致性保证 (Consistency)

为了确保公平对比，我们在两个引擎中尽量保持了逻辑和工作负载的一致性：

| 维度 | pyo3-quant | VectorBT | 说明 |
|------|------------|----------|------|
| **数据源** | Polars DataFrame | Pandas DataFrame | 源数据由同一随机种子生成，数值完全一致。 |
| **对标策略** | SMA / EMA+RSI / **No-Ind** | SMA / EMA+RSI / **No-Ind** | 新增 **Strategy C (No-Indicator)** 以排除指标计算差异，纯粹对比回测引擎核心性能。 |
| **优化方式** | 权重驱动自适应 (Adaptive) | 随机搜索 (Random Search) | VectorBT 利用随机搜索的固定参数进行了指标预计算优化；pyo3-quant 模拟真实自适应场景，不做全局预计算。 |
| **Numba JIT** | 不适用 (原生 Rust) | 启用 (针对复杂指标) | VectorBT 在计算 EMA/RSI 时启用了 Numba 以获得最佳性能。 |
| **预热 (Warmup)** | 有 | 有 | 在正式计时前均运行一次小规模测试。对 VectorBT 是为了触发 Numba JIT 编译；对 pyo3-quant 是为了初始化 Rayon 线程池和内存分配器，确保公平。 |

### 2.1 关于 Strategy C (无指标) 的重要性

我们特意引入了 **Strategy C (无指标策略)**，即仅基于价格比较（`close > close[-1]`）进行买卖。

*   **目的**: 剥离指标计算（TA-Lib/Pandas vs Rust）的影响，**直接对比回测引擎核心 Loop 的性能**。
*   **公平性**: 在此场景下，双方都没有复杂的指标计算负担，VectorBT 也无法使用“指标预计算”优化。这是衡量 Rust 引擎底座与 Numba JIT 引擎底座性能差异的最公平基准。

## 3. 为什么这样设计？

用户通常关心的不是“回测框架初始化的 1 毫秒”，而是当需要跑 **2000 次参数优化** 或处理 **百万行 K 线** 时，引擎还需要多久才能给出结果。因此，我们将**参数生成 + 指标 + 信号 + 回测** 作为一个整体进行黑盒计时，这最能反映真实的高频迭代场景。
