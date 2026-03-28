# WF 最小改动预热方案讨论摘要（逻辑链条闭环）

这份文档是本次任务的方案摘要，不是迁移文档。目标是以最小改动修复 WF 预热质量问题，并把“指标预热口径”先做成可验证、可复用的统一规范。

## 废弃说明（新增）

【目标口径】
1. 当前摘要中的 WF 最小改动方案已废弃，不再作为后续实现依据。
2. 废弃原因不是局部公式错误，而是方案源头存在结构性问题：
- 当前方案先按 `base` 生成窗口，再把窗口映射到各个 `source`；
- 但 `base` 窗口合法，不代表所有 `source` 在预热数量、左侧可用数据、mapping 投影后仍然合法；
- 这会导致“base 已合法、source 才报错”的滞后冲突，很难通过局部补规则优雅收口。
3. 当前方案里通过 `WFDataContainer/WFSummaryContainer` 额外包装 `ranges` 的做法，也放大了容器语义与窗口合法性判定的复杂度。
4. 因此本任务不再继续沿着“最小改动 + WF 专用容器层”方向推进实现。
5. 后续应以新的重构任务替代本方案，重新定义：
- `DataContainer/BacktestSummary` 自身的 `ranges` 语义；
- Python 层构造阶段的 `source` 合法性前移；
- “窗口合法”的统一判定口径。

【边界说明】
1. 下文内容保留为本次讨论快照，供回溯当时思路与问题来源使用。
2. 除非后续新任务明确复用某些条目，否则不得直接以本文后续规则作为当前实现标准。

阅读标记：
- `【目标口径】`：本任务必须落地的规则。
- `【边界说明】`：本任务明确不处理或延后处理的内容。
- 全文统一策略：Fail-Fast，直接报错，不做静默回退。

---

## 0. 总体取舍（原拍板，现已废弃）

【目标口径】
1. 不改回测引擎主链。
2. 不做全项目容器重构。
3. 先做“指标契约重构”，再接入 WF。
4. 移除白名单主机制，不再依赖 `wf_allow_internal_nan_indicators` 兜底（确认性声明：当前代码中该字段已不存在）。
5. WF 内部允许引入专用容器层（带索引元数据），但对外返回仍保持通用容器类型。

【边界说明】
1. 本次不推进全局 run_ranges 架构重构。
2. 本次聚焦“指标预热契约 + WF 消费规范”。
3. 本次不讨论历史迁移细节，只定义新口径。

---

## 1. 第一阶段先做什么（关键顺序）

【目标口径】
第一阶段先落地“指标契约 + 指标测试”，完成后再改 WF：
1. 给每个指标补齐统一契约回调（见第 2 节）。
2. 落地 source 级预热聚合工具函数（见第 3 节，需暴露 PyO3）。
3. 完成全量指标 pytest 专项（每个已注册指标都覆盖，单指标独立样本校验）。
4. 只有第一阶段通过后，才进入 WF 预检与窗口切分改造。

理由：
- WF 的预热逻辑依赖指标口径；先把指标口径做实，后续链路才不会漂移。

### 1.1 WF 内部容器与边界（新增）

【目标口径】
1. 仅在 WF 内部引入两类专用容器：
- `WFDataContainer { data: DataContainer, ranges: WindowRanges }`
- `WFSummaryContainer { summary: BacktestSummary, ranges: WindowRanges }`
2. 两类 WF 容器都不可变：
- 任何切片只能通过工具函数返回新对象；
- 切片实现使用 Rust + Polars 矢量化流程（clone/slice/concat），不允许就地改写。
3. WF 内部禁止直接切片通用容器：
- 禁止直接切片 `DataContainer`/`BacktestSummary`；
- 必须走 `slice_wf_data(...)` / `slice_wf_summary(...)` 一类工具函数。
4. 回测引擎与优化器不感知 WF 容器：
- 调用引擎时只借用 `wf_data.data`（或 `wf_summary.summary`）。
5. 对外返回边界保持不变：
- WF 最终对外仍返回通用 `DataContainer` / `BacktestSummary`；
- 仅在 WF 内部使用带 `ranges` 的包装容器。

---

## 2. 指标统一契约（每个指标必须遵守）

### 2.1 两个必实现回调（唯一写法）

【目标口径】
每个指标必须实现以下两个回调，缺一不可：
1. `required_warmup_bars(resolved_params) -> usize`
2. `warmup_mode() -> Strict | Relaxed`

含义：
1. `required_warmup_bars` 是该指标“最小必要预热值”的唯一真值来源。
2. `warmup_mode` 定义该指标在“非预热段”的校验强度。

参数规则：
1. `optimize=true`：取参数 `max`。
2. `optimize=false`：取参数 `value`。

为什么这样取：
1. `optimize=true` 阶段需要覆盖整段搜索空间，预热按 `max` 计算才能得到安全上界，避免某些候选参数在运行时预热不足。
2. `optimize=false` 阶段只执行当前这组已确定参数，预热按 `value` 计算才能与真实运行口径一致，避免无意义放大预热区。
3. 参数解析责任统一由调用方承担：先按 `optimize` 规则把 `Param` 解析为 `resolved_params`，再传给 `required_warmup_bars`；指标回调内部不重复做 `max/value` 解析。

### 2.2 两类模式的运行时校验语义

【目标口径】
1. `Strict`：
- 预热段（前 `warmup` 行）在该指标全部输出列上应为空；
- 非预热段在该指标全部输出列上不得出现 `NaN/null`。
2. `Relaxed`：
- 预热段（前 `warmup` 行）在该指标全部输出列上应为空；
- 非预热段允许结构性空值，但按行检查时不得“整行全空”（该指标全部输出列同一行同时为空）。

说明：
- `opening-bar` 归类为 `Strict`，允许 `warmup=0`。
- `PSAR`（后续如 `SuperTrend`）归类为 `Relaxed`。

### 2.2.1 预热检查作用域（必须明确）

【目标口径】
1. 当前口径固定为“全列口径”。
2. `required_warmup_bars` 表达的是该指标全部输出列的前导预热需求上界：
- 对该指标全部输出列分别计算前导空值数量；
- 取最大值作为该指标 `required_warmup_bars`。
3. `Strict/Relaxed` 运行时检查也按该指标全部输出列执行，不再区分主列/核心列。

【边界说明】
1. `Relaxed` 仅放宽“非预热段逐元素非空”约束，不放宽预热段全空约束。
2. `Relaxed` 非预热段仍需满足“按行不得整行全空”。

### 2.3 指标列归属规则（避免歧义）

【目标口径】
1. 指标业务列命名仍保持现有规则（由 `indicator_key` 前缀区分）。
2. 预热契约不写入指标 DataFrame 列，单独走契约结构返回。

---

## 3. 预热聚合工具函数（Rust + PyO3）

【目标口径】
提供一个“纯参数 -> 契约结果”的聚合函数，并暴露给 PyO3：

`resolve_indicator_contracts(indicators_params_py) -> IndicatorContractReport`

`IndicatorContractReport` 最小字段：
1. `warmup_bars_by_source: Dict[str, int]`
2. `contracts_by_indicator: Dict[str, {source, warmup_bars, warmup_mode}]`

语义：
1. 先把原始 `Param` 按 `optimize` 规则解析成 `resolved_params`。
2. 遍历所有指标，调用 `required_warmup_bars(resolved_params)` 与 `warmup_mode()`。
3. 同一 source 下取最大 warmup，得到 `warmup_bars_by_source`。
4. 同时返回每个指标的契约明细，供 WF 预检逐指标校验。

错误策略（Fail-Fast）：
1. 指标未实现回调：报错。
2. 指标参数缺失或非法：报错。
3. 本函数不做 base 绑定；base 绑定与“缺失 base source 报错”由 `validate_wf_indicator_readiness(...)` 负责。

PyO3 设计对齐说明：
- 按 `doc/structure/pyo3_interface_design.md` 风格，优先放在 `pyo3_quant.backtest_engine.indicators` 子模块。

---

## 4. WF 如何消费第一阶段产物

### 4.1 预检入口保持唯一

【目标口径】
`Backtest.validate_wf_indicator_readiness(wf_cfg, params_override=None) -> WfPrecheckReport`

方法职责更新为：
1. 先按固定规则构建预检参数集（`optimize=true -> max`，`optimize=false -> value`），并解析成 `resolved_params`。
2. 调用 `resolve_indicator_contracts(...)` 得到：
- `warmup_bars_by_source`
- `contracts_by_indicator`
3. 再跑 `ExecutionStage::Indicator` 得到指标输出结果。
4. 逐指标执行运行时硬校验：
- 以该指标 `required_warmup_bars(resolved_params)` 返回值划分预热段；
- 按 `warmup_mode` 在“该指标全部输出列”上执行 Strict/Relaxed 校验（见 2.2.1）。
5. 返回结构化预检结果；失败直接报错。
6. 绑定 base 预热真值（仅用于 base 窗口切分）：
`indicator_warmup_bars_base = warmup_bars_by_source[base_data_key]`；缺失直接报错。
7. `warmup_bars_by_source` 必须完整保留到 WF runner，禁止在预检后丢弃。
8. WF 运行阶段必须按每个 source 独立计算 `source_warmup_start/source_warmup_end`，不允许只用 base 预热值统一套所有 source。

### 4.2 `WfPrecheckReport` 最小字段

【目标口径】
最小字段必须包含：
- `base_data_key: String`
- `warmup_bars_by_source: HashMap<String, usize>`
- `contracts_by_indicator: HashMap<String, IndicatorContract>`

说明：
- Fail-Fast 口径固定为“失败直接抛异常，不返回 `ok=false` 报告”；
- 因此 report 只承载成功路径数据，错误信息由异常链承载；
- 白名单字段从返回中移除。

### 4.3 指标校验改动落点（改哪里）

【目标口径】
指标校验分两层，改动位置必须明确：

1. Rust 运行时校验（WF 预检硬校验）：
- 指标契约回调与业务实现：`src/backtest_engine/indicators/**/*.rs`
- 指标注册与统一入口：`src/backtest_engine/indicators/registry.rs`
- 契约聚合与 PyO3 暴露：`src/backtest_engine/indicators/py_bindings.rs`（或同等导出位置）
- 模块注册：`src/lib.rs`（若新增导出符号）

2. Python 入口封装（只封装，不重写校验逻辑）：
- 预检调用入口：`py_entry/runner/backtest.py` 中 `validate_wf_indicator_readiness(...)`

3. pytest 测试层（集中在指标专项）：
- 指标契约专项：`py_entry/Test/indicators/test_indicator_warmup_contract.py`
- 聚合契约专项（Phase 1）：`py_entry/Test/indicators/test_resolve_indicator_contracts.py`
- 预检入口专项（Phase 2）：`py_entry/Test/backtest/test_wf_precheck_contract.py`

### 4.4 为什么不采用其他设计（但不保留旧方案）

【目标口径】
1. 不采用“在指标 DataFrame 中写掩码列”的设计：
- 同 source 多指标会出现契约列重名冲突；
- 契约信息污染业务输出列，后续信号消费容易歧义。
2. 不采用“从结果列反推 warmup”的设计：
- 结果形态依赖实现细节，容易漂移；
- 不能作为稳定的静态真值来源。
3. 本任务最终唯一口径：
- 由回调定义 warmup 与模式；
- 由运行时与 pytest 校验契约是否被正确实现。

---

## 5. 数据层硬校验（保留）

【目标口径】
`build_time_mapping` 构建阶段继续执行硬校验：
1. 首尾覆盖：
- `source_start <= base_start`
- `source_end + source_interval > base_end`（严格大于）
2. 原始 source 输入数据列不得出现 `NaN/null`。
3. `base_data_key` 必须是参与映射的最小周期 source；否则直接报错。
4. 最小周期校验口径必须固定：
- 不能比较字符串；
- 必须先通过统一工具函数解析每个 `data_key -> interval_ms`；
- 再比较 `interval_ms`，要求 `base_data_key` 对应值是最小值；
- 任一 `data_key` 解析失败直接报错。
5. 任一不满足直接报错。

说明：
- 这是数据源质量校验，不是 warmup 校验。

【边界说明】
1. 覆盖校验对等间隔时间序列（如 OHLCV）成立。
2. `Renko` 等非等间隔数据允许接入，但覆盖风险由外部承担。

### 5.1 Python 网络层覆盖优化（可选但推荐）

【目标口径】
1. 这部分必须对齐现有 Python 请求工具链，不新增对外协议字段：
- 配置入口：`OhlcvDataFetchConfig`（核心字段仍是 `since`、`limit`）
- 单次请求：`OhlcvRequestParams -> get_ohlcv_data(...)`
- 数据装配：`generate_data_dict(...)`
- 最终校验：`pyo3_quant.backtest_engine.data_ops.build_time_mapping(...)`
2. Python 层只做“覆盖补拉优化”，不做预热推导；预热由指标契约与 WF 预检处理。
3. 对用户保持零新增参数：仍只传 `since + limit`；补拉逻辑是 `generate_data_dict` 内部实现细节。
4. end 侧补拉增加一个参数：`end_backfill_min_step_bars`，默认 `5`。

流程（按现有工具函数可直接落地）：
1. 先请求 base 周期，得到 `base_start_time/base_end_time`。
2. 每个非 base 周期先用同一组 `since + limit` 发起首轮请求，得到
`source_start_time/source_end_time/actual_returned_bars`。
3. start 侧补拉（前移 `since`）：
- 若 `source_start_time > base_start_time`，每轮前移 1 根 source bar：
`since -= source_interval_ms`
- 重新请求，直到 `source_start_time <= base_start_time`。
4. end 侧补拉（增大 `limit`）：
- 若 `source_end_time + source_interval_ms <= base_end_time`，先估算缺口：
`missing = ceil((base_end_time - source_start_time) / source_interval_ms) + 1 - actual_returned_bars`
- 每轮 `limit += max(missing, end_backfill_min_step_bars)`，直到
`source_end_time + source_interval_ms > base_end_time`。
5. 全部 source 补拉完成后，再统一调用 `build_time_mapping`；若仍不满足覆盖，由 Rust 侧硬校验直接报错。
6. 为防止异常死循环，Python 内部补拉轮次使用模块内常量限流（内部常量，不暴露给策略配置）。

【边界说明】
1. 该优化不影响 Rust 侧算法与异常口径。
2. 该优化失败时，仍以 `build_time_mapping` 报错为准（Fail-Fast）。
3. `source_interval_ms` 估算仅适用于等间距时间序列（如 OHLCV、Heikin-Ashi）；`Renko` 不保证有效。
4. `end_backfill_min_step_bars` 属于 Python 数据请求层参数，不属于 `WalkForwardConfig`。

---

## 6. 向前测试第一层：函数式数据流总览（新增）

【目标口径】
1. 向前测试模块必须采用函数式、无副作用流程。
2. 每一步都必须是显式输入 -> 显式输出。
3. 禁止就地修改 `DataContainer` / `BacktestSummary`。
4. 禁止就地修改 `WFDataContainer` / `WFSummaryContainer`。
5. 每次数据切片、结果切片、信号注入、窗口拼接都必须返回新对象。
6. 本层只做主流程总览，不展开内部算法细节。

### 6.1 统一记号与容器边界

【目标口径】
1. WF 内部只使用两类专用容器：
- `WFDataContainer { data: DataContainer, ranges: WindowRanges }`
- `WFSummaryContainer { summary: BacktestSummary, ranges: WindowRanges }`
2. 为了在总流程里表达“同一窗口的数据容器与结果容器一起流动”，引入仅用于文档描述的记号：
- `wf_result_i = { data: WFDataContainer, summary: WFSummaryContainer }`
3. `window_test_results[i]` 与 `stitched_test_result` 都按这个二元结果对象理解。
4. 这只是文档记号，不新增正式类型定义。
5. 回测引擎与优化器不感知 WF 专用容器：
- 优化器只借用 `WFDataContainer.data`
- 回测引擎只借用 `WFDataContainer.data` 或 `WFSummaryContainer.summary`
6. WF 最终对外返回时，再从内部容器脱壳为通用 `DataContainer/BacktestSummary`。
7. `WindowRanges` 只表达“当前这个 WF 容器实际承载了哪一段 base/source 数据”：
- 不表达全局共享状态；
- 不允许由调用方口头约定或隐式推断；
- 每次新建 `WFDataContainer/WFSummaryContainer` 时都必须显式写入。
8. `WindowRanges` 的唯一语义是“当前容器实际承载的数据区间”：
- 不是策略统计区间；
- 不是窗口计划区间；
- 容器里实际装了哪一段数据，`ranges` 就必须写哪一段；
- 若容器承载的是 `run range`，`ranges` 必须写 `run range`；
- 若容器承载的是 `test-only/stat range`，`ranges` 必须写 `test-only/stat range`；
- 禁止把 `eval_stat_range` 写进仍然承载 `eval_run_range` 数据的容器；
- 禁止把“逻辑上关心的统计区间”冒充为“物理上实际承载的区间”。

### 6.2 全流程函数链

【目标口径】
1. 向前测试按以下固定函数链执行：

1. `precheck_wf(backtest, wf_cfg) -> (W_base, W_s)`
- 输入：`Backtest`、`WalkForwardConfig`
- 返回：base 预热需求 `W_base`、各 source 预热需求 `W_s`
- 作用：为后续 base 窗口生成与 source 映射提供唯一预热真值
- 复用第三层工具：`validate_wf_indicator_readiness`

2. `build_base_windows(data, wf_cfg, W_base) -> windows`
- 输入：全量 `DataContainer`、`WalkForwardConfig`、`W_base`
- 返回：每个窗口的 base 区间计划
- 作用：先在 base 维度生成三模式窗口
- 复用第三层工具：`build_base_window_ranges`

3. `build_source_ranges_for_windows(windows, mapping, W_s, mode) -> source_ranges_by_window`
- 输入：base 窗口、`mapping`、`W_s`、模式
- 返回：每个窗口、每个 source 的 source 区间计划
- 作用：把 base 区间映射成 source 区间
- 复用第三层工具：`build_source_ranges`

4. `build_train_eval_wf_data(data, windows, source_ranges_by_window, i) -> (train_wf_data_i, eval_wf_data_i)`
- 输入：全量 `DataContainer`、第 `i` 个窗口的区间计划
- 返回：训练容器与评估容器两个 `WFDataContainer`
- 作用：把全量数据切成当前窗口的训练数据和评估数据
- 复用第三层工具：`slice_wf_data`

5. `run_window_optimizer(train_wf_data_i, optimizer_config, template_cfg) -> params_i`
- 输入：当前窗口训练数据、优化配置、模板配置
- 返回：当前窗口最优参数 `params_i`
- 作用：在训练窗口上完成参数搜索，为评估窗口提供唯一参数输入

6. `run_signal_stage(eval_wf_data_i, params_i, template_cfg) -> first_eval_wf_summary_i`
- 输入：`eval_wf_data_i`、`params_i`、模板配置
- 返回：注入前 `WFSummaryContainer`
- 作用：第一遍只跑到 `Signals`

7. `inject_cross_window_signals(first_eval_wf_summary_i, prev_window_result, mode) -> injected_eval_wf_summary_i`
- 输入：当前窗口注入前 summary、上一窗口结果
- 返回：注入后的 `WFSummaryContainer`
- 作用：按跨窗规则返回新的信号容器
- 约束：`prev_window_result` 只能来自 `window_test_results[i-1]`，禁止读取任何中间态 summary
- 复用第三层工具：`build_injection_plan`

8. `run_backtest_stage(eval_wf_data_i, injected_eval_wf_summary_i, params_i, template_cfg) -> eval_backtest_wf_summary_i`
- 输入：当前窗口评估数据、注入后 summary、当前窗口参数、模板配置
- 返回：覆盖“测试预热区 + 测试非预热区”的中间 `WFSummaryContainer`
- 作用：第二遍执行 `Backtest`

9. `slice_window_test_result(window_i, eval_wf_data_i, eval_backtest_wf_summary_i, source_ranges_by_window[i]) -> window_test_results[i]`
- 输入：当前窗口 base 区间计划、当前窗口评估数据、中间 summary、当前窗口 source 区间
- 返回：仅保留测试非预热区的 `wf_result_i`
- 作用：切到窗口级最终测试结果，并在切片后调用 `recompute_wf_performance(...)` 计算窗口级 `Performance`
- 约束：`window_test_results[i]` 是下一窗口唯一允许读取的 `prev_window_result`
- 复用第三层工具：
  - `base_test_stat_range`
  - `test_stat_range`
  - `compose_window_result`
  - `slice_wf_data`
  - `slice_wf_summary`
  - `recompute_wf_performance`

10. `stitch_window_results(window_test_results) -> stitched_test_result`
- 输入：所有窗口级 `wf_result_i`
- 返回：stitched 级 `wf_result`
- 作用：拼接窗口结果、重建 stitched 资金列，并调用 `recompute_wf_performance(...)` 重算 stitched `Performance`
- 复用第三层工具：
  - `stitch_wf_data`
  - `stitch_wf_summary`
  - `recompute_wf_performance`

11. `unwrap_wf_results(window_test_results, stitched_test_result) -> public_results`
- 输入：WF 内部窗口结果与 stitched 结果
- 返回：对外通用返回
- 作用：从内部 WF 容器脱壳为 `DataContainer + BacktestSummary`

---

## 7. 向前测试第二层：阶段函数详解（新增）

### 7.1 `precheck_wf`

【目标口径】
1. 输入：
- `Backtest`
- `WalkForwardConfig`
2. 输出：
- `(W_base, W_s)`
3. 处理步骤：
- 调用 `validate_wf_indicator_readiness(...)`
- 读取 `indicator_warmup_bars_base`
- 读取 `warmup_bars_by_source`
- 绑定 `base_data_key`
4. 失败策略：
- 任一指标未就绪直接报错
- `base_data_key` 对应预热值缺失直接报错
5. 内部算法：
- 纯消费第三层的指标契约聚合结果

### 7.2 `build_base_windows`

【目标口径】
1. 输入：
- 全量 `DataContainer`
- `WalkForwardConfig`
- `W_base`
2. 输出：
- `windows`
3. 处理步骤：
- 读取 `N/T/M/S`
- 按模式计算第一个窗口的 base 区间
- 按 `step = S` 生成后续候选窗口
- 只纳入“测试非预热区存在”的合法窗口
- 一旦某候选窗口不再满足纳入条件，停止继续生成后续窗口
- 对每个窗口产出训练/执行两组区间
4. 容器处理：
- 本函数不切片容器，只产出 base 区间计划
5. 失败策略：
- 若最终合法窗口总数为 `0`，直接报错
- 模式约束不满足直接报错
6. 复用第三层工具：
- `build_base_window_ranges`

### 7.3 `build_source_ranges_for_windows`

【目标口径】
1. 输入：
- `windows`
- `mapping`
- `W_s`
- 模式
2. 输出：
- `source_ranges_by_window`
3. 处理步骤：
- 外层遍历窗口
- 内层遍历 `source_keys`
- 对每个 `(window_i, source_key)` 调用 `build_source_ranges(...)`
- 把结果写入 `source_ranges_by_window[i][source_key]`
4. 容器处理：
- 本函数不切片容器，只产出 source 区间计划
5. 失败策略：
- 任一 source 缺失 warmup 直接报错
- 任一 mapping 缺失或越界直接报错
6. 复用第三层工具：
- `build_source_ranges`

### 7.4 `build_train_eval_wf_data`

【目标口径】
1. 输入：
- 全量 `DataContainer`
- 当前窗口 `window_i`
- 当前窗口 `source_ranges_by_window[i]`
2. 输出：
- `train_wf_data_i`
- `eval_wf_data_i`
3. 处理步骤：
- 先把全量 `DataContainer` 包装为 `full_wf_data`
- 先按训练区间构造训练 `WindowRanges`
- 再按执行区间构造评估 `WindowRanges`
- 基于 `full_wf_data` 分别调用 `slice_wf_data(...)`
4. 容器处理：
- 输入容器：全量通用 `DataContainer`
- 输出容器：两个新的 `WFDataContainer`
5. 失败策略：
- 任一字段切片失败直接报错
6. 复用第三层工具：
- `wrap_full_wf_data`
- `slice_wf_data`
7. `build_train_eval_wf_data(...)` 的 `WindowRanges` 绑定规则：
- `train_wf_data_i.ranges.base` 必须写 `window_i.train_run_range_i`
- `eval_wf_data_i.ranges.base` 必须写 `window_i.eval_run_range_i`
- 对每个 `source_key`：
- 若 `BorrowFromTrain / ExtendTest`：
- `train_wf_data_i.ranges.source[source_key]` 必须写 `source_train_run_range_s`
- `eval_wf_data_i.ranges.source[source_key]` 必须写 `source_eval_run_range_s`
- 若 `NoWarmup`：
- `train_wf_data_i.ranges.source[source_key]` 必须写 `source_train_range_s`
- `eval_wf_data_i.ranges.source[source_key]` 必须写 `source_test_range_s`
- 这里写入的是“切出来并实际装入容器的数据范围”，不是后续 `Performance` 使用的统计范围

### 7.5 `run_window_optimizer`

【目标口径】
1. 输入：
- `train_wf_data_i`
- `optimizer_config`
- 模板配置
2. 输出：
- `params_i`
3. 处理步骤：
- 借用 `train_wf_data_i.data`
- 仅在训练窗口上执行优化
- 返回当前窗口唯一评估参数 `params_i`
4. 容器处理：
- 输入容器：`WFDataContainer`
- 输出容器：无 WF 容器，仅返回参数对象
5. 失败策略：
- 优化阶段失败直接报错

### 7.6 `run_signal_stage`

【目标口径】
1. 输入：
- `eval_wf_data_i`
- 当前窗口参数
- 模板配置
2. 输出：
- `first_eval_wf_summary_i`
3. 处理步骤：
- 借用 `eval_wf_data_i.data`
- 第一遍只执行到 `ExecutionStage::Signals`
- 产出注入前 `WFSummaryContainer`
4. 容器处理：
- 输入容器：`WFDataContainer`
- 输出容器：新的 `WFSummaryContainer`
- `first_eval_wf_summary_i.ranges` 必须直接复制 `eval_wf_data_i.ranges`
5. 失败策略：
- `Signals` 阶段失败直接报错

### 7.7 `inject_cross_window_signals`

【目标口径】
1. 输入：
- `first_eval_wf_summary_i`
- `prev_window_result`（窗口 `i=0` 时为空；窗口 `i>=1` 时只能取 `window_test_results[i-1]`）
- 模式
2. 输出：
- `injected_eval_wf_summary_i`
3. 处理步骤：
- 只从 `prev_window_result.summary` 的上一窗口 `Test` 末根推导跨窗持仓状态
- 生成当前窗口注入计划
- 只替换 `signals`
- 返回新的 `WFSummaryContainer`
4. 容器处理：
- 输入容器：`WFSummaryContainer`
- 输出容器：新的 `WFSummaryContainer`
- 只允许替换 `signals` 字段，`ranges` 必须保持与 `first_eval_wf_summary_i` 完全一致
5. 失败策略：
- 多空持仓冲突直接报错
- 若调用方传入的不是 `window_test_results[i-1]`，视为流程错误直接报错
6. 复用第三层工具：
- `build_injection_plan`

### 7.8 `run_backtest_stage`

【目标口径】
1. 输入：
- `eval_wf_data_i`
- `injected_eval_wf_summary_i`
- 当前窗口参数
- 模板配置
2. 输出：
- `eval_backtest_wf_summary_i`
3. 处理步骤：
- 借用 `eval_wf_data_i.data`
- 在“测试预热区 + 测试非预热区”上执行 `Backtest`
- 返回覆盖整段执行区间的中间 `WFSummaryContainer`
4. 容器处理：
- 输入容器：`WFDataContainer + WFSummaryContainer`
- 输出容器：新的 `WFSummaryContainer`
- `eval_backtest_wf_summary_i.ranges` 必须沿用 `injected_eval_wf_summary_i.ranges`
5. 失败策略：
- `Backtest` 失败直接报错

### 7.9 `slice_window_test_result`

【目标口径】
1. 输入：
- `window_i`
- `eval_wf_data_i`
- `eval_backtest_wf_summary_i`
- `source_ranges_by_window[i]`
2. 输出：
- `window_test_results[i] = { data, summary }`
3. 处理步骤：
- 先用 `base_test_stat_range(window_i)` 确定 base 测试非预热区
- 再对每个 `source_key` 用 `test_stat_range(...)` 确定 source 测试非预热区
- 按 base/source 各自区间切 `WFDataContainer`
- 按同一组 base/source 区间切 `WFSummaryContainer`
- 丢弃旧 `performance`
- 基于测试非预热区调用 `recompute_wf_performance(...)` 重算窗口级 `Performance`
- 组装成新的 `wf_result_i`
- 将 `wf_result_i` 发布为下一窗口唯一允许读取的 `prev_window_result`
4. 容器处理：
- 输入容器：`WFDataContainer + WFSummaryContainer`
- 输出容器：窗口级 `wf_result_i`
5. 失败策略：
- 任一区间缺失、越界或空区间直接报错
6. 复用第三层工具：
- `base_test_stat_range`
- `test_stat_range`
- `compose_window_result`
- `slice_wf_data`
- `slice_wf_summary`
- `recompute_wf_performance`

### 7.10 `stitch_window_results`

【目标口径】
1. 输入：
- `window_test_results`
2. 输出：
- `stitched_test_result`
3. 处理步骤：
- 先拼接窗口级 `WFDataContainer`
- 再拼接窗口级 `WFSummaryContainer`
- 只在 stitched 阶段重建资金列
- 基于 stitched `backtest + data` 调用 `recompute_wf_performance(...)` 重算 stitched `Performance`
- 做时间一致性强校验
4. 容器处理：
- 输入容器：`list[wf_result_i]`
- 输出容器：stitched 级 `wf_result`
5. 失败策略：
- 拼接 schema 不一致直接报错
- 时间校验失败直接报错
6. 复用第三层工具：
- `stitch_wf_data`
- `stitch_wf_summary`
- `recompute_wf_performance`

### 7.11 `unwrap_wf_results`

【目标口径】
1. 输入：
- `window_test_results`
- `stitched_test_result`
2. 输出：
- `window_test_results_public`
- `stitched_test_result_public`
3. 处理步骤：
- 从 `WFDataContainer/WFSummaryContainer` 取出 `.data/.summary`
- 保持字段原样透传
4. 容器处理：
- 输入容器：WF 内部结果
- 输出容器：通用 `DataContainer + BacktestSummary`
5. 失败策略：
- 禁止在此阶段再切片、再重算、再推导区间

---

## 8. 向前测试第三层：通用算法工具（新增）

### 8.1 `build_base_window_ranges`

【目标口径】
1. 本工具负责三模式下的 base 窗口生成，是 `build_base_windows(...)` 的唯一算法来源。
2. 删除旧的预热控制参数，新增唯一参数：`min_warmup_bars`（最小预热数量）。
3. 保留三模式：`BorrowFromTrain` / `ExtendTest` / `NoWarmup`。
4. `BorrowFromTrain` / `ExtendTest` 的预热数量公式：
- 训练预热：`E_train = max(W_base, M)`
- 测试预热：`E_test = max(W_base, M, 1)`
5. `NoWarmup` 的独立规则：
- 不定义 `E_train / E_test`
- 含义是“base 与 source 都不引入任何预热段”
6. 参数定义：
- `N`：全量 base K 线总数（来源：`data_dict.mapping.height()`）
- `T`：`train_bars`（来源：`WalkForwardConfig.train_bars`）
- `M`：`min_warmup_bars`（来源：`WalkForwardConfig.min_warmup_bars`）
- `S`：`test_bars`（来源：`WalkForwardConfig.test_bars`）
- `W_base`：`indicator_warmup_bars_base`
7. 滚动步长固定：`step = S`
8. 通用前置校验：
- `M >= 0`
- `T >= 1`
- `BorrowFromTrain / ExtendTest`：`S >= 2`
- `NoWarmup`：`S >= 3`
- `BorrowFromTrain / ExtendTest`：`E_test >= 1`
- `BorrowFromTrain`：`E_test <= (E_train + T)`
- `NoWarmup`：不引入额外预热变量校验
- 不满足直接报错
9. 窗口纳入与停止规则：
- 候选窗口先做 base 边界合法性判定，再判断是否纳入
- `BorrowFromTrain` 合法条件：`base_start_i + E_train + T + S <= N`
- `ExtendTest` 合法条件：`base_start_i + E_train + T + E_test + S <= N`
- `NoWarmup` 合法条件：`base_start_i + T + S <= N`
- 只有满足对应模式合法条件时，`Test_i` 才被视为“存在”
- 在合法前提下，再用 `eval_stat_range_i.start < eval_stat_range_i.end` 判定“测试非预热区存在”
- 若某候选窗口没有任何测试非预热数据，则该窗口不纳入结果集；这是正常停止生成窗口，不是运行时错误
- 窗口按时间顺序从前到后生成；一旦某候选窗口不再满足纳入条件，后续窗口也不再继续生成
- 若最终合法窗口总数为 `0`，直接报错
- 若最终合法窗口总数大于 `0`，则尾部不足整窗属于正常结束，不报错
10. `BorrowFromTrain` 公式：
- `base_start_i = i * step`
- `TrainWarmup_i = [base_start_i, base_start_i + E_train)`
- `Train_i = [base_start_i + E_train, base_start_i + E_train + T)`
- `TestWarmup_i = [base_start_i + E_train + T - E_test, base_start_i + E_train + T)`
- `Test_i = [base_start_i + E_train + T, base_start_i + E_train + T + S)`
- 训练回测区间：`train_run_range_i = [TrainWarmup_i.start, Train_i.end)`
- 训练评估区间：`train_eval_range_i = [Train_i.start, Train_i.end)`
- 执行回测区间：`eval_run_range_i = [TestWarmup_i.start, Test_i.end)`
- 执行评估区间：`eval_stat_range_i = [Test_i.start, Test_i.end)`
11. `ExtendTest` 公式：
- `base_start_i = i * step`
- `TrainWarmup_i = [base_start_i, base_start_i + E_train)`
- `Train_i = [base_start_i + E_train, base_start_i + E_train + T)`
- `TestWarmup_i = [base_start_i + E_train + T, base_start_i + E_train + T + E_test)`
- `Test_i = [base_start_i + E_train + T + E_test, base_start_i + E_train + T + E_test + S)`
- 训练回测区间：`train_run_range_i = [TrainWarmup_i.start, Train_i.end)`
- 训练评估区间：`train_eval_range_i = [Train_i.start, Train_i.end)`
- 执行回测区间：`eval_run_range_i = [TestWarmup_i.start, Test_i.end)`
- 执行评估区间：`eval_stat_range_i = [Test_i.start, Test_i.end)`
12. `NoWarmup` 公式：
- `base_start_i = i * step`
- `Train_i = [base_start_i, base_start_i + T)`
- `Test_i = [base_start_i + T, base_start_i + T + S)`
- 训练回测区间：`train_run_range_i = [Train_i.start, Train_i.end)`
- 训练评估区间：`train_eval_range_i = [Train_i.start, Train_i.end)`
- 执行回测区间：`eval_run_range_i = [Test_i.start, Test_i.end)`
- 执行评估区间：`eval_stat_range_i = [Test_i.start, Test_i.end)`

### 8.2 `build_injection_plan`

【目标口径】
1. 本工具负责三模式统一注入规则，是 `inject_cross_window_signals(...)` 的唯一算法来源。
2. 跨窗判定来源固定为“上一窗口 `Test` 末根持仓状态”。
3. 判定公式（窗口 `i >= 1`）：
- `prev_test_last = Test_{i-1}.end - 1`
- 多头跨窗：`entry_long_price(prev_test_last)` 非空且 `exit_long_price(prev_test_last)` 为空
- 空头跨窗：`entry_short_price(prev_test_last)` 非空且 `exit_short_price(prev_test_last)` 为空
- 若多头与空头同时成立，直接报错
4. 注入顺序（窗口 `i`）：
- 在 `Test_i` 倒数第二根注入双向离场
- 若跨窗为多头：
  - `BorrowFromTrain / ExtendTest`：在 `TestWarmup_i` 最后一根注入 `entry_long=true`
  - `NoWarmup`：在 `Test_i` 第一根注入 `entry_long=true`
- 若跨窗为空头：
  - `BorrowFromTrain / ExtendTest`：在 `TestWarmup_i` 最后一根注入 `entry_short=true`
  - `NoWarmup`：在 `Test_i` 第一根注入 `entry_short=true`
- 若无跨窗持仓：不注入开仓
5. `NoWarmup` 的附加约束：
- `Test_i` 第一根跨窗开仓注入与 `Test_i` 倒数第二根离场注入禁止落在同一根 K 线
- 因此 `NoWarmup` 的合法窗口前提固定为 `S >= 3`
6. 第一窗仅执行 `Test_0` 倒数第二根离场注入；不执行跨窗开仓注入。
7. 每窗执行链固定：
- 先运行到 `Signals`
- 按规则注入
- 注入后执行 `run_backtest`
- 窗口级与 stitched 级 `Performance` 统一由 `recompute_wf_performance(...)` 负责
8. 跨窗状态回写规则：
- 窗口 `i` 只能读取 `window_test_results[i-1]`
- 窗口 `i` 完成切片与 `Performance` 重算后，才能把 `window_test_results[i]` 发布给窗口 `i+1`
- 禁止把 `first_eval_wf_summary_i`、`injected_eval_wf_summary_i`、`eval_backtest_wf_summary_i` 作为下一窗状态来源
9. 测试预热段职责（仅 `BorrowFromTrain / ExtendTest`）：
- 只用于指标预热与信号注入锚点
- 不作为独立回测统计区
- 窗口绩效只看 `Test` 非预热段
10. 执行切片区间：
- `BorrowFromTrain`：
  `evaluation_range_i = [base_start_i + E_train + T - E_test, base_start_i + E_train + T + S)`
- `ExtendTest`：
  `evaluation_range_i = [base_start_i + E_train + T, base_start_i + E_train + T + E_test + S)`
- `NoWarmup`：
  `evaluation_range_i = [base_start_i + T, base_start_i + T + S)`
11. 资金列重建口径：
- 窗口级 `Test` 结果不做资金列重建
- `stitched` 阶段必须按窗口边界重建资金列

### 8.3 `build_source_ranges`

【目标口径】
1. 定义工具函数（每个窗口、每个 source 调用一次）：
- `build_source_ranges(window_i, source_s, mode, W_s, mapping_col_s) -> SourceRangeResult`
- `SourceRangeResult` 为枚举返回：
  - `WarmupRanges`
  - `NoWarmupRanges`
2. 工具函数入参：
- `window_i`：第 `i` 个窗口的 base 区间（来自 `build_base_window_ranges`）
- `source_s`：当前 source 键
- `mode`：`BorrowFromTrain / ExtendTest / NoWarmup`
- `W_s`：`warmup_bars_by_source[source_s]`
- `mapping_col_s`：`mapping[source_s]`
3. 返回类型定义（统一右开区间）：
- `WarmupRanges`：
  - `source_train_run_range_s = [source_train_run_start_s, source_train_end_s)`
  - `source_train_eval_range_s = [source_train_start_s, source_train_end_s)`
  - `source_eval_run_range_s = [source_eval_run_start_s, source_test_end_s)`
  - `source_eval_stat_range_s = [source_test_start_s, source_test_end_s)`
- `NoWarmupRanges`：
  - `source_train_range_s = [source_train_start_s, source_train_end_s)`
  - `source_test_range_s = [source_test_start_s, source_test_end_s)`
4. 记号定义：
- `map_s(x)`：把 base 索引 `x` 映射到 source 索引
- `end_s(x_end)`：右边界映射，定义为 `map_s(x_end - 1) + 1`
5. `BorrowFromTrain / ExtendTest` 公式：
- 训练段：
  - `start1_train_s = map_s(TrainWarmup_i.start)`
  - `start2_train_s = map_s(Train_i.start) - W_s`
  - `source_train_run_start_s = min(start1_train_s, start2_train_s)`
  - `source_train_start_s = map_s(Train_i.start)`
  - `source_train_end_s = end_s(Train_i.end)`
- 执行段：
  - `start1_eval_s = map_s(TestWarmup_i.start)`
  - `start2_eval_s = map_s(Test_i.start) - W_s`
  - `source_eval_run_start_s = min(start1_eval_s, start2_eval_s)`
  - `source_test_start_s = map_s(Test_i.start)`
  - `source_test_end_s = end_s(Test_i.end)`
6. `NoWarmup` 公式：
- `source_train_start_s = map_s(Train_i.start)`
- `source_train_end_s = end_s(Train_i.end)`
- `source_test_start_s = map_s(Test_i.start)`
- `source_test_end_s = end_s(Test_i.end)`
- 按 `NoWarmupRanges` 返回
7. Fail-Fast 规则：
- 任一 `map_s(x)` 缺失（null/越界）直接报错
- `BorrowFromTrain / ExtendTest` 下若 `start2_* < 0` 直接报错
- 任一区间不满足 `start < end` 直接报错
- 报错字段至少包含：`window_id`、`source`、`mode`、`stage(train/eval)`、`required_warmup`、`available_left_bars`
8. 结果语义：
- 不同窗口、不同 source 的切片起止不同是预期行为
- 区间统一由 `build_source_ranges(...)` 产出，禁止在其他模块重复计算或改写

### 8.4 `wrap_full_wf_data`

【目标口径】
1. `wrap_full_wf_data(data: DataContainer) -> WFDataContainer` 是通用数据进入 WF 内部的唯一包装入口。
2. 输入：
- 全量通用 `DataContainer`
3. 输出：
- `WFDataContainer { data, ranges }`
4. `ranges` 初值定义：
- `full_base_range = [0, N)`
- `full_source_range[source_key] = [0, data.source[source_key].height())`
- 该初值只表达“当前容器承载的是全量数据”，不表达训练/评估窗口语义
5. 使用规则：
- `slice_wf_data(...)` 的输入必须是 `WFDataContainer`
- 因此所有训练/评估窗口切片，都必须先从 `wrap_full_wf_data(...)` 得到 `full_wf_data`
- 禁止直接从裸 `DataContainer` 进入 `slice_wf_data(...)`
6. `WFSummaryContainer` 的初始 `ranges` 绑定规则：
- `run_signal_stage(...)` 首次生成 `WFSummaryContainer` 时，必须直接复制对应 `eval_wf_data_i.ranges`
- `run_backtest_stage(...)` 产生新的 `WFSummaryContainer` 时，必须沿用输入 summary 的 `ranges`
- 引擎阶段本身禁止重新推导 `ranges`

### 8.5 `base_test_stat_range`、`test_stat_range` 与 `compose_window_result`

【目标口径】
1. `base_test_stat_range(window_i)` 是窗口 base 测试非预热区间的唯一提取函数：
- `BorrowFromTrain / ExtendTest`：返回 `window_i.eval_stat_range_i`
- `NoWarmup`：返回 `window_i.eval_stat_range_i`
2. `test_stat_range(result: SourceRangeResult)` 是窗口 source 测试非预热区间的唯一提取函数：
- `WarmupRanges(r)`：返回 `r.source_eval_stat_range_s`
- `NoWarmupRanges(r)`：返回 `r.source_test_range_s`
3. `compose_window_result(...) -> wf_result_i` 是窗口级结果构造工具：
- 对每个窗口、每个 `source_key`
- 先取 `base_range = base_test_stat_range(window_i)`
- 读取 `result = source_ranges_by_window[i][source_key]`
- 取 `[a, b) = test_stat_range(result)`
- 用 `base_range` + 每个 source 的 `[a, b)` 构造窗口级 `WFDataContainer`
- 用同一组 `base_range` + source 测试区间构造窗口级 `WFSummaryContainer`
4. 统一约束：
- `window_test_results` 只能消费 `window_i + source_ranges_by_window`
- `signals/backtest/mapping/skip_mask` 只能消费 `base_test_stat_range(window_i)`
- `indicators/source` 只能消费 `test_stat_range(result)`
- 禁止重新计算区间
- 任一 base/source 测试区间缺失、越界或空区间直接报错
5. `window_test_results[i]` 的 `ranges` 绑定规则：
- `window_test_results[i].data.ranges.base` 与 `window_test_results[i].summary.ranges.base` 必须写 `base_test_stat_range(window_i)`
- 对每个 `source_key`：
- `window_test_results[i].data.ranges.source[source_key]` 与 `window_test_results[i].summary.ranges.source[source_key]` 必须写 `test_stat_range(result)`
- 只有在 `slice_window_test_result(...)` 已经把容器切到 `test-only` 之后，才允许把 `ranges` 改写为 `stat/test-only range`
- 在训练容器、执行容器阶段，禁止提前写成 `stat/test-only range`

### 8.6 `slice_wf_data` 与 `stitch_wf_data`

【目标口径】
1. `slice_wf_data(...) -> WFDataContainer`
- 输入：`WFDataContainer` 原对象 + base/source 区间
- 输出：新的 `WFDataContainer`
- 索引口径：`mapping/skip_mask` 走 base，`source` 走 source
2. 窗口级切片规则：
- `mapping`：按窗口 base 区间切片
- `source`：逐 key 切片，直接使用 `build_source_ranges(...)` 产出的 source 区间
- `mapping` 重基：每列都要重基到新 `source` 局部索引
- `skip_mask`：若存在，按同一 base 区间切片
- `base_data_key`：原样复制
- 返回对象的 `ranges` 必须同步更新为本次切片实际使用的 base/source 区间
3. `stitch_wf_data(...) -> WFDataContainer`
- 唯一输入：`window_test_results[i].data`
- 输入数据拼接只允许依赖输入数据本身，禁止读取 `window_test_results[i].summary`
- `source`：按 key 逐窗严格拼接
- `mapping`：逐窗拼接并按累计 source 行偏移做 offset shift
- `skip_mask`：若存在，按窗口顺序逐窗拼接
- `base_data_key`：原样复制
- stitched 结果的 `ranges` 必须显式重建为：
- `stitched_base_range = [0, len(base_理论时间序列))`
- `stitched_source_range[source_key] = [0, len(source_理论时间序列[source_key]))`
4. stitched 理论时间序列构造规则：
- `base_理论时间序列`：
- 按 `window_id` 递增顺序
- 逐窗拼接 `window_test_results[i].data` 内部可用的 base `time` 序列
- 若输入数据侧不存在可用于 stitched 校验的 base `time` 字段，直接报错，禁止回退读取 `summary`
- `source_理论时间序列[source_key]`：
- 按 `window_id` 递增顺序
- 逐窗拼接 `window_test_results[i].data.source[source_key].time`
- 若任一 `source[key]` 缺少 `time` 字段，直接报错
- `skip_mask_理论值`：
- 若 `skip_mask` 存在，按 `window_id` 递增顺序逐窗拼接 `window_test_results[i].data.skip_mask`
5. stitched 后强校验：
- `source[key]`：`time` 列与理论 `time` 列完全一致
- `mapping`：
  - 先校验 `mapping.height == len(base_理论时间序列)`
  - 再逐列校验 `mapping[key] -> source[key]` 映射后的 `time` 列与理论 mapping `time` 列完全一致
- `skip_mask`：
  - 行数与 base 理论长度一致
  - 各列逐行值与理论 skip_mask 完全一致
6. 实现约束：
- 所有切片、拼接、校验必须基于 Rust + Polars 矢量化实现

### 8.7 `slice_wf_summary` 与 `stitch_wf_summary`

【目标口径】
1. `slice_wf_summary(...) -> WFSummaryContainer`
- 输入：`WFSummaryContainer` 原对象 + 对应窗口区间信息
- 输出：新的 `WFSummaryContainer`
- 索引口径：`indicators` 走 source，`signals/backtest` 走 base
2. 窗口级切片规则：
- `indicators`：
  - 本质是按 `source_key` 组织的多 source 容器
  - 每个 key 复用 `build_source_ranges(...)` 的 source 区间
- `signals`：按窗口 base 区间切片
- `backtest`：按窗口 base 区间切片，窗口级不重建资金列
- `performance`：
  - 切片后旧值丢弃
  - 本工具只负责把 `performance` 置空，不在此处重算
- 返回对象的 `ranges` 必须同步更新为本次切片实际使用的 base/source 区间
3. base/source 区间来源约束：
- `signals/backtest` 只能使用 `base_test_stat_range(window_i)`
- `indicators` 只能使用 `test_stat_range(result)`
4. `stitch_wf_summary(...) -> WFSummaryContainer`
- 唯一输入：`window_test_results[i].summary`
- 结果数据拼接只允许依赖结果数据本身，禁止回读 `window_test_results[i].data`
- `indicators`：按 key 逐窗严格拼接，拼接后仍保持 source 语义
- `signals/backtest`：逐窗严格拼接
- `backtest`：拼接后必须按窗口边界重建资金列
- `performance`：先置空
- stitched 结果的 `ranges` 必须与 `stitch_wf_data(...)` 产出的 stitched data ranges 完全一致
5. stitched 理论区间构造规则：
- `base_理论时间序列`：
- 按 `window_id` 递增顺序
- 逐窗拼接 `window_test_results[i].summary.backtest.time`
- 若 `backtest` 缺少 stitched 所需的 base `time` 字段，直接报错
- `source_理论时间序列[source_key]`：
- 按 `window_id` 递增顺序
- 逐窗拼接 `window_test_results[i].summary.indicators[source_key].time`
- 若某个结果字段天然没有 `time` 列且 stitched 校验又需要该列，直接报错，禁止回退读取 `data`
- `base_理论区间`：
- 起点固定为 `0`
- 终点固定为 `len(base_理论时间序列)`
- `source_理论区间[source_key]`：
- 起点固定为 `0`
- 终点固定为 `len(source_理论时间序列[source_key])`
- `performance_理论时间跨度`：
- `start = base_理论时间序列.first`
- `end = base_理论时间序列.last`
- `span` 必须与 stitched base 长度对应
6. stitched 后强校验：
- `indicators[key]`：`time` 列与该 key source 理论 `time` 列完全一致
- `signals/backtest`：`time` 列与 base 理论 `time` 列完全一致
- `performance`：时间跨度字段与 `performance_理论时间跨度` 完全一致
- `ranges.base/source`：必须分别与 `base_理论区间`、`source_理论区间` 完全一致
7. 实现约束：
- 字段切片、窗口拼接、时间一致性校验必须使用 Rust + Polars 矢量化流程

### 8.8 `recompute_wf_performance`

【目标口径】
1. `recompute_wf_performance(wf_data, wf_summary) -> WFSummaryContainer` 是 `Performance` 重算的唯一入口。
2. 输入：
- `WFDataContainer`
- 不含有效 `performance` 的 `WFSummaryContainer`
3. 输出：
- 写回新 `performance` 后的 `WFSummaryContainer`
4. 规则：
- 窗口级重算：基于窗口级 test-only `wf_data + wf_summary.backtest`
- stitched 级重算：基于 stitched `wf_data + wf_summary.backtest`
- 本工具只重算 `performance`，不再改动 `indicators/signals/backtest/ranges`
- stitched 级重算前，`wf_data.ranges` 与 `wf_summary.ranges` 必须已完成一致性校验
5. 使用位置：
- `slice_window_test_result(...)` 在切到测试非预热区后调用一次
- `stitch_window_results(...)` 在 stitched 资金列重建完成后调用一次

---

## 9. Python/private 工作流影响评估（结论：改动小）

【目标口径】
1. 主流程顺序不变：`backtest -> optimize -> sensitivity -> walk_forward`。
2. 用户侧新增负担：
- 第一阶段需要关注指标契约落地；
- 入口显式调用一次预检。
3. executor/ipynb/searcher 仍是“入口加一次预检”，主调用链不改。

参数口径更新：
1. 工作流级参数：
- 现有 WF 参数：`train_bars/min_warmup_bars/test_bars/inherit_prior/optimizer_config`
- 预热模式参数：`wf_warmup_mode`（Rust enum，经 PyO3 暴露，禁止字符串自由输入）
2. `wf_allow_internal_nan_indicators` 从工作流配置移除。

### 9.1 文件改动落点（最小集合）

【目标口径】
1. Python 侧（必须改）：
- `py_entry/strategy_hub/core/config.py`：工作流参数入口，新增/透传 `wf_warmup_mode`
- `py_entry/runner/backtest.py`：新增 `validate_wf_indicator_readiness(...)`
- `py_entry/strategy_hub/core/executor.py`：单策略入口显式调用一次预检
- `py_entry/strategy_hub/core/strategy_searcher.py`：`walk_forward` 分支前显式调用一次预检
- `py_entry/strategy_hub/demo.ipynb`：增加显式预检单元
2. Rust 侧（仅当 `wf_warmup_mode` 需要入 `WalkForwardConfig` 时改）：
- `src/types/inputs/walk_forward.rs`

【明确不改动】
1. 不改数据请求协议（仍为 `since + limit`）。
2. 不改回测引擎主链。
3. 不改容器体系。
4. 不改 research 评估口径。

---

## 10. 分阶段落地顺序（更新）

【目标口径】
1. Phase 1（先做，指标规范化）：
- 每个指标补齐两个回调：`required_warmup_bars` + `warmup_mode`
- `resolve_indicator_contracts`（Rust + PyO3）落地
- 指标 pytest 专项按 Strict/Relaxed 规则全部通过

2. Phase 2（WF 接入与工作流贯通）：
- `validate_wf_indicator_readiness` 改为消费契约聚合结果
- Python 入口统一“显式预检一次”：`executor.py`、`strategy_searcher.py`、`demo.ipynb`
- `wf_warmup_mode` 参数链路打通（strategy_hub 配置 -> WF 调用）
- `wf_allow_internal_nan_indicators` 路径彻底移除
- 保持三模式与 base 预热数量公式不变
- runner 按 8.3 落地“每 source 独立预热切片（含 source_warmup_start/source_warmup_end）”

3. Phase 3（数据覆盖优化 + 全链路回归）：
- `generate_data_dict` 内部落地 start/end 覆盖补拉
- end 侧使用 `end_backfill_min_step_bars`（默认 `5`）
- 覆盖失败最终仍由 `build_time_mapping` Fail-Fast
- 完成 WF 全链路回归与性能冒烟（2000 bars + 30 次优化）

完成标准（按阶段闸门）：
1. Phase 1 通过：所有已注册指标契约测试通过，`resolve_indicator_contracts` 与 pytest 结果一致。
2. Phase 2 通过：executor / searcher / ipynb 三条入口均只做一次预检且可稳定执行。
3. Phase 3 通过：mapping 覆盖校验稳定，WF 回归通过，不破坏现有单次回测与优化流程。

---

## 11. 统一错误分类（更新）

1. `INDICATOR_CONTRACT_INVALID`：指标缺少回调、回调返回非法、契约与输出不一致。
2. `WF_CONFIG_INVALID`：WF 参数非法（如 `min_warmup_bars < 0`、模式非法、参数链路不一致）。
3. `MAPPING_COVERAGE_INVALID`：mapping 首尾覆盖失败。
4. `SOURCE_DATA_INVALID`：原始 source 输入数据包含 `NaN/null`。
5. `WF_INDICATOR_NOT_READY`：指标非预热段不满足契约模式的就绪规则，或缺少 `base_data_key` 对应 warmup。
6. `WF_SOURCE_WARMUP_UNDERFLOW`：某 source 在窗口内可用左侧样本不足，无法满足 `required_warmup_count_s`。
