# 统一 Ranges / Warmup / WF 执行范围与文件清单

对应文档：

1. [../00_meta/task_summary.md](../00_meta/task_summary.md)
2. [../02_spec/01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
3. [../02_spec/02_python_fetch_and_initial_build.md](../02_spec/02_python_fetch_and_initial_build.md)
4. [../02_spec/03_backtest_and_result_pack.md](../02_spec/03_backtest_and_result_pack.md)
5. [../02_spec/04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
6. [../02_spec/05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)
7. [03_execution_stages_and_acceptance.md](./03_execution_stages_and_acceptance.md)
8. [../04_review/04_execution_backfill_template.md](../04_review/04_execution_backfill_template.md)
9. [02_test_plan.md](./02_test_plan.md)
10. [05_pre_execution_ai_review.md](./05_pre_execution_ai_review.md)

本文只保留三类内容：

1. 执行范围
2. 文件修改清单
3. 物理模块边界

分阶段执行、阶段验收与回补模板已拆到：

1. [03_execution_stages_and_acceptance.md](./03_execution_stages_and_acceptance.md)
2. [../04_review/04_execution_backfill_template.md](../04_review/04_execution_backfill_template.md)
3. [05_pre_execution_ai_review.md](./05_pre_execution_ai_review.md)

## 0. 摘要归属与落地引用

执行时统一按“摘要归属文档 -> 实现落点”的方式理解，不在执行文档里复制第二套解释。

| 摘要归属 | 主要实现落点 | 本文只关心什么 |
|---|---|---|
| `01_overview_and_foundation.md` | `src/types/*`、`src/backtest_engine/data_ops/*` | `WarmupRequirements`、`TimeProjectionIndex`、类型、builder、通用约束 |
| `02_python_fetch_and_initial_build.md` | `src/backtest_engine/data_ops/fetch_planner/*`、`py_entry/runner/setup_utils.py` | planner 状态机、Python/Rust 职责边界、取数对接 |
| `03_backtest_and_result_pack.md` | `src/backtest_engine/top_level_api.rs`、`src/backtest_engine/backtester/*`、`src/backtest_engine/performance_analyzer/mod.rs`、`src/backtest_engine/data_ops/*` | 单次回测主流程、`build_result_pack(...)`、`extract_active(...)` |
| `04_walk_forward_and_stitched.md` | `src/backtest_engine/walk_forward/*` | `WalkForwardPlan`、窗口主循环、跨窗注入、`StitchedReplayInput` |
| `05_segmented_backtest_truth_and_kernel.md` | `src/backtest_engine/backtester/*` | `ResolvedRegimePlan`、`run_backtest_with_schedule(...)`、统一 kernel、Rust 等价性测试基线 |

## 1. 执行目标

本次执行只做一件事：

1. 先把内部主链迁移到摘要定义的统一 `DataPack / ResultPack / SourceRange / WF / stitched` 语义；旧公开 `walk_forward` 壳层按分阶段桥接策略在最终阶段一次性切换。

完成标准：

1. `DataPack / ResultPack / SourceRange` 真值入口与摘要一致。
2. 初始取数、单次回测、`extract_active(...)`、WF、stitched 使用同一套 `ranges / mapping` 语义。
3. `walk_forward` 返回结构与摘要一致。
4. 不保留兼容层，不保留旧字段，不保留旧 `transition_*` 口径。

## 2. 破坏性更新与全局约束

### 2.1 破坏性更新清单

1. `DataContainer` 迁移为 `DataPack`。
2. `BacktestSummary` 迁移为 `ResultPack`。
3. `SourceRange { warmup, total }` 迁移为 `SourceRange { warmup_bars, active_bars, pack_bars }`。
4. `WalkForwardConfig` 中的 `train_bars / test_bars / transition_bars` 迁移到摘要定义的新字段口径。
5. `WindowArtifact / StitchedArtifact / WalkForwardResult / NextWindowHint` 全量按摘要重写。
6. Python 结果包装层同步迁移到新字段，不保留旧字段兼容。
7. 旧的 `transition_range / transition_bars / transition_time_range` 等字段全部删除。
8. `WalkForwardConfig.inherit_prior` 删除，不保留公开兼容语义。
9. `WalkForwardConfig.optimizer_config` 保留，作为优化器配置唯一来源。
10. `WfWarmupMode::NoWarmup` 删除；关闭指标预热实验统一走 `ignore_indicator_warmup = true`。

### 2.1.1 分阶段迁移口径

1. “不保留兼容层”只约束最终公共形态：
   - 不新增公共兼容字段
   - 不新增公共兼容 API
   - 不新增公共双轨语义
2. 分阶段执行期间，尚未轮到公共切换的旧公开路径可以原样保留，以维持整仓编译闭环。
3. 这种“旧公开路径暂未切换”属于迁移顺序，不属于兼容层。
4. 因而：
   - 阶段 A1 / A2 / B / C 不要求 `walk_forward` 公共返回已经切到摘要最终形态
   - 阶段 D1 / D2 也不是公共 API 切换阶段
   - 阶段 E 才一次性完成 `WalkForwardResult.stitched_result` 与相关公共类型的最终切换
   - 在阶段 E 前，`src/types/outputs/walk_forward.rs` 继续保留旧公开壳层，以维持编译闭环；这属于迁移顺序，不属于兼容层
5. 在最终切换发生前，不允许发明新的中间公共结构去承接迁移状态。

### 2.1.2 旧公开 API 与新核心类型桥接策略

1. 本任务采用“旧公开壳层后切、内部主链先切”的单桥接策略。
2. 在阶段 E 前，允许保留的只有：
   - 既有 `src/types/outputs/walk_forward.rs` 公开壳层
   - 既有 `walk_forward` 公开返回路径
3. 在阶段 E 前，不允许新增：
   - 新的公共兼容字段
   - 新的公共兼容 API
   - 新的中间公共结构
   - 公共双轨语义
4. 在阶段 E 前，若公开壳层需要继续工作，只允许通过私有模块边界桥接到新的内部核心类型：
   - `DataContainer -> DataPack`
   - `BacktestSummary -> ResultPack`
5. 这条桥接只允许存在于私有入口 / facade 边界：
   - 不允许在窗口规划、窗口主循环、stitched 组装或 segmented replay 内部重复写第二套桥接逻辑
6. 若实现过程中发现这条私有桥接仍不足以维持编译闭环，就必须前移公共类型切换；不允许继续堆叠新的过渡层。

### 2.2 错误系统约束

1. 总入口优先复用 `src/error/quant_error.rs` 里的 `QuantError`。
2. 能落到已有子错误类型时，优先复用：
   - `src/error/backtest_error/error.rs`
   - `src/error/indicator_error/error.rs`
   - `src/error/signal_error/error.rs`
   - `src/error/optimizer_error/error.rs`
3. 不新增平行错误系统，不新增第二套 PyO3 异常映射链。
4. 若确实需要扩充错误类型，优先在现有错误枚举中补分支。

### 2.3 PyO3 / stub / 类型源头约束

1. Rust 类型是唯一事实源。
2. 所有对外边界类型都优先在 Rust 端定义，再通过 PyO3 暴露。
3. Python 侧只消费 Rust 自动生成的 `.pyi` 存根，不再镜像维护一份平行输入/输出类型。
4. 若本次重构新增或修改了对外类型，必须同步更新 PyO3 暴露与 `just stub` 生成结果。
5. 不允许为了测试或包装方便，在 Python 端再定义一套与 Rust 同语义的镜像类型。

重点边界对象：

1. `DataPack`
2. `ResultPack`
3. `SourceRange`
4. `WalkForwardConfig`
5. `WalkForwardResult`
6. `WindowArtifact`
7. `StitchedArtifact`
8. `StitchedMeta`
9. `BacktestParamSegment`
10. `NextWindowHint`

### 2.4 模块拆分约束

1. `mod.rs` 只负责：
   - 子模块声明
   - `pub use`
   - 薄入口
2. 单文件目标控制在 `200~250` 行；超过 `300` 行必须拆分，纯类型定义文件除外。
3. 已经超过 `300` 行的旧文件，本次默认抽新文件，不继续在原文件里追加大段新逻辑。
4. 共享真值 helper、builder、切片、编排流程不能混写在同一文件。
5. 禁止新增 `utils.rs`、`helpers.rs` 这类无边界收纳文件。
6. 模块拆分按“真值链 / 对象归属”组织，不按“谁调用我”组织。
7. 允许同一真值链内的相邻小模块在实现时合并；不允许跨真值链合并成新的大文件。

## 3. 推荐物理文件边界

### 3.1 `data_ops`

```text
src/backtest_engine/data_ops/
  mod.rs
  warmup_requirements.rs
  time_projection.rs
  data_pack_builder.rs
  result_pack_builder.rs
  active_extract.rs
  window_slice.rs
  fetch_planner/
    mod.rs
    planner.rs
    source_state.rs
    initial_ranges.rs
```

归属约束：

1. `warmup_requirements.rs`
   - `W_resolved -> W_normalized -> W_applied -> W_backtest_exec_base -> W_required`
2. `time_projection.rs`
   - `exact_index_by_time(...)`
   - `map_source_row_by_time(...)`
   - `map_source_end_by_base_end(...)`
   - `validate_coverage(...)`
3. `data_pack_builder.rs`
   - `build_mapping_frame(...)`
   - `build_data_pack(...)`
4. `result_pack_builder.rs`
   - `build_result_pack(...)`
   - `strip_indicator_time_columns(...)`
5. `active_extract.rs`
   - `extract_active(...)`
6. `window_slice.rs`
   - `slice_data_pack_by_base_window(...)`
7. `fetch_planner/`
   - planner 状态机，不和 builder / slice 混写

### 3.2 `walk_forward`

```text
src/backtest_engine/walk_forward/
  mod.rs
  plan.rs
  injection.rs
  window_runner.rs
  stitch.rs
  time_ranges.rs
  next_window_hint.rs
```

归属约束：

1. `plan.rs`
   - `WalkForwardPlan`
   - `WindowPlan`
   - `build_window_indices(...)`
2. `injection.rs`
   - `detect_last_bar_position(...)`
   - `build_carry_only_signals(...)`
   - `build_final_signals(...)`
3. `window_runner.rs`
   - 每窗执行主循环
4. `stitch.rs`
   - `extract_active(...) -> test_active_result -> stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
   - `StitchedReplayInput`
5. `time_ranges.rs`
   - `build_pack_time_ranges(...)`
   - `build_window_time_ranges(...)`
6. `next_window_hint.rs`
   - `NextWindowHint`

### 3.3 `backtester`

```text
src/backtest_engine/backtester/
  mod.rs
  main_loop.rs
  data_preparer.rs
  atr_calculator.rs
  schedule_contract.rs
  schedule_policy.rs
  params_selector.rs
  output_schema.rs
  tests.rs
```

归属约束：

1. `mod.rs`
   - 只保留 `run_backtest(...)` 与 `run_backtest_with_schedule(...)` 薄入口
2. `schedule_contract.rs`
   - contiguity
   - ATR contract
3. `schedule_policy.rs`
   - segment-vary policy
4. `params_selector.rs`
   - `ParamsSelector`
5. `output_schema.rs`
   - `build_schedule_output_schema(...)`

## 4. 文件修改清单

### 4.1 Rust 类型与导出

必须修改：

1. `src/types/inputs/data.rs`
2. `src/types/inputs/walk_forward.rs`
3. `src/types/outputs/backtest.rs`
4. `src/types/outputs/walk_forward.rs`
5. `src/types/mod.rs`
6. `src/types/outputs/mod.rs`
7. `src/types/inputs/mod.rs`

主要任务：

1. 新内部主链先切到 `DataPack`，最终公共切换再一次性完成 `DataContainer -> DataPack`。
2. 新内部主链先切到 `ResultPack`，最终公共切换再一次性完成 `BacktestSummary -> ResultPack`。
3. 引入新 `SourceRange`。
4. `walk_forward` 相关输出结构按最终摘要重写。
5. `WalkForwardResult.stitched_result` 的最终切换与回填放到阶段 E 一次性完成：
   - 阶段 A1 / A2 / B / C 不要求改写 `src/types/outputs/walk_forward.rs` 的旧公开字段依赖
   - 旧 `walk_forward` 公开类型在阶段 E 前只作为未切换的公共壳层保留
   - 阶段 D1 / D2 不定义新的中间公共返回结构
   - `StitchedReplayInput` 只停留在内部 stitched 模块边界
   - 若阶段 D1 / D2 为保持编译暂时保留既有公开返回路径，这只允许是未切换前的既有公共边界
6. 同步 PyO3 暴露与 stub 生成。

### 4.2 Rust 数据构建与切片

必须修改：

1. `src/backtest_engine/data_ops/mod.rs`
2. `src/backtest_engine/data_ops/warmup_requirements.rs`
3. `src/backtest_engine/data_ops/time_projection.rs`
4. `src/backtest_engine/data_ops/data_pack_builder.rs`
5. `src/backtest_engine/data_ops/result_pack_builder.rs`
6. `src/backtest_engine/data_ops/active_extract.rs`
7. `src/backtest_engine/data_ops/window_slice.rs`
8. `src/backtest_engine/data_ops/fetch_planner/mod.rs`
9. `src/backtest_engine/data_ops/fetch_planner/planner.rs`
10. `src/backtest_engine/data_ops/fetch_planner/source_state.rs`
11. `src/backtest_engine/data_ops/fetch_planner/initial_ranges.rs`
12. `src/backtest_engine/indicators/contracts.rs`

主要任务：

1. 落地 `build_mapping_frame(...)`、`build_data_pack(...)`、`build_result_pack(...)`、`strip_indicator_time_columns(...)`。
2. 落地 `slice_data_pack_by_base_window(...)` 与 `extract_active(...)`。
3. 落地 stitched 最终 `strip -> build_result_pack(...)` 所需的 builder 配合。
4. 在 `time_projection.rs` 落地 `resolve_source_interval_ms(source_key)`，作为 coverage / 补拉 / 右边界投影唯一 `interval_ms` 来源。
5. 落地共享 warmup helper：
   - `resolve_contract_warmup_by_key(...)`
   - `normalize_contract_warmup_by_key(...)`
   - `apply_wf_warmup_policy(...)`
   - `resolve_backtest_exec_warmup_base(...)`
   - `merge_required_warmup_by_key(...)`
6. 这条 helper 链必须完整承接：
   - `W_resolved`
   - `W_normalized`
   - `W_applied`
   - `W_backtest_exec_base`
   - `W_required`
7. planner 路径即使当前固定不忽略指标 warmup，也必须显式调用 `apply_wf_warmup_policy(..., false)`。
8. planner 初始化只允许先生成 `source_keys`，再复用 `resolve_source_interval_ms(source_key)`；不允许在 `fetch_planner/*` 里再写第二套 timeframe -> interval 解析。
9. `skip_mask` contract 统一在 `build_data_pack(...)` 校验。
10. `data_ops/mod.rs` 只保留子模块声明与薄导出。

### 4.3 Rust 回测主流程

必须修改：

1. `src/backtest_engine/top_level_api.rs`
2. `src/backtest_engine/utils/context.rs`
3. `src/backtest_engine/backtester/mod.rs`
4. `src/backtest_engine/backtester/signal_preprocessor.rs`
5. `src/backtest_engine/performance_analyzer/mod.rs`

主要任务：

1. 单次回测主流程统一吃 `DataPack`。
2. `build_result_pack(...)` 成为正式结果构建入口。
3. 绩效模块内部按 `data.ranges[data.base_data_key].warmup_bars` 自己切 `active 区间`。
4. `performance` 保持通用指标字典口径：`Option<HashMap<String, f64>>`。
5. 清掉 `has_leading_nan` 在回测模块里的旧作用，最终只保留在 `signals`。
6. `execute_single_backtest(...)` 与 `BacktestContext` 返回新 `ResultPack`。
7. `extract_active(...)`、pair consistency 校验和导出逻辑必须建立在同源 `DataPack / ResultPack` 配对之上。
8. `analyze_performance(...)` 的输入高度校验、内部切片与 fail-fast contract 必须单独落 dedicated test，不只靠回归间接覆盖。

### 4.4 Rust WF 与 stitched

必须修改：

1. `src/backtest_engine/walk_forward/mod.rs`
2. `src/backtest_engine/walk_forward/plan.rs`
3. `src/backtest_engine/walk_forward/injection.rs`
4. `src/backtest_engine/walk_forward/window_runner.rs`
5. `src/backtest_engine/walk_forward/stitch.rs`
6. `src/backtest_engine/walk_forward/time_ranges.rs`
7. `src/backtest_engine/walk_forward/next_window_hint.rs`
8. `src/backtest_engine/walk_forward/data_splitter.rs`
9. `src/backtest_engine/walk_forward/runner.rs`

按需修改：

1. `src/backtest_engine/optimizer/runner/rebuild.rs`

主要任务：

1. 用新窗口索引工具函数替换旧 `generate_windows(...)` 逻辑。
2. 落地 `WalkForwardPlan`、`WindowPlan` 与 `build_window_indices(...)`。
3. 落地跨窗注入与窗口主循环。
4. 训练阶段保持 `train_pack_data -> best_params`，不新增训练 `RunArtifact`。
5. 落地 `StitchedReplayInput` 与 stitched 输入构造：
   - `stitched_data`
   - `stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
   - `stitched_indicators_with_time`
6. `stitched_atr_by_row` 必须按唯一算法落地。
   - `stitched_data` 继续保持 active-only 零预热
   - 但 `stitched_atr_by_row` 不允许直接在 active-only `stitched_data.base` 上现算
   - 必须先基于 `full_data.base` 左侧已有上下文物化，再投影回 stitched 行轴
7. `walk_forward/mod.rs` 只保留薄导出与入口。
8. `runner.rs` 与 `data_splitter.rs` 若保留，只允许作为薄 facade / 转发层。
9. `build_pack_time_ranges(...)` 与 `build_window_time_ranges(...)` 只允许落在 `time_ranges.rs`，不允许在窗口主循环、stitched 组装或 Python 包装层各写一套。

### 4.5 Rust segmented replay / kernel

必须修改：

1. `src/backtest_engine/backtester/mod.rs`
2. `src/backtest_engine/backtester/main_loop.rs`
3. `src/backtest_engine/backtester/data_preparer.rs`
4. `src/backtest_engine/backtester/atr_calculator.rs`
5. `src/backtest_engine/backtester/schedule_contract.rs`
6. `src/backtest_engine/backtester/schedule_policy.rs`
7. `src/backtest_engine/backtester/params_selector.rs`
8. `src/backtest_engine/backtester/output_schema.rs`
9. `src/backtest_engine/backtester/state/write_config.rs`
10. `src/backtest_engine/backtester/output/output_init.rs`
11. `src/backtest_engine/backtester/tests.rs`

主要任务：

1. 新增 `BacktestParamSegment` 与 `run_backtest_with_schedule(...)`。
2. `run_backtest(...)` 退化成单段 `schedule` 再调用 `run_backtest_with_schedule(...)`。
3. 统一单一路径的 `ParamsSelector { schedule, segment_idx }`。
4. 抽取统一 kernel，保持与单次回测主循环等价。
5. 落地：
   - `validate_schedule_contiguity(...)`
   - `validate_backtest_param_schedule_policy(...)`
   - `validate_schedule_atr_contract(...)`
6. multi-segment output schema 作为独立 contract 落地。
7. 新增 Rust 等价性测试基线。
8. `backtester/mod.rs` 只保留对外入口与薄导出。

### 4.6 Python 包装层

必须修改：

1. `py_entry/runner/backtest.py`
2. `py_entry/runner/results/wf_result.py`
3. `py_entry/runner/results/run_result.py`

按需修改：

1. 任何直接访问旧 `DataContainer / BacktestSummary / transition_*` 字段的 Python 调用点

主要任务：

1. 更新 Python 侧类型名与字段访问。
2. 删除旧 WF 字段读取逻辑。
3. 对齐新的窗口结果和 stitched 结果结构。
4. Python 包装层必须显式对齐 `WalkForwardResult.stitched_result.meta.backtest_schedule`。

### 4.7 测试

重点修改或新增：

1. `src/backtest_engine/backtester/tests.rs`
2. `py_entry/Test/backtest/test_data_fetch_planner_contract.py`
3. `py_entry/Test/backtest/test_strip_indicator_time_columns_contract.py`
4. `py_entry/Test/backtest/test_performance_contract.py`
5. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
6. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
7. `py_entry/Test/walk_forward/test_walk_forward_guards.py`
8. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`
9. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
10. 与 `extract_active(...)`、stitched、`NextWindowHint` 相关测试
11. Rust 等价性测试：
   - `legacy_run_backtest_reference(...)` vs 新 `run_backtest(...)`
12. segmented replay 测试：
   - `run_backtest_with_schedule(...)` 的 contiguity / schema / rebase / 单段退化
