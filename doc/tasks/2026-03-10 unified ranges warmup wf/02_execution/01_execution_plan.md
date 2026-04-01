# 统一 Ranges / Warmup / WF 重构执行文档

对应摘要：

1. [../01_summary/task_summary.md](../01_summary/task_summary.md)
2. [../01_summary/01_overview_and_foundation.md](../01_summary/01_overview_and_foundation.md)
3. [../01_summary/02_python_fetch_and_initial_build.md](../01_summary/02_python_fetch_and_initial_build.md)
4. [../01_summary/03_backtest_and_result_pack.md](../01_summary/03_backtest_and_result_pack.md)
5. [../01_summary/04_walk_forward_and_stitched.md](../01_summary/04_walk_forward_and_stitched.md)
6. [../01_summary/05_segmented_backtest_truth_and_kernel.md](../01_summary/05_segmented_backtest_truth_and_kernel.md)
7. [02_test_plan.md](./02_test_plan.md)

本文只保留执行所需内容：

1. 实施顺序
2. 关键接口
3. 文件修改清单
4. 破坏性更新与删除项
5. 测试与验收

不再重复摘要文档里的方案解释。
执行文档只记录代码落地与阶段回补，不记录摘要是否审阅通过、执行文档是否审阅通过等流程 gate 状态。

## 0. 摘要归属与落地引用

执行时统一按“摘要归属文档 -> 实现落点”的方式理解，不在执行文档里复制第二套解释。

| 摘要归属 | 本次在实现里主要落到哪里 | 执行文档只关心什么 |
|---|---|---|
| `01_overview_and_foundation.md` | `src/types/*`、`src/backtest_engine/data_ops/mod.rs` | 类型、builder、共享真值入口与通用约束 |
| `02_python_fetch_and_initial_build.md` | `src/backtest_engine/data_ops/mod.rs`、`py_entry/runner/setup_utils.py`、取数相关 Python 入口 | planner 状态机、Python/Rust 职责边界、取数对接 |
| `03_backtest_and_result_pack.md` | `src/backtest_engine/top_level_api.rs`、`src/backtest_engine/utils/context.rs`、`src/backtest_engine/backtester/mod.rs`、`src/backtest_engine/backtester/signal_preprocessor.rs`、`src/backtest_engine/performance_analyzer/mod.rs`、`src/backtest_engine/data_ops/mod.rs` | 单次回测主流程、`build_result_pack(...)`、`extract_active(...)` |
| `04_walk_forward_and_stitched.md` | `src/backtest_engine/walk_forward/*` | `build_window_indices(...)`、窗口主循环、跨窗注入、给 `05` 构造 stitched replay 输入 |
| `05_segmented_backtest_truth_and_kernel.md` | `src/backtest_engine/backtester/*` | `run_backtest_with_schedule(...)`、统一 kernel、单次退化成单段 schedule、Rust 等价性测试基线 |

这里再把执行文档的引用边界写死：

1. 若某个概念在摘要里已经有明确归属，执行文档只写“改哪些文件、哪些入口调用它”，不重复解释概念本身。
2. 若某个实现步骤需要依赖共享真值，优先回到其归属摘要查看，不在执行文档里再抄一遍整段算法。
3. 执行文档里允许保留最小必要的接口片段与阶段顺序，但不再复制摘要里的长表格、术语定义或完整伪代码。

## 1. 执行目标

本次执行只做一件事：

1. 把现有 `DataContainer / BacktestSummary / walk_forward` 旧链路，整体迁移到摘要文档定义的统一 `DataPack / ResultPack / SourceRange / WF / stitched` 语义。

完成标准：

1. `DataPack / ResultPack / SourceRange` 真值入口与摘要一致。
2. 初始取数、单次回测、`extract_active(...)`、WF、stitched 使用同一套 `ranges / mapping` 语义。
3. `walk_forward` 返回结构与摘要文档 `## 7` 一致。
4. 不保留兼容层，不保留旧字段，不保留旧 `transition_*` 口径。

## 2. 破坏性更新清单

本任务按破坏性更新执行：

1. `DataContainer` 迁移为 `DataPack`。
2. `BacktestSummary` 迁移为 `ResultPack`。
3. `SourceRange { warmup, total }` 迁移为 `SourceRange { warmup_bars, active_bars, pack_bars }`。
4. `WalkForwardConfig` 中的 `train_bars / test_bars / transition_bars` 迁移到摘要文档定义的新字段口径；WF 预热配置最终收敛为 `BorrowFromTrain | ExtendTest` 加 `ignore_indicator_warmup: bool`，并显式补入 `optimize_metric`。
5. `WindowArtifact / StitchedArtifact / WalkForwardResult / NextWindowHint` 全量按摘要文档重写。
6. Python 结果包装层同步迁移到新字段，不保留旧字段兼容。
7. 旧的 `transition_range / transition_bars / transition_time_range` 等字段全部删除。

## 2.1 错误系统约束

本任务实现时，错误处理必须优先复用现有 `src/error` 体系：

1. 总入口优先使用 `src/error/quant_error.rs` 里的 `QuantError`。
2. 能落到已有子错误类型时，优先复用：
   - `src/error/backtest_error/error.rs`
   - `src/error/indicator_error/error.rs`
   - `src/error/signal_error/error.rs`
   - `src/error/optimizer_error/error.rs`
3. 不新增平行错误系统，不新增第二套 PyO3 异常映射链。
4. 若确实需要扩充错误类型，优先在现有错误枚举中补分支，而不是另起一个新错误模块。
5. `build_data_pack(...)`、`build_result_pack(...)`、`extract_active(...)`、WF、stitched 相关新错误，默认都先收口到 `QuantError`。

## 2.2 PyO3 / stub / 类型源头约束

本任务必须继续遵守当前项目的 PyO3 接口与 stub 生成范式：

1. Rust 类型是唯一事实源。
2. 所有对外边界类型都优先在 Rust 端定义，再通过 PyO3 暴露。
3. Python 侧只消费 Rust 自动生成的 `.pyi` 存根，不再镜像维护一份平行输入/输出类型。
4. 若本次重构新增或修改了对外类型，必须同步更新 PyO3 暴露与 `just stub` 生成结果。
5. 不允许为了测试或包装方便，在 Python 端再定义一套与 Rust 同语义的镜像类型。
6. Python 用户层可以继续保留面向业务可读性的配置对象，但它们不直接作为 Rust 边界类型。
7. 只要某个核心输入/输出类型可以直接在 Rust 端定义并通过 PyO3 导出，就必须直接走 Rust + stub 生成 `.pyi`，不要在 Python 端再补一份同语义 dataclass / Pydantic 模型 / 手写 `.pyi`。
8. 本任务重点约束的对象包括：
   - `DataPack`
   - `ResultPack`
   - `SourceRange`
   - `WalkForwardConfig`
   - `WalkForwardResult`
   - `WindowArtifact`
   - `StitchedArtifact`
   - `StitchedMeta`
   - `BacktestParamSegment`
   - `NextWindowHint`
9. Python 侧若确实保留包装层对象，必须满足：
   - 只做组合、展示、导出或便捷访问
   - 不重新定义上述 Rust 核心边界对象的真值字段与结构契约

## 3. 文件修改清单

### 3.1 Rust 类型与导出

必须修改：

1. `src/types/inputs/data.rs`
2. `src/types/inputs/walk_forward.rs`
3. `src/types/outputs/backtest.rs`
4. `src/types/outputs/walk_forward.rs`
5. `src/types/mod.rs`
6. `src/types/outputs/mod.rs`
7. `src/types/inputs/mod.rs`

主要任务：

1. 重命名 `DataContainer -> DataPack`。
2. 重命名 `BacktestSummary -> ResultPack`。
3. 引入新 `SourceRange`。
4. 重写 `walk_forward` 相关输出结构。
5. 同步 PyO3 暴露与 stub 生成。

### 3.2 Rust 数据构建与切片

必须修改：

1. `src/backtest_engine/data_ops/mod.rs`
2. `src/backtest_engine/indicators/contracts.rs`

主要任务：

1. 落地 `build_mapping_frame(...)`。
2. 落地 `build_data_pack(...)`。
3. 落地 `build_result_pack(...)`。
4. 落地 `strip_indicator_time_columns(...)`。
5. 落地 `slice_data_pack_by_base_window(...)`。
6. 落地 `extract_active(...)`。
7. 落地 stitched 最终 `strip -> build_result_pack(...)` 所需的 builder 配合。
8. 落地共享 warmup helper：
   - `resolve_contract_warmup_by_key(...)`
   - `normalize_contract_warmup_by_key(...)`
   - `apply_wf_warmup_policy(...)`
   - `resolve_backtest_exec_warmup_base(...)`
   - `merge_required_warmup_by_key(...)`
   具体 helper 契约统一引用摘要 `01_overview_and_foundation.md`，执行文档不再重复解释。

### 3.3 Rust 回测主流程

必须修改：

1. `src/backtest_engine/top_level_api.rs`
2. `src/backtest_engine/utils/context.rs`
3. `src/backtest_engine/backtester/mod.rs`
4. `src/backtest_engine/backtester/signal_preprocessor.rs`
5. `src/backtest_engine/performance_analyzer/mod.rs`

主要任务：

1. 让单次回测主流程统一吃 `DataPack`。
2. 让 `build_result_pack(...)` 成为正式结果构建入口。
3. 让绩效模块内部按 `data.ranges[data.base_data_key].warmup_bars` 自己切 `active 区间`。
4. 清掉 `has_leading_nan` 在回测模块里的旧作用：
   - 最终只保留在 `signals`
   - 仅供调试
   - 不再从 `signals` 透传到 `backtest`
   - 不再在 `signal_preprocessor` 里参与进场屏蔽
   - 不再被 `performance_analyzer` 读取
   - 一句话概括：除 `signals` 外，其他模块都不应再感知或消费 `has_leading_nan`
5. 让 `execute_single_backtest(...)` 与 `BacktestContext` 返回新 `ResultPack`。

### 3.4 Rust WF 与 stitched

必须修改：

1. `src/backtest_engine/walk_forward/data_splitter.rs`
2. `src/backtest_engine/walk_forward/runner.rs`
3. `src/backtest_engine/walk_forward/mod.rs`

按需修改：

1. `src/backtest_engine/optimizer/runner/rebuild.rs`

主要任务：

1. 用新窗口索引工具函数替换旧 `generate_windows(...)` 逻辑。
2. 落地 `WalkForwardPlan`、`WindowPlan` 与 `build_window_indices(...)` 及其 3 个私有步骤。
3. 落地跨窗注入。
4. 落地窗口主循环。
5. 落地 `StitchedReplayInput` 与 stitched 输入构造：
   - `stitched_data`
   - `stitched_signals`
   - `backtest_schedule: Vec<BacktestParamSegment>`
   - `stitched_atr_by_row`
   - `stitched_indicators_with_time`
   - `StitchedReplayInput` 只收纳这批既有正式输入真值，不新增第二套 replay 解释层
   - `stitched_atr_by_row` 必须按唯一算法落地：
     - 先按 unique `resolved_atr_period` 计算 stitched base 全量 ATR cache
     - 再按 `backtest_schedule` 做 segment 级 slice + concat
   - 不允许按 row 逐行现算，也不允许先按窗口各算一条 ATR 再二次拼接
   - `best_params` 的冻结语义唯一落点是 `rebuild_param_set(...)`
   - 不允许在 WF / stitched 层额外做第二次 canonicalize，再派生一套 concrete params
6. 落地 `NextWindowHint` 新算法。

### 3.5 Rust segmented replay / kernel

必须修改：

1. `src/backtest_engine/backtester/mod.rs`
2. `src/backtest_engine/backtester/main_loop.rs`
3. `src/backtest_engine/backtester/data_preparer.rs`
4. `src/backtest_engine/backtester/atr_calculator.rs`
5. `src/backtest_engine/backtester/state/write_config.rs`
6. `src/backtest_engine/backtester/output/output_init.rs`
7. `src/backtest_engine/backtester/tests.rs`（新增）

主要任务：

1. 新增 `BacktestParamSegment` 与 schedule replay 入口 `run_backtest_with_schedule(...)`。
2. 让 `run_backtest(...)` 在内部先构造单段 `schedule`，再直接调用 `run_backtest_with_schedule(...)`。
3. 统一为单一路径的 `ParamsSelector { schedule, segment_idx }` 与 `select_params_for_row(...)`。
4. 抽取统一 kernel，保持与当前单次回测主循环的初始化顺序、循环顺序、写入顺序等价。
5. 落地 `validate_schedule_contiguity(...)`、`validate_backtest_param_schedule_policy(...)`、`validate_schedule_atr_contract(...)`。
6. 把 multi-segment output schema 提升成独立 contract：
   - `build_schedule_output_schema(schedule)` 必须稳定决定列集合、列顺序与 dtype
   - 多段 schedule 下按并集列输出
   - 未启用 segment 的功能列必须写入文档已定义的非激活态默认值
   - 当前正式语义下，这些按 segment 启停变化的可选功能列全部是 `f64` 风险价格列，默认值统一写 `NaN`
   - 单段 schedule 必须退化成当前固定 schema
7. 新增 Rust 等价性测试基线：
   - 先对旧 `run_backtest(...)` 清掉 `has_leading_nan` 旧作用链
   - 再冻结成 `legacy_run_backtest_reference(...)`
   - 最后与新的 `run_backtest(...)` 做严格逐项对比

### 3.6 Python 包装层

必须修改：

1. `py_entry/runner/backtest.py`
2. `py_entry/runner/results/wf_result.py`
3. `py_entry/runner/results/run_result.py`

按需修改：

1. 任何直接访问旧 `DataContainer / BacktestSummary / transition_*` 字段的 Python 调用点
2. Python 包装层必须显式对齐 `stitched_result.meta.backtest_schedule`
   - 不允许只在 Rust 内部临时传递 `backtest_schedule`，却在最终 Python 结果结构里丢失

主要任务：

1. 更新 Python 侧类型名与字段访问。
2. 删除旧 WF 字段读取逻辑。
3. 对齐新的窗口结果和 stitched 结果结构。

### 3.7 测试

重点修改或新增：

1. `src/backtest_engine/backtester/tests.rs`（新增）
2. `py_entry/Test/backtest/test_data_fetch_planner_contract.py`
3. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
4. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
5. `py_entry/Test/walk_forward/test_walk_forward_guards.py`
6. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`
7. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
8. 新增与 `extract_active(...)`、stitched、`NextWindowHint` 相关测试
9. 新增 Rust 等价性测试：
   - `legacy_run_backtest_reference(...)` vs 新 `run_backtest(...)`
10. 新增 segmented replay 测试：
   - `run_backtest_with_schedule(...)` 的 contiguity / schema / rebase / 单段 schedule 退化

## 4. 分阶段执行与阶段验收

必须按阶段串行执行，不要一次性并行改大块逻辑。

通用规则：

1. 只有当前阶段通过验收，才能进入下一阶段。
2. 每个阶段结束后，必须立刻回填本文 `## 10` 的阶段完成记录，不能等到全部做完再补。
3. 每个阶段的正式验收优先使用：
   - `just check`
   - 对应阶段的最小测试命令
4. 若该阶段测试文件尚未落地，允许先用审阅清单做临时验收；但必须在后续阶段把测试补齐，并回填到同一条阶段记录里。
5. 最终总验收仍然保留：
   - `just check`
   - `just test`

### 阶段 A：类型、builder 与基础真值

阶段目标：

1. 先立住 `DataPack / ResultPack / SourceRange`。
2. 先立住 `build_mapping_frame(...) / build_data_pack(...) / build_result_pack(...) / strip_indicator_time_columns(...)`。
3. 明确写死哪些路径必须走 builder，哪些路径是例外。

关键落点：

1. `3.1 Rust 类型与导出`
2. `3.2 Rust 数据构建与切片` 中的 builder 部分

阶段约束：

1. `build_mapping_frame(...)` 在生产链路里只由 `build_data_pack(...)` 调用；但可以保留 PyO3 暴露，作为测试 / 调试工具函数。
2. `build_result_pack(...)` 绝不调用 `build_mapping_frame(...)`，只继承 `data.mapping` 子集。
3. `build_result_pack(...)` 的 `indicators` 入参正式语义是 raw indicators，也就是还没带 `time` 列的指标结果。
4. 若上游手里拿到的是某个已有 `ResultPack.indicators`，必须先统一调用 `strip_indicator_time_columns(...)`，再允许喂给 `build_result_pack(...)`。
5. `extract_active(...)` 是唯一不走 builder 的显式特例，但本阶段只冻结它的边界，不在本阶段实现完整逻辑。
6. `ResultPack` 必须显式携带 `base_data_key`，后续 `&ResultPack` helper 统一从 `result.base_data_key` 读取 base 语义。

阶段验收：

1. 先跑 `just check`
2. 再跑：
   - `just test-py path="py_entry/Test/backtest/test_data_pack_contract.py"`
   - `just test-py path="py_entry/Test/backtest/test_result_pack_contract.py"`
   - `just test-py path="py_entry/Test/backtest/test_mapping_projection_contract.py"`
3. 若上述测试尚未落地，至少完成一次审阅：
   - 对照摘要 `01 / 03`
   - 对照本文 `5.1 / 5.2`
   - 明确确认 `build_result_pack(...)` 没有误走 `build_mapping_frame(...)`

### 阶段 B：初始取数、planner 状态机与初始 `DataPack`

阶段目标：

1. Python 只保留网络请求与空响应重试。
2. Rust 统一承担 planner 状态推进、共享 warmup 聚合、首尾覆盖、初始 `ranges` 计算与 `build_data_pack(...)`。

关键落点：

1. `3.2 Rust 数据构建与切片`
2. `py_entry/runner/setup_utils.py`
3. 取数相关 Python 入口

阶段约束：

1. 非 base source 的时间投影统一调用：
   - `exact_index_by_time(...)`
   - `map_source_row_by_time(...)`
   - `map_source_end_by_base_end(...)`
2. planner 初始化必须显式走共享 helper 链，并显式合并：
   - `resolve_contract_warmup_by_key(...)`
   - `normalize_contract_warmup_by_key(...)`
   - `resolve_backtest_exec_warmup_base(backtest_params)`
   - `merge_required_warmup_by_key(...)`
3. `required_warmup_by_key` 只表示 planner 与 WF 共享的基础 warmup 下界；它不覆盖 WF-local 的 `min_warmup_bars`。
4. `DataPackFetchPlannerInput` 必须正式携带 `backtest_params`。
5. `resolve_backtest_exec_warmup_base(...)` 必须在 helper 内部统一解析会影响 warmup 的 `Param.value / Param.max` 真值，不允许 Python 或 planner 先手工物化第二套 concrete runtime params。
6. `DataPackFetchPlannerInput.effective_limit` 必须满足 `>= 1`，`effective_limit = 0` 直接 fail-fast。

阶段验收：

1. 先跑 `just check`
2. 再跑：
   - `just test-py path="py_entry/Test/backtest/test_data_fetch_planner_contract.py"`
3. 若该测试尚未落地，至少完成一次审阅：
   - 对照摘要 `01 / 02`
   - 检查 `DataPackFetchPlannerInput` 是否已补 `backtest_params`
   - 检查 `required_warmup_by_key` 是否已取代旧 `W_normalized` 落点

### 阶段 C：单次回测、`build_result_pack(...)` 与 `extract_active(...)`

阶段目标：

1. 单次回测全链路改成新 `DataPack / ResultPack`。
2. `extract_active(...)` 改成正式工具函数。
3. 清掉 `has_leading_nan` 在回测核心链上的旧作用。

关键落点：

1. `3.3 Rust 回测主流程`
2. `3.2 Rust 数据构建与切片` 中的 `extract_active(...)`

阶段约束：

1. 信号模块内部处理预热禁开仓。
2. 绩效模块内部处理非预热切片。
3. `extract_active(...)` 不调用 builder，只做字段切片、mapping 重基、`ranges` 归零、`performance` 继承。
4. `has_leading_nan` 只保留在 `signals`，除 `signals` 外其他模块都不应再感知或消费它。

阶段验收：

1. 先跑 `just check`
2. 再跑：
   - `just test-py path="py_entry/Test/backtest/test_extract_active_contract.py"`
   - `just test-py path="py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py"`
3. 若 `extract_active(...)` 专项测试尚未落地，至少完成一次审阅：
   - 对照摘要 `03`
   - 明确确认 `extract_active(...)` 没有误走 builder
   - 明确确认 `has_leading_nan` 已从 `backtest / performance` 链移除

### 阶段 D：WF 主流程、窗口索引、跨窗注入与 stitched 上游输入

阶段目标：

1. 落地 `build_window_indices(...)`、窗口切片、跨窗注入与窗口主循环。
2. 只把 stitched replay 上游输入构造完整，不在本阶段落地 replay kernel。

关键落点：

1. `3.4 Rust WF 与 stitched`

阶段约束：

1. `step = test_active_bars` 写死。
2. `build_window_indices(...)` 是唯一窗口索引入口；它的正式产物是 `WalkForwardPlan`；`required_warmup_by_key` 是它的正式 warmup 输入，`min_warmup_bars` 仍是 WF-local constraint。
3. `ignore_indicator_warmup = true` 只允许通过 `apply_wf_warmup_policy(...)` 把指标契约 warmup 截获为 `0`；`backtest_exec_warmup_base` 不受影响。
4. `wf_params.backtest` 仍然只是参数容器，不是已物化 concrete runtime params；`resolve_backtest_exec_warmup_base(...)` 必须在 helper 内部统一按 `Param.value / Param.max` 解析。
5. `best_params` 的冻结语义唯一落点是 `src/backtest_engine/optimizer/runner/rebuild.rs`：
   - 仍然返回 `SingleParamSet`
   - 保留原始参数树形状与 `min / max / step / optimize`
   - 只把最优解写回各叶子 `.value`
   - 不允许在 WF / stitched 层再做第二次 canonicalize
6. `WalkForwardPlan` 只负责窗口规划真值：
   - `required_warmup_by_key`
   - `windows: Vec<WindowPlan>`
   - 不负责 `best_params`、窗口执行结果或 stitched replay 输入
7. `build_window_indices(...)` 必须显式产出 `test_active_base_row_range`；它只保留在 `WindowIndices` 里，不再额外挂第二份同义字段；虽然它会通过 `WindowMeta` 对外暴露，但语义上只供 stitched `backtest_schedule` 内部重基使用。
8. 窗口主循环只消费 `wf_plan.windows`，不允许在执行阶段重新推导第二套窗口几何真值。
9. 窗口测试执行固定三段：
   - `raw_signal_stage_result`
   - `natural_test_pack_backtest_result`
   - `final_test_pack_result`
10. `run_walk_forward(...)` 必须显式忽略 `settings.execution_stage` 与 `settings.return_only_final`；这两个字段属于单次回测阶段返回控制，不允许在 WF 内继续透传。
11. `final_test_pack_result` 才是窗口正式结果；`natural_test_pack_backtest_result` 只用于跨窗 carry 与边界判断，不进入正式返回值，不进入 stitched，不参与正式 performance。
12. `detect_last_bar_position(...)` 只从 `natural_test_pack_backtest_result.backtest` 读取。
13. `04` 的 stitched 末段只负责构造 `StitchedReplayInput`：
   - `stitched_data`
   - `stitched_signals`
   - `backtest_schedule: Vec<BacktestParamSegment>`
   - `stitched_atr_by_row`
   - `stitched_indicators_with_time`
   - replay 直接消费：
     - `stitched_data`
     - `stitched_signals`
     - `backtest_schedule`
     - `stitched_atr_by_row`
   - 最终 `stitched_result` 构建阶段再消费：
     - `stitched_indicators_with_time`
   - 这些对象在阶段 D 只作为 replay 上游输入存在，不在本阶段回填最终 `stitched_result`
   - 这里的 `stitched_signals` 必须直接来自各窗口 `test_active_result.signals`
   - 不允许再回退去拼完整 `final_signals`
   - 当前正式语义接受这条保守约束：
     - carry 开仓写在 active 第一根
     - 真正继承开仓在第二根 active bar 开盘执行
14. `backtest_schedule` 只允许读取各窗口 `window_results[i].meta.test_active_base_row_range`，再以第一窗 `start` 做减法重基；不允许按 `cursor += active_rows` 第二次规划。
15. `stitched_atr_by_row` 必须按唯一算法落地：
   - 先按 unique `resolved_atr_period` 计算 stitched base 全量 ATR cache
   - 再按 `backtest_schedule` 做 segment 级 `slice + concat`
   - 不允许按 row 逐行现算，也不允许先按窗口各算一条 ATR 再二次拼接
16. `run_optimization(...)` 的搜索空间来源与优化目标来源都必须唯一：
   - 搜索空间只读取 `run_walk_forward(...)` 输入的 `wf_params`
   - 优化目标只读取 `config.optimize_metric`
   - 不允许在 `template / settings` 或其他入口再派生第二套搜索域或第二套优化目标

阶段验收：

1. 先跑 `just check`
2. 再跑：
   - `just test-py path="py_entry/Test/walk_forward/test_window_indices_contract.py"`
   - `just test-py path="py_entry/Test/walk_forward/test_window_slice_contract.py"`
   - `just test-py path="py_entry/Test/walk_forward/test_wf_signal_injection_contract.py"`
3. 若 `stitched` 上游 contract 测试已落地，再追加：
   - `just test-py path="py_entry/Test/walk_forward/test_stitched_contract.py"`
4. 若阶段测试未全部具备，至少完成一次审阅：
   - 对照摘要 `04`
   - 明确确认 `test_active_base_row_range` 已透传
   - 明确确认 `best_params` 只按 `.value` 消费
   - 明确确认 `backtest_schedule` 与 `stitched_atr_by_row` 的算法落点已唯一
   - 明确确认阶段 D 只构造 replay 上游输入，不回填最终 `stitched_result.meta`

### 阶段 E：segmented replay、统一 kernel、Python 包装层与最终回归

阶段目标：

1. 落地 `run_backtest_with_schedule(...)`、统一 kernel、单次退化成单段 schedule。
2. 完成最终 stitched replay、`build_result_pack(...)` 回收与 Python 包装层对齐。
3. 补齐 Rust 等价性测试和完整回归。

关键落点：

1. `3.5 Rust segmented replay / kernel`
2. `3.6 Python 包装层`

阶段约束：

1. `run_backtest(...)` 必须在内部先构造单段 `schedule`，再直接调用 `run_backtest_with_schedule(...)`。
2. `ParamsSelector` 只保留单一路径：`schedule + segment_idx`。
3. multi-segment output schema 必须作为独立 contract 落地：
   - 并集列集合
   - 稳定列顺序
   - 稳定 dtype
   - 未启用 segment 的非激活态默认值
   - 单段 schedule 退化成当前固定 schema
4. 最终 stitched `ResultPack` 必须统一走：
   - `strip_indicator_time_columns(...)`
   - `build_result_pack(...)`
   不允许引入 stitched builder 特例，也不再保留 `stitched_result_pre_capital + capital rebuild` 旧路线。
5. `stitched_result.meta.backtest_schedule` 在本阶段回填：
   - 直接复用 replay 实际使用的那一份 `backtest_schedule`
   - 不允许 replay 后再反推或重建
6. Python 包装层必须显式对齐 `stitched_result.meta.backtest_schedule`。
7. Rust 等价性测试基线固定为：
   - 先在旧 `run_backtest(...)` 上清掉 `has_leading_nan` 旧作用链
   - 再冻结成 `legacy_run_backtest_reference(...)`
   - 最后与新的 `run_backtest(...)` 做严格逐项对比
8. 多窗口 stitched carry 语义必须作为独立 contract 落地：
   - stitched replay 不能只验证 `backtest_schedule / stitched_atr_by_row / schema`
   - 必须显式验证后一窗起点的 carry 语义仍与当前正式 WF 语义一致
   - 当前正式语义固定为：carry 信号位于 active 第一根，真正继承开仓在第二根 active bar 开盘执行

阶段验收：

1. 先跑 `just check`
2. 再跑：
   - `just test-rust`
   - `just test-py path="py_entry/Test/walk_forward/test_stitched_contract.py"`
   - `just test-py path="py_entry/Test/walk_forward/test_walk_forward_guards.py"`
3. 上述 stitched 测试里必须实际覆盖：
   - 多窗口 stitched carry contract
   - 不能只覆盖 `backtest_schedule / ATR / schema`
4. 阶段 E 完成后，再跑最终总验收：
   - `just check`
   - `just test`

## 5. 关键实现片段

这里只保留必须落地的代码骨架。

### 5.1 `SourceRange`

```rust
struct SourceRange {
    warmup_bars: usize,
    active_bars: usize,
    pack_bars: usize,
}
```

强约束：

1. `warmup_bars + active_bars == pack_bars`
2. `0 <= warmup_bars <= pack_bars`
3. `0 <= active_bars <= pack_bars`
4. 这里只写 `SourceRange` 自身的通用结构约束，不把具体场景里的更强限制混进来
5. 例如：
   - `pack_bars > 0`
   - `active_bars > 0`
   - `test_active >= 3`
   这些都应分别放在 `DataPack / ResultPack`、WF 窗口合法性和 stitched / hint 专项约束里，不属于 `SourceRange` 的通用定义
6. `warmup_bars` 允许为 `0`

### 5.2 `WalkForwardPlan / WindowPlan / WindowIndices`

```rust
struct WindowPlan {
    window_idx: usize,
    indices: WindowIndices,
}

struct WalkForwardPlan {
    required_warmup_by_key: HashMap<String, usize>,
    windows: Vec<WindowPlan>,
}

struct WindowSliceIndices {
    source_ranges: HashMap<String, Range<usize>>,
    ranges_draft: HashMap<String, SourceRange>,
}

struct WindowIndices {
    train_pack: WindowSliceIndices,
    test_pack: WindowSliceIndices,
    test_active_base_row_range: Range<usize>,
}
```

强约束：

1. `WalkForwardPlan` 只承接窗口规划真值：
   - `required_warmup_by_key`
   - `windows`
2. `WindowPlan` 只负责把 `window_idx` 和 `WindowIndices` 绑定起来，不新增第二份窗口几何真值。
3. `source_ranges` 指向 WF 输入 `DataPack.source` 的局部行号区间。
4. `ranges_draft` 只描述新窗口 `DataPack` 的 `ranges`。
5. `source_ranges` 必须包含 `data.base_data_key`。
6. `ranges_draft` 不能用于切旧容器。
7. `test_active_base_row_range` 指向原始 WF 输入 `DataPack.base` 轴上的绝对半开区间。
8. 虽然它会通过 `WindowMeta` 对外暴露，但语义上只供 stitched `backtest_schedule` 内部重基使用，不应被理解成通用业务元数据。

### 5.3 `BacktestParamSegment` 与 `StitchedReplayInput`

```rust
struct BacktestParamSegment {
    start_row: usize,
    end_row: usize,
    params: BacktestParams,
}

struct StitchedReplayInput {
    stitched_data: DataPack,
    stitched_signals: DataFrame,
    backtest_schedule: Vec<BacktestParamSegment>,
    stitched_atr_by_row: Option<Series>,
    stitched_indicators_with_time: HashMap<String, DataFrame>,
}
```

强约束：

1. `04` 最终交给 `05` 的 stitched replay 输入固定收敛为 `StitchedReplayInput`。
2. `StitchedReplayInput` 只收纳 stitched 阶段已经生成的正式输入真值，不新增第二套 replay 解释层。
3. replay 直接消费：
   - `stitched_data`
   - `stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
4. 最终 `stitched_result` 构建阶段再消费：
   - `stitched_indicators_with_time`
5. `backtest_schedule` 的每段 `start_row / end_row` 必须只从各窗口 `test_active_base_row_range` 做减法重基得到：
   - `base0 = window_results[0].meta.test_active_base_row_range.start`
   - `start_row_i = original_start_i - base0`
   - `end_row_i = original_end_i - base0`
6. 不允许在 stitched 阶段按 `cursor += active_rows` 第二次规划 schedule。
7. segmented replay 完成后，最终 stitched `ResultPack` 仍然统一走 `build_result_pack(...)`。
8. stitched 阶段先拼出来的 `stitched_indicators_with_time` 属于结果态 indicators，带 `time` 列。
9. 因此在最终生成 stitched `ResultPack` 前，必须先统一调用：
   - `stitched_raw_indicators = strip_indicator_time_columns(stitched_indicators_with_time)`
10. 再基于 segmented replay 产出的 `stitched_backtest_truth` 计算 `stitched_performance`。
11. 最后统一调用 `build_result_pack(...)`：
   - `data = stitched_data`
   - `indicators = stitched_raw_indicators`
   - `signals = stitched_signals`
   - `backtest = stitched_backtest_truth`
   - `performance = stitched_performance`
12. 不允许把带 `time` 的 `stitched_indicators_with_time` 直接回灌到 `build_result_pack(...)`。
13. 不允许绕过 `build_result_pack(...)` 直接手写最终 stitched `ResultPack`。

## 6. 删除项与不保留兼容层

必须直接删，不保留兼容：

1. 旧 `transition_*` 字段与语义。
2. 旧 `WindowSpec { train_range, transition_range, test_range }` 体系。
3. 旧 `walk_forward` 输出结构。
4. 旧的 stitched 拼接逻辑里直接依赖窗口完整结果切片的写法。
5. Python 侧对旧字段的兼容读取。
6. 任何“如果新字段不存在则退回旧字段”的回退逻辑。

## 7. 阶段与测试计划映射

本节只回答一件事：每个执行阶段应当对应 `02_test_plan.md` 的哪一层测试。

### 7.1 阶段 A

对应 `02_test_plan.md`：

1. `4.1 第一层：Builder / 容器不变量测试`

### 7.2 阶段 B

对应 `02_test_plan.md`：

1. `4.1.1 第一层补充：DataPackFetchPlanner 状态机 contract`

### 7.3 阶段 C

对应 `02_test_plan.md`：

1. `4.2 第二层：extract_active(...) 专项测试`
2. 必要时补跑现有单次回测回归测试，防止 builder / backtest 主流程一起漂移

### 7.4 阶段 D

对应 `02_test_plan.md`：

1. `4.3 第三层：WF 窗口规划与切片测试`
2. `4.4 第四层：WF 跨窗注入测试`
3. `4.5 第五层` 中与 stitched replay 上游输入直接相关的 contract 测试

### 7.5 阶段 E

对应 `02_test_plan.md`：

1. `4.5 第五层：stitched / segmented replay 专项测试`
2. `4.6 第六层：少量完整 WF 回归`

## 8. 阶段验收总规则

1. 阶段未通过验收，不得进入下一阶段。
2. 每个阶段的验收顺序固定为：
   - 先 `just check`
   - 再跑该阶段的最小测试
   - 若该阶段测试尚未落地，则做审阅验收
   - 最后回填 `## 10` 的阶段完成记录
3. 审阅验收不是永久替代项：
   - 若某阶段先用审阅临时放行，必须在后续补测后再回填同一条记录
4. 阶段 E 完成后，才允许跑最终总验收：
   - `just check`
   - `just test`
5. 不要一边改一边跑 `just check`；每个阶段内部先完成逻辑修改，再统一验收。

## 9. 执行前审阅检查项

本节只列执行前审阅时必须覆盖的检查项，不记录“是否审阅通过”的状态结论；执行文档只记录代码落地与阶段回补。

执行前审阅应至少覆盖：

1. 是否仍有旧 `SourceRange { warmup, total }` 残留。
2. 是否仍有旧 `transition_*` 字段残留。
3. `build_result_pack(...)` 是否误调用 `build_mapping_frame(...)`。
4. `extract_active(...)` 是否仍误走 builder。
5. `run_backtest(...)` 是否已经内部退化成单段 `schedule`，再直接调用 `run_backtest_with_schedule(...)`。
6. `legacy_run_backtest_reference(...)` 是否是在清掉 `has_leading_nan` 旧作用链之后再冻结。
7. stitched 是否仍试图走旧的 `stitched_result_pre_capital + capital rebuild` 路线。
8. `build_window_indices(...)` 是否已经显式产出并透传 `test_active_base_row_range`。
9. `backtest_schedule` 是否只由 `test_active_base_row_range` 做减法重基得到，而不是重新按 `cursor += active_rows` 规划。
10. `walk_forward` 主循环是否已闭环：
   - `window_results.push(...)`
   - `prev_last_bar_position` 回写
   - `has_cross_boundary_position` 回写
11. 是否已经显式区分：
   - `raw_signal_stage_result`
   - `carry_only_signals`
   - `natural_test_pack_backtest_result`
   - `final_signals`
   - `final_test_pack_result`
12. `detect_last_bar_position(...)` 是否只从 `natural_test_pack_backtest_result.backtest` 读取，而不是误从正式强平后的 `final_test_pack_result.backtest` 读取。
13. 最终 stitched `ResultPack` 是否仍然统一走：
    - `strip_indicator_time_columns(...)`
    - `build_result_pack(...)`
    而不是绕过 builder 直接手写结果。

## 10. 阶段完成回补记录

每个阶段完成后，直接回填对应小节；不要等到全部结束再统一补。
本节只记录代码落地、验收命令、验收结果与剩余风险，不记录审阅通过状态。

### 10.1 阶段 A 完成记录

1. 状态：`未开始 / 进行中 / 已完成`
2. 实际修改文件：
3. 实际验收命令：
4. 验收结果：
5. 若未跑测试，审阅结论：
6. 剩余风险 / 待后续：

### 10.2 阶段 B 完成记录

1. 状态：`未开始 / 进行中 / 已完成`
2. 实际修改文件：
3. 实际验收命令：
4. 验收结果：
5. 若未跑测试，审阅结论：
6. 剩余风险 / 待后续：

### 10.3 阶段 C 完成记录

1. 状态：`未开始 / 进行中 / 已完成`
2. 实际修改文件：
3. 实际验收命令：
4. 验收结果：
5. 若未跑测试，审阅结论：
6. 剩余风险 / 待后续：

### 10.4 阶段 D 完成记录

1. 状态：`未开始 / 进行中 / 已完成`
2. 实际修改文件：
3. 实际验收命令：
4. 验收结果：
5. 若未跑测试，审阅结论：
6. 剩余风险 / 待后续：

### 10.5 阶段 E 完成记录

1. 状态：`未开始 / 进行中 / 已完成`
2. 实际修改文件：
3. 实际验收命令：
4. 验收结果：
5. 若未跑测试，审阅结论：
6. 剩余风险 / 待后续：

### 10.6 最终总验收记录

1. 实际修改文件汇总：
2. 删除的旧接口 / 旧字段：
3. 新增测试列表：
4. `just check` 结果：
5. `just test` 结果：
6. 未完成项与阻塞项：
