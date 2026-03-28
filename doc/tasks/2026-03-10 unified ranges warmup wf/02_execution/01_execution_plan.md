# 统一 Ranges / Warmup / WF 重构执行文档

对应摘要：

1. [../01_summary/task_summary.md](../01_summary/task_summary.md)
2. [../01_summary/01_overview_and_foundation.md](../01_summary/01_overview_and_foundation.md)
3. [../01_summary/02_python_fetch_and_initial_build.md](../01_summary/02_python_fetch_and_initial_build.md)
4. [../01_summary/03_backtest_and_result_pack.md](../01_summary/03_backtest_and_result_pack.md)
5. [../01_summary/04_walk_forward_and_stitched.md](../01_summary/04_walk_forward_and_stitched.md)
6. [02_test_plan.md](./02_test_plan.md)

本文只保留执行所需内容：

1. 实施顺序
2. 关键接口
3. 文件修改清单
4. 破坏性更新与删除项
5. 测试与验收

不再重复摘要文档里的方案解释。

## 0. 摘要归属与落地引用

执行时统一按“摘要归属文档 -> 实现落点”的方式理解，不在执行文档里复制第二套解释。

| 摘要归属 | 本次在实现里主要落到哪里 | 执行文档只关心什么 |
|---|---|---|
| `01_overview_and_foundation.md` | `src/types/*`、`src/backtest_engine/data_ops/mod.rs` | 类型、builder、共享真值入口与通用约束 |
| `02_python_fetch_and_initial_build.md` | `src/backtest_engine/data_ops/mod.rs`、`py_entry/runner/setup_utils.py`、取数相关 Python 入口 | planner 状态机、Python/Rust 职责边界、取数对接 |
| `03_backtest_and_result_pack.md` | `src/backtest_engine/top_level_api.rs`、`src/backtest_engine/utils/context.rs`、`src/backtest_engine/performance_analyzer/mod.rs`、`src/backtest_engine/data_ops/mod.rs` | 单次回测主流程、`build_result_pack(...)`、`extract_active(...)` |
| `04_walk_forward_and_stitched.md` | `src/backtest_engine/walk_forward/*` | `build_window_indices(...)`、窗口主循环、stitched、`NextWindowHint` |

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
4. 落地 `slice_data_pack_by_base_window(...)`。
5. 落地 `extract_active(...)`。
6. 落地 stitched 拼接与资金列重建辅助函数。
7. 把共享 warmup helper 正式收口到唯一实现源头：
   - `resolve_contract_warmup_by_key(...)`
   - `normalize_contract_warmup_by_key(...)`
   - `apply_wf_warmup_policy(...)`
   其中 `resolve_contract_warmup_by_key(...)` 必须只是 `resolve_indicator_contracts(...).warmup_bars_by_source` 的薄封装，不允许再写第二套聚合逻辑。

### 3.3 Rust 回测主流程

必须修改：

1. `src/backtest_engine/top_level_api.rs`
2. `src/backtest_engine/utils/context.rs`
3. `src/backtest_engine/performance_analyzer/mod.rs`

主要任务：

1. 让单次回测主流程统一吃 `DataPack`。
2. 让 `build_result_pack(...)` 成为正式结果构建入口。
3. 让绩效模块内部按 `data.ranges[data.base_data_key].warmup_bars` 自己切非预热段。
4. 让 `execute_single_backtest(...)` 与 `BacktestContext` 返回新 `ResultPack`。

### 3.4 Rust WF 与 stitched

必须修改：

1. `src/backtest_engine/walk_forward/data_splitter.rs`
2. `src/backtest_engine/walk_forward/runner.rs`
3. `src/backtest_engine/walk_forward/mod.rs`

主要任务：

1. 用新窗口索引工具函数替换旧 `generate_windows(...)` 逻辑。
2. 落地 `build_window_indices(...)` 及其 3 个私有步骤。
3. 落地跨窗注入。
4. 落地窗口主循环。
5. 落地 stitched。
6. 落地 `NextWindowHint` 新算法。

### 3.5 Python 包装层

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

### 3.6 测试

重点修改或新增：

1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
2. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
3. `py_entry/Test/walk_forward/test_walk_forward_guards.py`
4. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`
5. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
6. 新增与 `extract_active(...)`、stitched、`NextWindowHint` 相关测试

## 4. 实施顺序

必须按顺序执行，不要并行改大块逻辑。

### 阶段 A：先统一类型与 builder 真值

目标：

1. 先把 `DataPack / ResultPack / SourceRange` 定义立住。
2. 先把 `build_mapping_frame(...) / build_data_pack(...) / build_result_pack(...)` 立住。
3. 先把 “哪些地方必须走 builder，哪些地方允许例外” 写进代码结构。

关键约束：

1. `build_mapping_frame(...)` 在生产链路里只由 `build_data_pack(...)` 调用；但可以保留 PyO3 暴露，作为测试 / 调试工具函数。
2. `build_result_pack(...)` 绝不调用 `build_mapping_frame(...)`。
3. `build_result_pack(...)` 只继承 `data.mapping` 子集。
4. `extract_active(...)` 是唯一不走 builder 的显式特例。

关键接口：

```rust
fn build_mapping_frame(
    source: &HashMap<String, DataFrame>,
    base_data_key: &str,
) -> Result<DataFrame, QuantError>

fn build_data_pack(
    source: HashMap<String, DataFrame>,
    base_data_key: String,
    ranges: HashMap<String, SourceRange>,
    skip_mask: Option<DataFrame>,
) -> Result<DataPack, QuantError>

fn build_result_pack(
    data: &DataPack,
    indicators: Option<HashMap<String, DataFrame>>,
    signals: Option<DataFrame>,
    backtest: Option<DataFrame>,
    performance: Option<HashMap<String, f64>>,
) -> Result<ResultPack, QuantError>
```

这里顺手把 `ResultPack` 的 base 身份写死：

1. `ResultPack` 必须显式携带 `base_data_key: String`。
2. `build_result_pack(...)` 不允许外部额外传这个字段，而是直接从 `data.base_data_key` 复制。
3. 后续凡是 helper 只接收 `&ResultPack`，但又需要读取 base 语义时，都统一走：
   - `result.base_data_key`
   - `result.ranges[result.base_data_key]`
4. 不再依赖“外层上下文总能拿到 base key”这种隐含前提。
5. 若 `indicators[k]` 存在，`build_result_pack(...)` 必须统一为其补入 `time` 列，而不是要求指标模块自己携带：
   - 若上游 `indicators[k]` 已经包含同名 `time` 列，直接报错，不做覆盖
   - 先校验 `indicators[k].height() == data.source[k].height()`
   - 再把 `data.source[k]["time"]` 复制进 `indicators[k]`
   - 最后校验补入后的 `indicators[k]["time"] == data.source[k]["time"]`
6. 因此 `ResultPack.indicators[k]` 的正式契约是“带 `time` 列的指标结果 DF”。

### 阶段 B：再落地初始取数与 `DataPack` 初始构建

目标：

1. Python 只保留网络请求。
2. Rust 统一做 warmup 聚合、首尾覆盖、初始 `ranges` 计算、`build_data_pack(...)`。

关键约束：

1. 非 base source 的时间投影统一调用：
   - `exact_index_by_time(...)`
   - `map_source_row_by_time(...)`
   - `map_source_end_by_base_end(...)`
2. `resolve_indicator_contracts(...)` 的正式公式与边界统一以摘要 `01_overview_and_foundation.md#2.2` 为准；执行时不再在 planner / WF 内各写一套聚合逻辑。
3. `resolve_contract_warmup_by_key(...)` 必须直接调用 `resolve_indicator_contracts(...)` 并提取 `warmup_bars_by_source`，不允许平行实现第二套聚合逻辑。
4. planner 初始化时，必须显式走同一条共享 helper 链：
   - `resolved_contract_warmup_by_key = resolve_contract_warmup_by_key(indicators_params)`
   - `normalized_contract_warmup_by_key = normalize_contract_warmup_by_key(S_keys, resolved_contract_warmup_by_key)`
5. 初始取数 planner 与 WF `build_window_indices(...)` 必须复用同一份 warmup 聚合口径，禁止各自单独再算一套。
6. 不允许在多个模块里各自重写一套 backward asof 逻辑。
7. `DataPackFetchPlannerInput.effective_limit` 必须满足 `>= 1`：
   - 因为初始取数算法后续要直接定义 `base_effective_start_time / base_first_live_time`
   - 这要求 base 至少有 `1` 根 live bar
   - 因此 `effective_limit = 0` 必须在 planner 输入阶段直接 fail-fast 报错

关键落点：

1. `src/backtest_engine/data_ops/mod.rs`
2. `py_entry/runner/setup_utils.py`
3. 与 build data 相关的 Python 入口

现有实现对接迁移：

1. 当前 Python 侧已有的 `OhlcvDataFetchConfig` 与 `OhlcvRequestParams` 继续保留：
   - `OhlcvDataFetchConfig` 继续作为用户层配置对象
   - `OhlcvRequestParams` 继续作为现有网络请求对象
2. 本次迁移不重写 Python 网络请求层，只替换“取多少、何时补拉、何时完成”的规划逻辑：
   - Python 不再自己计算 warmup、首尾覆盖、补拉轮次
   - Rust `DataPackFetchPlanner` 成为唯一状态机
3. 迁移后的调用顺序写死为：
   - Python 从 `OhlcvDataFetchConfig` 抽取 planner 真正需要的字段，构造 `DataPackFetchPlannerInput`
   - Rust 创建 `DataPackFetchPlanner`
   - Python 循环调用 `next_request()`
   - Python 用 `FetchRequest + OhlcvDataFetchConfig` 组装现有 `OhlcvRequestParams`
   - Python 继续调用现有 `get_ohlcv_data(...)`
   - 若响应为空，Python 侧最多重试 `2` 次；重试后仍为空则直接报错
   - 只有拿到非空 `pl.DataFrame` 后，才调用 Rust `ingest_response(...)`
   - Rust 状态机内部继续推进 `ensure_tail_coverage(...) / ensure_head_time_coverage(...) / ensure_head_warmup_bars(...)`
   - 直到 `is_complete() == true` 后，由 Rust `finish()` 一次性返回 `DataPack`
4. 因此本次迁移的真正替换点是：
   - 保留 Python 请求适配层
   - 删除 Python 侧原有的 warmup / 覆盖 / 补拉算法状态
   - 把这些状态统一下沉到 Rust planner
5. 若后续排查问题，职责边界也必须按这条链理解：
   - Python 只负责请求编排、空响应重试、`DataFrame` 回传
   - Rust 负责非空快照校验、状态推进、最终 `DataPack` 构建

### 阶段 C：落地单次回测与 `extract_active(...)`

目标：

1. 单次回测全链路改成新 `DataPack / ResultPack`。
2. `extract_active(...)` 改成正式工具函数。

关键约束：

1. 信号模块内部处理预热禁开仓。
2. 绩效模块内部处理非预热切片。
3. `extract_active(...)` 不调用 builder。
4. `extract_active(...)` 只做：
   - 字段切片
   - mapping 重基
   - `ranges` 归零
   - `performance` 继承

关键接口：

```rust
fn extract_active(
    data: &DataPack,
    result: &ResultPack,
) -> Result<(DataPack, ResultPack), QuantError>
```

### 阶段 D：最后落地 WF 与 stitched

目标：

1. 把最复杂的窗口规划、跨窗注入、stitched 放到最后。
2. 此时前面的基础容器、builder、回测主流程必须已稳定。

关键约束：

1. `step = test_active_bars` 写死。
2. `build_window_indices(...)` 是唯一窗口索引入口。
3. `WfWarmupMode` 只保留 `BorrowFromTrain | ExtendTest`。
4. `min_warmup_bars` 默认值必须是 `0`；只有调用方显式提高时，才作为 WF 的额外预热下界参与窗口规划。
5. `ignore_indicator_warmup` 默认值必须是 `false`；仅用于“有预热 vs 无预热”的对照实验与备胎方案。
6. WF 初始化时，必须显式走同一条共享 helper 链：
   - `resolved_contract_warmup_by_key = resolve_contract_warmup_by_key(wf_params.indicators)`
   - `normalized_contract_warmup_by_key = normalize_contract_warmup_by_key(S_keys, resolved_contract_warmup_by_key)`
   - `applied_contract_warmup_by_key = apply_wf_warmup_policy(normalized_contract_warmup_by_key, config.ignore_indicator_warmup)`
7. 因此 `ignore_indicator_warmup = true` 时，只允许通过 `apply_wf_warmup_policy(...)` 把聚合预热需求截获为 `0`，其余 WF 算法不新增平行分支。
8. 窗口测试执行固定三段：
   - 第一次跑到 `Signals`，得到 `raw_signal_stage_result`
   - 第二次只用 `carry_only_signals` 跑到 `Backtest`，得到 `natural_test_pack_backtest_result`
   - 第三次用 `final_signals` 跑到 `Performance`，得到 `final_test_pack_result`
9. `run_walk_forward(...)` 明确忽略 `settings.execution_stage` 与 `settings.return_only_final`：
   - 这两个字段属于单次回测引擎的阶段返回控制
   - 在 WF 内部必须由当前阶段自己覆盖
   - 其余通用执行设置才继续继承
10. WF 必须显式遵守摘要里的 `ResultPack` 阶段产出契约表：
   - `raw_signal_stage_result`：至少产出 `indicators + signals`
   - `natural_test_pack_backtest_result`：至少产出 `backtest`
   - `final_test_pack_result`：必须产出完整 `indicators + signals + backtest + performance`
   - `stitched_result_pre_capital`：必须产出 `indicators + signals + backtest`
   - `stitched_result`：必须产出完整 `indicators + signals + backtest + performance`
11. `detect_last_bar_position(...)` 只从 `natural_test_pack_backtest_result.backtest` 读取：
   - 既用于 `prev_last_bar_position` 回写
   - 也用于 `has_cross_boundary_position`
12. `final_test_pack_result` 才是窗口正式结果；`natural_test_pack_backtest_result` 不进入正式返回值，不进入 stitched，不参与正式 performance。
13. stitched 的 `DataPack` 真值来自 `full_data` 切片，不来自窗口 `DataPack` 拼接。
14. stitched 只拼 `test_active_result`，不拼完整 `test_pack_result`。
15. `run_optimization(...)` 的搜索空间来源必须唯一：
   - 直接读取 `run_walk_forward(...)` 输入的 `wf_params: &SingleParamSet`
   - `template / settings` 不得再派生第二套优化域
16. `run_optimization(...)` 的优化目标来源也必须唯一：
   - 直接读取 `config.optimize_metric`
   - 默认值固定为 `OptimizeMetric::CalmarRatioRaw`
   - `template / settings` 不得再派生第二套优化目标
17. 这里的类型层级必须理解成：
   - `SingleParamSet`：整棵参数树
   - `Param`：参数树里的单个叶子参数节点
   因此 `SingleParamSet` 虽然名字像“单组参数”，但仍可同时承载固定参数与优化搜索空间。
18. WF 的 warmup helper 对象来源固定为 `wf_params.indicators`。
   - 这里的 `wf_params.indicators` 指 `run_walk_forward(...)` 输入参数树中的指标参数子树
   - 它是当前实现唯一合法的指标参数读取入口
   - 任何 WF 内部涉及指标契约 warmup 的读取，只要没有走这条路径，就视为实现偏离摘要契约
   - 这条路径已与当前 `SingleParamSet` 源码结构对齐，不是执行层临时发明的 extractor 约定

关键接口：

```rust
fn build_window_indices(
    data: &DataPack,
    config: &WalkForwardConfig,
    applied_contract_warmup_by_key: &HashMap<String, usize>,
) -> Result<Vec<WindowIndices>, QuantError>

fn slice_data_pack_by_base_window(
    data: &DataPack,
    indices: &WindowSliceIndices,
) -> Result<DataPack, QuantError>

fn detect_last_bar_position(
    backtest: &DataFrame,
) -> Result<Option<CrossSide>, QuantError>

fn build_carry_only_signals(
    raw_signal_stage_result: &ResultPack,
    prev_last_bar_position: Option<CrossSide>,
) -> Result<DataFrame, QuantError>

fn build_final_signals(
    raw_signal_stage_result: &ResultPack,
    carry_only_signals: &DataFrame,
) -> Result<DataFrame, QuantError>
```

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
   - `test_active >= 2`
   这些都应分别放在 `DataPack / ResultPack`、WF 窗口合法性和 stitched / hint 专项约束里，不属于 `SourceRange` 的通用定义
6. `warmup_bars` 允许为 `0`

### 5.2 `WindowSliceIndices`

```rust
struct WindowSliceIndices {
    source_ranges: HashMap<String, Range<usize>>,
    ranges_draft: HashMap<String, SourceRange>,
}
```

强约束：

1. `source_ranges` 指向 WF 输入 `DataPack.source` 的局部行号区间。
2. `ranges_draft` 只描述新窗口 `DataPack` 的 `ranges`。
3. `source_ranges` 必须包含 `data.base_data_key`。
4. `ranges_draft` 不能用于切旧容器。

### 5.3 stitched 中间态

```rust
struct StitchedResultDraft {
    indicators: HashMap<String, DataFrame>,
    signals: DataFrame,
    backtest: DataFrame,
}
```

强约束：

1. `StitchedResultDraft` 不持有 `mapping`。
2. stitched 最终 `mapping` 真值来自 `stitched_data.mapping`。
3. 先用 `StitchedResultDraft` 构建一个仅用于校验的 `stitched_result_pre_capital`。
4. 对 `stitched_result_pre_capital` 做一致性校验。
5. 再基于 `stitched_result_pre_capital.backtest` 重建出 `rebuilt_stitched_backtest`。
6. 再基于 `rebuilt_stitched_backtest` 计算 `stitched_performance`。
7. 最后再一次性构建最终 `stitched_result`：
   - `backtest = rebuilt_stitched_backtest`
   - `performance = stitched_performance`
8. 不允许出现“先构建最终 stitched_result，再替换其 backtest / performance 字段”的实现。

## 6. 删除项与不保留兼容层

必须直接删，不保留兼容：

1. 旧 `transition_*` 字段与语义。
2. 旧 `WindowSpec { train_range, transition_range, test_range }` 体系。
3. 旧 `walk_forward` 输出结构。
4. 旧的 stitched 拼接逻辑里直接依赖窗口完整结果切片的写法。
5. Python 侧对旧字段的兼容读取。
6. 任何“如果新字段不存在则退回旧字段”的回退逻辑。

## 7. 测试计划

### 7.1 基础不变量测试

1. `build_data_pack(...)`：
   - `mapping.time` 必须严格递增
   - `mapping.height() == source[base].height()`
   - `ranges[base].pack_bars == mapping.height()`
2. `build_result_pack(...)`：
   - `result.mapping.time == data.mapping.time`
   - `result.mapping[k] == data.mapping[k]`（对子集 `indicator_source_keys`）
3. `extract_active(...)`：
   - `new_result.mapping.time == new_data.mapping.time`
   - `new_result.ranges[base].pack_bars == new_result.mapping.height()`
   - 若 `signals / backtest` 存在，高度必须等于 `new_result.mapping.height()`

### 7.2 WF 测试

1. `P_train = 0` 合法时，`train_warmup` 允许空区间。
2. 第 0 窗：
   - `train_warmup / train_active / test_warmup` 不足直接报错
   - `test_active` 允许截短
3. `test_active < 2`：
   - 第 0 窗报错
   - 后续最后一窗不生成
4. 跨窗注入：
   - 末根持仓方向检测
   - `carry_only_signals` 只注入测试预热最后一根同向开仓
   - `final_signals` 才追加倒数第二根双向离场
   - `natural_test_pack_backtest_result.backtest` 才是下一窗 carry 来源
   - `final_test_pack_result.backtest` 不能再被当作下一窗 carry 来源
5. `ignore_indicator_warmup`：
   - 默认值 `false` 时，结果口径必须与严格预热模式一致
   - 显式设为 `true` 时，只验证链路可运行与对照差异存在，不把它当作严格正确性测试

### 7.3 stitched 测试

1. `stitched_result.mapping.time == stitched_data.mapping.time`
2. `stitched_result.indicators[k]["time"] == stitched_data.source[k].time`
3. `mapping` 语义投影时间一致
4. 非 base `indicators[k]`：
   - 0 根重叠可拼
   - 1 根重叠后窗口覆盖前窗口
   - >1 根重叠直接报错
5. 资金列重建：
   - 边界行 `growth = 1`
   - 同窗口非边界行按局部增长因子递推
   - stitched 全局资金归零后保持 0
   - 最终返回给调用方的 `stitched_result.backtest` 必须已经是重建后的全局 backtest

## 8. 验收顺序

严格按顺序执行：

1. 类型与 builder 改完
2. 初始取数改完
3. 单次回测与 `extract_active(...)` 改完
4. WF 与 stitched 改完
5. Python 包装层改完
6. 再统一运行检查

命令顺序：

1. `just check`
2. `just test`

不要一边改一边跑 `just check`。

## 9. AI 审阅报告

执行前审阅应至少覆盖：

1. 是否仍有旧 `SourceRange { warmup, total }` 残留。
2. 是否仍有旧 `transition_*` 字段残留。
3. `build_result_pack(...)` 是否误调用 `build_mapping_frame(...)`。
4. `extract_active(...)` 是否仍误走 builder。
5. stitched 是否仍试图从中间态持有完整 `mapping[k]`。
6. `walk_forward` 主循环是否已闭环：
   - `window_results.push(...)`
   - `prev_last_bar_position` 回写
   - `has_cross_boundary_position` 回写
7. 是否已经显式区分：
   - `raw_signal_stage_result`
   - `carry_only_signals`
   - `natural_test_pack_backtest_result`
   - `final_signals`
   - `final_test_pack_result`
8. `detect_last_bar_position(...)` 是否只从 `natural_test_pack_backtest_result.backtest` 读取，而不是误从正式强平后的 `final_test_pack_result.backtest` 读取。

## 10. 执行后更新报告

执行完成后，把下面清单直接回填到本文：

1. 实际修改文件列表
2. 删除的旧接口 / 旧字段
3. 新增测试列表
4. `just check` 结果
5. `just test` 结果
6. 未完成项与阻塞项
