# WF 最小改动方案 - 架构与算法文档

## 1. 目标
本文件只描述实现结构、输入输出契约与执行顺序，不解释方案动机。

本任务的唯一实现口径：
1. 指标预热需求先由指标契约聚合得到。
2. WF 窗口先在 base 上生成，再按 source 独立映射。
3. WF 内部统一使用带 `ranges` 的专用容器。
4. 回测引擎与优化器只消费通用 `DataContainer/BacktestSummary` 载荷。
5. 对外返回仍保持通用容器类型。

---

## 2. 模块分层

### 2.1 Rust 侧
1. `src/backtest_engine/indicators/**/*.rs`
   - 指标实现
   - `required_warmup_bars(resolved_params) -> usize`
   - `warmup_mode() -> Strict | Relaxed`
2. `src/backtest_engine/indicators/registry.rs`
   - 注册指标契约聚合入口
3. `src/types/outputs/indicator_contract.rs`
   - 指标契约聚合输出类型
4. `src/types/inputs/walk_forward.rs`
   - `WalkForwardConfig`
   - `WfWarmupMode`
5. `src/backtest_engine/walk_forward/data_splitter.rs`
   - base 窗口生成
   - source 区间映射
6. `src/backtest_engine/walk_forward/runner.rs`
   - WF 执行主流程
   - 注入、窗口切片、stitched 拼接
7. `src/types/outputs/walk_forward.rs`
   - WF 输出类型
   - 窗口结果与 stitched 结果的外部返回契约

### 2.2 Python 侧
1. `py_entry/runner/backtest.py`
   - 预检封装入口
   - Python 对 Rust 的统一调用面
2. `py_entry/strategy_hub/core/executor.py`
   - 单策略执行入口
3. `py_entry/strategy_hub/core/strategy_searcher.py`
   - 多策略/多品种工作流入口
4. `py_entry/strategy_hub/core/config.py`
   - WF 配置构造与透传
5. `py_entry/strategy_hub/demo.ipynb`
   - 人工调试入口

---

## 3. 核心类型

### 3.1 通用容器
1. `DataContainer`
   - 通用数据容器
   - 供回测引擎、优化器、对外结果使用
2. `BacktestSummary`
   - 通用结果容器
   - 包含 `indicators/signals/backtest/performance`

### 3.2 WF 内部专用容器
1. `WFDataContainer { data: DataContainer, ranges: WindowRanges }`
2. `WFSummaryContainer { summary: BacktestSummary, ranges: WindowRanges }`

硬约束：
1. 两类 WF 容器只允许在 WF 内部使用。
2. 两类 WF 容器不可变。
3. 任何切片都必须返回新对象。
4. 禁止在 WF 内直接切片裸 `DataContainer/BacktestSummary`。
5. 引擎调用时只借用 `.data` 或 `.summary` 载荷。

### 3.3 区间类型
1. `WindowRanges`
   - 描述单窗口 base/source 两类索引区间
2. `SourceRangeResult`
   - `WarmupRanges`
   - `NoWarmupRanges`

区间语义：
1. 全部使用右开区间 `[start, end)`。
2. base 与 source 区间严格分离。
3. source 区间只能由 `build_source_ranges(...)` 产出。

---

## 4. 预检与契约聚合

### 4.1 指标契约
每个指标必须实现：
1. `required_warmup_bars(resolved_params) -> usize`
2. `warmup_mode() -> Strict | Relaxed`

### 4.2 聚合函数
统一入口：
1. `resolve_indicator_contracts(indicators_params_py) -> IndicatorContractReport`

输出至少包含：
1. `warmup_bars_by_source`
2. `contracts_by_indicator`
3. `indicator_warmup_bars_base`

### 4.3 Python 预检入口
统一入口：
1. `Backtest.validate_wf_indicator_readiness(...)`

职责：
1. 调用 Rust 聚合函数
2. 绑定 `base_data_key`
3. 返回 WF 所需的 `W_base` 与 `W_s`
4. 失败直接报错

---

## 5. base 算法

### 5.1 三模式
1. `BorrowFromTrain`
2. `ExtendTest`
3. `NoWarmup`

### 5.2 base 窗口生成
实现位置：
1. `src/backtest_engine/walk_forward/data_splitter.rs`

输入：
1. `N`
2. `train_bars`
3. `min_warmup_bars`
4. `test_bars`
5. `indicator_warmup_bars_base`
6. `wf_warmup_mode`

输出：
1. 每个窗口的 `train/warmup/test` base 区间
2. `train_run_range`
3. `train_eval_range`
4. `eval_run_range`
5. `eval_stat_range`

硬约束：
1. `BorrowFromTrain/ExtendTest` 使用训练预热与测试预热。
2. `NoWarmup` 不生成任何预热段。
3. 滚动步长固定为 `test_bars`。

---

## 6. source 映射算法

### 6.1 统一工具函数
实现位置：
1. `src/backtest_engine/walk_forward/data_splitter.rs`

唯一入口：
1. `build_source_ranges(window_i, source_key, mode, W_s, mapping_col_s) -> SourceRangeResult`

### 6.2 输入
1. base 窗口区间
2. 当前 source 键
3. 当前模式
4. `W_s`
5. `mapping[source_key]`

### 6.3 输出
1. `WarmupRanges`
   - `source_train_run_range_s`
   - `source_train_eval_range_s`
   - `source_eval_run_range_s`
   - `source_eval_stat_range_s`
2. `NoWarmupRanges`
   - `source_train_range_s`
   - `source_test_range_s`

### 6.4 规则
1. `BorrowFromTrain/ExtendTest` 必须分别计算训练段与执行段的 source 预热起点。
2. `NoWarmup` 只做 direct mapping。
3. `map_s(x)` 缺失、越界、空区间、左侧样本不足，直接报错。
4. 禁止在其他模块再次推导 source 区间。

---

## 7. WF 内部切片工具

### 7.1 `slice_wf_data(...) -> WFDataContainer`
职责：
1. 输入 `WFDataContainer + WindowRanges`
2. 输出新的 `WFDataContainer`
3. 同时完成：
   - `mapping` base 切片
   - `source` source 切片
   - `mapping` 重基
   - `skip_mask` 切片
   - 一致性校验

### 7.2 `slice_wf_summary(...) -> WFSummaryContainer`
职责：
1. 输入 `WFSummaryContainer + WindowRanges`
2. 输出新的 `WFSummaryContainer`
3. 同时完成：
   - `indicators` 按 source 切
   - `signals/backtest` 按 base 切
   - `performance` 丢弃后重算

### 7.3 stitched 拼接工具
职责：
1. 输入窗口级 `WFDataContainer/WFSummaryContainer`
2. 输出 stitched 级 `WFDataContainer/WFSummaryContainer`
3. `backtest` 资金列只在 stitched 阶段重建
4. `performance` 只在 stitched 阶段二次重算

### 7.4 校验要求
1. `DataContainer` 与 `BacktestSummary` 的切片、拼接、校验都必须基于 Rust + Polars 矢量化实现。
2. `time` 列必须与理论时间序列完全一致。
3. `mapping` 必须先校验长度，再逐列校验映射后的 `time` 列。
4. `skip_mask` 按值完全一致校验。

---

## 8. WF 执行顺序

### 8.1 固定顺序
1. 预检，得到 `W_base/W_s`
2. 生成 base 窗口
3. 生成 `source_ranges_by_window`
4. 切出 `train_wf_data_i/eval_wf_data_i`
5. 优化器只消费 `train_wf_data_i.data`
6. 第一遍执行到 `ExecutionStage::Signals`
7. 注入信号，返回新的 `WFSummaryContainer`
8. 第二遍执行 `Backtest`
9. 切到测试非预热区
10. 计算窗口级 `Performance`
11. 拼接 `window_test_results`
12. 重建 stitched 资金列
13. 重算 stitched `Performance`
14. 对外脱壳为通用容器

### 8.2 容器边界
1. 训练阶段生成 `WFDataContainer`
2. 第一遍评估生成 `WFSummaryContainer`
3. 信号注入返回新的 `WFSummaryContainer`
4. 第二遍评估返回窗口级 `WFSummaryContainer`
5. stitched 阶段产出 stitched 级 `WFDataContainer/WFSummaryContainer`
6. 最终返回时才脱壳

---

## 9. 输出契约

### 9.1 对外返回
1. `window_test_results`
   - 返回通用 `DataContainer + BacktestSummary`
   - 只保留测试非预热区
2. `stitched_test_result`
   - 返回通用 `DataContainer + BacktestSummary`
   - 来源于窗口结果拼接，不回全量数据二次切片

### 9.2 外部可见口径
1. `indicators` 保持 source 语义
2. `signals/backtest/performance` 保持 base 语义
3. stitched 结果必须通过时间一致性强校验

---

## 10. 文件落点
1. `src/backtest_engine/indicators/**/*.rs`
2. `src/backtest_engine/indicators/registry.rs`
3. `src/types/outputs/indicator_contract.rs`
4. `src/types/inputs/walk_forward.rs`
5. `src/types/outputs/walk_forward.rs`
6. `src/backtest_engine/walk_forward/data_splitter.rs`
7. `src/backtest_engine/walk_forward/runner.rs`
8. `py_entry/runner/backtest.py`
9. `py_entry/strategy_hub/core/config.py`
10. `py_entry/strategy_hub/core/executor.py`
11. `py_entry/strategy_hub/core/strategy_searcher.py`
12. `py_entry/strategy_hub/demo.ipynb`
