# WF 最小改动预热方案讨论摘要（逻辑链条闭环）

这份文档是本次任务的方案摘要，不是迁移文档。目标是以最小改动修复 WF 预热质量问题，并把“指标预热口径”先做成可验证、可复用的统一规范。

阅读标记：
- `【目标口径】`：本任务必须落地的规则。
- `【边界说明】`：本任务明确不处理或延后处理的内容。
- 全文统一策略：Fail-Fast，直接报错，不做静默回退。

---

## 0. 总体取舍（本次最终拍板）

【目标口径】
1. 不改回测引擎主链。
2. 不做全项目容器重构。
3. 先做“指标契约重构”，再接入 WF。
4. 移除白名单主机制，不再依赖 `wf_allow_internal_nan_indicators` 兜底（确认性声明：当前代码中该字段已不存在）。

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
6. 绑定 base 预热真值：
`indicator_warmup_bars_base = warmup_bars_by_source[base_data_key]`；缺失直接报错。

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

## 6. WF 过渡期与三模式（保留）

【目标口径】
1. 保留 `transition_bars/transition_range` 命名。
2. 保留三模式：`BorrowFromTrain` / `ExtendTest` / `NoWarmup`。
3. 运行时公式不变：
- `BorrowFromTrain` / `ExtendTest`：
`effective_transition_bars = max(indicator_warmup_bars_base, transition_bars, 1)`
- `NoWarmup`：
`effective_transition_bars = max(transition_bars, 1)`
4. 参数定义（统一）：
- `N`：全量 base K 线总数
- `T`：`train_bars`
- `X`：`transition_bars`（用户配置）
- `S`：`test_bars`
- `W`：`indicator_warmup_bars_base`（预检得到）
5. 有效过渡期长度：
- `BorrowFromTrain` / `ExtendTest`：`E = max(W, X, 1)`
- `NoWarmup`：`E = max(X, 1)`
6. 滚动步长固定：`step = S`（所有模式一致）。
7. `transition_bars` 必须显式配置且 `>= 1`。
8. 通用前置校验：
- `T >= 1`
- `S >= 2`（保证“测试段倒数第二根”注入点存在）
- `E >= 1`
- BorrowFromTrain 额外约束：`E <= T`（否则 `Transition` 起点会落到训练段起点之前，直接报错）
- 不满足直接报错（Fail-Fast）。
9. `E == 1` 合法且必须支持：
- 新注入规则下，`Transition` 只需要“最后一根注入锚点”，不再需要 `>= 2`；
- 已删除“Transition 倒数第二根离场注入”，所以 `transition_bars >= 1` 已充分。

### 6.1 BorrowFromTrain（借训练尾部做预热）

【目标口径】
1. 第 `i` 个窗口 base 起点：`base_start_i = i * step`。
2. 四段区间（半开区间）：
- `Train_i = [base_start_i, base_start_i + T)`
- `Transition_i = [base_start_i + T - E, base_start_i + T)`（与 `Train_i` 尾部重叠）
- `Test_i = [base_start_i + T, base_start_i + T + S)`
3. 窗口合法性：`base_start_i + T + S <= N`。
4. 语义说明：
- 过渡期来自训练尾部，不新增额外数据占用；
- 训练与过渡有重叠，测试段与训练段不重叠。

### 6.2 ExtendTest（扩展窗口，不借训练）

【目标口径】
1. 第 `i` 个窗口 base 起点：`base_start_i = i * step`。
2. 四段区间（半开区间）：
- `Train_i = [base_start_i, base_start_i + T)`
- `Transition_i = [base_start_i + T, base_start_i + T + E)`（与训练不重叠）
- `Test_i = [base_start_i + T + E, base_start_i + T + E + S)`
3. 窗口合法性：`base_start_i + T + E + S <= N`。
4. 语义说明：
- 过渡期来自训练之后的新数据；
- 数据占用更大，但训练与过渡严格隔离。

### 6.3 NoWarmup（关闭指标预热补全）

【目标口径】
1. `E = max(X, 1)`，不再使用 `W` 放大过渡期。
2. 区间公式与 `ExtendTest` 相同：
- `Train_i = [base_start_i, base_start_i + T)`
- `Transition_i = [base_start_i + T, base_start_i + T + E)`
- `Test_i = [base_start_i + T + E, base_start_i + T + E + S)`
- `base_start_i + T + E + S <= N`
3. 语义说明：
- 仅保留最小过渡机制与注入锚点，不做指标预热扩展；
- 仍保持 Fail-Fast，预检不通过就直接报错。

### 6.4 三模式统一注入与执行规则

【目标口径】
1. 跨窗判定来源固定为“上一窗口 `Test` 末根持仓状态”。
2. 判定公式（窗口 `i >= 1`）：
- `prev_test_last = Test_{i-1}.end - 1`
- 语义补充：
  - `Test_{i-1}` 使用半开区间 `[start, end)` 表示；
  - 因此 `end - 1` 就是“上一窗口测试段最后一根 K 线”的索引；
  - 这里的“测试段”指非预热测试数据，不是 `Transition` 段，也不是全量数据最后一根。
- 多头跨窗：`entry_long_price(prev_test_last)` 非空且 `exit_long_price(prev_test_last)` 为空
- 空头跨窗：`entry_short_price(prev_test_last)` 非空且 `exit_short_price(prev_test_last)` 为空
- 若多头与空头同时成立，直接报错（持仓冲突）。
3. 注入顺序（窗口 `i`）：
- 在 `Test_i` 倒数第二根注入双向离场（`exit_long=true`、`exit_short=true`）
- 若跨窗为多头：在 `Transition_i` 最后一根注入 `entry_long=true`
- 若跨窗为空头：在 `Transition_i` 最后一根注入 `entry_short=true`
- 若无跨窗持仓：不注入开仓
4. 第一窗没有上一窗，跨窗判定为 false，只保留测试段离场注入。
5. 第一窗注入规则（明确）：
- 不跳过全部注入；
- 仅跳过“跨窗开仓注入”（因为没有上一窗可判定）；
- 仍执行 `Test_0` 倒数第二根的双向离场注入（用于保持注入规则一致性与边界收敛）。
6. 每窗执行链固定：
- 先运行到 `Signals`（第一遍只到 `Signals`，不跑 `Backtest/Performance`）
- 按规则注入
- 注入后执行 `run_backtest -> analyze_performance`
7. `Transition` 段职责：
- 只用于指标预热与信号注入锚点；
- 不作为独立回测统计区；
- 窗口绩效只看 `Test` 非预热段。
8. 评估区间切片范围（必须明确）：
- 术语统一：`评估区间 = test_with_warmup = Transition + Test`
- BorrowFromTrain：
`evaluation_range_i = [base_start_i + T - E, base_start_i + T + S)`
- ExtendTest / NoWarmup：
`evaluation_range_i = [base_start_i + T, base_start_i + T + E + S)`
- 统一等价表达：`evaluation_range_i = [Transition_i.start, Test_i.end)`
9. 跨窗状态传递（runner 级约束）：
- 必须维护上一窗口测试末根持仓状态（例如 `prev_test_last_position`）
- 窗口 `i` 只读取该状态决定是否注入开仓
- 窗口 `i` 完成后，用 `Test_i` 末根回测结果更新状态给 `i+1`。
10. 资金列重建口径（与当前实现一致）：
- 窗口级 `Test` 结果不做资金列重建；
- `stitched` 阶段必须按窗口边界重建资金列。

---

## 7. Python/private 工作流影响评估（结论：改动小）

【目标口径】
1. 主流程顺序不变：`backtest -> optimize -> sensitivity -> walk_forward`。
2. 用户侧新增负担：
- 第一阶段需要关注指标契约落地；
- 入口显式调用一次预检。
3. pipeline/ipynb/searcher 仍是“入口加一次预检”，主调用链不改。

参数口径更新：
1. 工作流级参数：
- 现有 WF 参数：`train_bars/transition_bars/test_bars/inherit_prior/optimizer_config`
- 预热模式参数：`wf_warmup_mode`（Rust enum，经 PyO3 暴露，禁止字符串自由输入）
2. `wf_allow_internal_nan_indicators` 从工作流配置移除。

### 7.1 文件改动落点（最小集合）

【目标口径】
1. Python 侧（必须改）：
- `py_entry/private_strategies/config.py`：工作流参数入口，新增/透传 `wf_warmup_mode`
- `py_entry/runner/backtest.py`：新增 `validate_wf_indicator_readiness(...)`
- `py_entry/private_strategies/template.py`：pipeline 入口显式调用一次预检
- `py_entry/private_strategies/strategy_searcher.py`：`walk_forward` 分支前显式调用一次预检
- `py_entry/private_strategies/demo.ipynb`：增加显式预检单元
2. Rust 侧（仅当 `wf_warmup_mode` 需要入 `WalkForwardConfig` 时改）：
- `src/types/inputs/walk_forward.rs`

【明确不改动】
1. 不改数据请求协议（仍为 `since + limit`）。
2. 不改回测引擎主链。
3. 不改容器体系。
4. 不改 research 评估口径。

---

## 8. 分阶段落地顺序（更新）

【目标口径】
1. Phase 1（先做，指标规范化）：
- 每个指标补齐两个回调：`required_warmup_bars` + `warmup_mode`
- `resolve_indicator_contracts`（Rust + PyO3）落地
- 指标 pytest 专项按 Strict/Relaxed 规则全部通过

2. Phase 2（WF 接入与工作流贯通）：
- `validate_wf_indicator_readiness` 改为消费契约聚合结果
- Python 入口统一“显式预检一次”：`template.py`、`strategy_searcher.py`、`demo.ipynb`
- `wf_warmup_mode` 参数链路打通（private 配置 -> WF 调用）
- `wf_allow_internal_nan_indicators` 路径彻底移除
- 保持三模式与过渡期公式不变

3. Phase 3（数据覆盖优化 + 全链路回归）：
- `generate_data_dict` 内部落地 start/end 覆盖补拉
- end 侧使用 `end_backfill_min_step_bars`（默认 `5`）
- 覆盖失败最终仍由 `build_time_mapping` Fail-Fast
- 完成 WF 全链路回归与性能冒烟（2000 bars + 30 次优化）

完成标准（按阶段闸门）：
1. Phase 1 通过：所有已注册指标契约测试通过，`resolve_indicator_contracts` 与 pytest 结果一致。
2. Phase 2 通过：pipeline / searcher / ipynb 三条入口均只做一次预检且可稳定执行。
3. Phase 3 通过：mapping 覆盖校验稳定，WF 回归通过，不破坏现有单次回测与优化流程。

---

## 9. 统一错误分类（更新）

1. `INDICATOR_CONTRACT_INVALID`：指标缺少回调、回调返回非法、契约与输出不一致。
2. `WF_CONFIG_INVALID`：WF 参数非法（如 `transition_bars < 1`、模式非法、参数链路不一致）。
3. `MAPPING_COVERAGE_INVALID`：mapping 首尾覆盖失败。
4. `SOURCE_DATA_INVALID`：原始 source 输入数据包含 `NaN/null`。
5. `WF_INDICATOR_NOT_READY`：指标非预热段不满足契约模式的就绪规则，或缺少 `base_data_key` 对应 warmup。
