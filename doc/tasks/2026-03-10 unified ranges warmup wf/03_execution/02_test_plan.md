# 统一 Ranges / Warmup / WF 重构测试文档

对应文档：

1. [01_execution_plan.md](./01_execution_plan.md)
2. [03_execution_stages_and_acceptance.md](./03_execution_stages_and_acceptance.md)
3. [../00_meta/task_summary.md](../00_meta/task_summary.md)
4. [../02_spec/01_overview_and_foundation.md](../02_spec/01_overview_and_foundation.md)
5. [../02_spec/03_backtest_and_result_pack.md](../02_spec/03_backtest_and_result_pack.md)
6. [../02_spec/04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
7. [../02_spec/05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)

本文只保留阶段 gate 必需项：

1. 必须冻结哪些 contract
2. 阶段放行依赖哪些测试层
3. 必须写死哪些性能硬约束

本文里的层次再写死一次：

1. `2` 与 `3` 是阶段 gate 必需的 contract 与硬约束。
2. `4` 到 `7` 已拆到 [06_test_plan_supplementary.md](./06_test_plan_supplementary.md)，不参与阶段 gate。

测试计划和摘要文档保持同一套对象视角：

1. `WarmupRequirements`
2. `TimeProjectionIndex`
3. `RunArtifact`
4. `WalkForwardPlan`
5. `StitchedReplayInput`
6. `ResolvedRegimePlan`

这些名称在测试计划里只表示 contract 归属，不要求测试代码必须新增同名公开类型。

## 1. 测试目标

本次测试的目标不是“把完整工作流跑很多遍”，而是：

1. 先把文档里已经定死的真值固化成不变量测试。
2. 先用小样本、小窗口、少量优化轮次把高风险边界锁死。
3. 再用极少数完整 WF 回归用例检查 stitched replay、窗口链路与单段 schedule 等价性没有漂。
4. 对能直接由 Rust + PyO3 + `just stub` 生成 `.pyi` 的核心边界类型，不再为测试方便额外定义 Python 镜像类型；测试应直接消费 Rust 导出的真实类型与自动生成的存根。

本次测试优先防止三类 quietly wrong：

1. `ranges / mapping` 语义漂移
2. `extract_active(...)`、WF 切片、stitched 拼接的边界错误
3. `backtest_schedule` 重基、segmented replay 与跨窗注入的静默错位
4. `ignore_indicator_warmup` 误用后被当成正规预热口径结果

## 2. 必须 contract 测试分层

### 2.1 第一层：Builder / 容器不变量测试

这层优先级最高，必须先写。

目标：

1. 把 `DataPack / ResultPack / SourceRange` 的基础真值锁死。
2. 这层不依赖完整 WF。
3. 默认只用小样本数据。

建议新增或改造测试文件：

说明：

1. 下面保留的是 planning 阶段建议新增或改造的测试文件名。
2. 这些文件名用于表达覆盖意图，不等于当前仓库必须保留同名文件。
3. 当前仓库实际 gate 入口、路径漂移与覆盖吸收关系，统一以后验记录为准，见 `../04_review/04_execution_backfill_template.md`。

1. `py_entry/Test/backtest/test_data_pack_contract.py`
2. `py_entry/Test/backtest/test_result_pack_contract.py`
3. `py_entry/Test/backtest/test_strip_indicator_time_columns_contract.py`
4. `py_entry/Test/backtest/test_mapping_projection_contract.py`
5. `py_entry/Test/backtest/test_data_fetch_planner_contract.py`
6. `py_entry/Test/backtest/test_performance_contract.py`

最小必测项：

1. `build_data_pack(...)`
   - `mapping.columns[0] == \"time\"`
   - `set(mapping.columns[1:]) == S_keys`
   - `mapping.columns.len() == 1 + len(S_keys)`
   - 除 `time` 外列序无语义；测试不得依赖非 `time` 列顺序
   - `mapping.time` 严格递增
   - `mapping.time.dtype == Int64`
   - `mapping.time` 不允许存在 null
   - 对每个非时间列 `mapping[k]`：
     - `dtype == UInt32`
     - 不允许存在 null
   - `mapping.height() == source[base].height()`
   - `ranges[base].pack_bars == mapping.height()`
   - 若 `skip_mask` 存在：
     - 必须是单列表 `DataFrame`
     - 唯一合法列名是 `\"skip\"`
     - `skip_mask[\"skip\"].dtype == Boolean`
     - `skip_mask[\"skip\"]` 不允许存在 null
     - `skip_mask.height() == source[base].height()`
     - `skip_mask.height() == mapping.height()`
   - 对非法 `skip_mask` 必须直接 fail-fast：
     - 非单列表
     - 缺少 `\"skip\"` 列
     - `\"skip\"` dtype 不是 `Boolean`
     - `\"skip\"` 存在 null
   - 长度与 base 轴不一致
   - `warmup_bars + active_bars == pack_bars`
   - `DataPackFetchPlannerInput.effective_limit = 0` 必须直接 fail-fast 报错
   - base 首次有效段若 `base_effective_df.height() < effective_limit`，必须直接 fail-fast
   - 不允许为 base 再临时补一套右侧补拉逻辑去凑满 `effective_limit`
   - `resolve_source_interval_ms(source_key)` 必须有 dedicated contract：
     - `ohlcv_1m / ohlcv_4h / ohlcv_1d` 等合法 key 能解析出唯一正整数 `interval_ms`
     - 非法 `source_key`、非法周期值、非法周期单位、解析结果 `<= 0` 必须直接 fail-fast
   - shared warmup helper 链必须完整体现 `WarmupRequirements` 的 5 段语义：
     - `W_resolved / W_normalized / W_applied / W_backtest_exec_base / W_required`
     - 不允许把 `W_required` 实现成漏掉 `W_backtest_exec_base` 的 4 段简化版
2. `build_result_pack(...)`
   - `result.mapping.columns[0] == \"time\"`
   - `set(result.mapping.columns[1:]) == indicator_source_keys`
   - `result.mapping.columns.len() == 1 + len(indicator_source_keys)`
   - 除 `time` 外列序无语义；测试不得依赖非 `time` 列顺序
   - `result.mapping.time.dtype == Int64`
   - `result.mapping.time` 不允许存在 null
   - 对每个非时间列 `result.mapping[k]`：
     - `dtype == UInt32`
     - 不允许存在 null
   - `result.mapping.time == data.mapping.time`
   - `result.mapping[k] == data.mapping[k]`（对子集 `indicator_source_keys`）
   - `result.ranges[k] == data.ranges[k]`（对子集）
   - `result.base_data_key == data.base_data_key`
   - 若 `indicators[k]` 存在，必须先校验：
     - `indicators[k].height() == data.source[k].height()`
   - 若上游 `indicators[k]` 已经包含同名 `time` 列，必须直接报错
   - 若 `indicators[k]` 存在，`build_result_pack(...)` 必须为其补入 `time` 列
   - 补入后必须验证：
     - `result.indicators[k]["time"] == data.source[k]["time"]`
   - 后续依赖 `&ResultPack` 的 helper 只能从 `result.base_data_key` 读取 base 语义，不再依赖外层 `DataPack`
   - `has_leading_nan` 只允许保留在 `signals`
   - `backtest` 与 `performance` 不允许再感知该字段
   - `performance` 仍保持通用指标字典口径：`Option<HashMap<String, f64>>`；键集由 `PerformanceParams.metrics` 与 `PerformanceMetric` 决定
3. `strip_indicator_time_columns(...)`
   - 必须有 dedicated contract test
   - 缺少 `time` 列必须 fail-fast
   - 存在多个同名 `time` 列必须 fail-fast
   - 仅移除唯一 `time` 列，其余列名、行数、列顺序必须保持不变
   - 返回结果必须能直接作为 raw indicators 再喂给 `build_result_pack(...)`
4. `analyze_performance(...)`
   - `backtest.height() != data.mapping.height()` 必须 fail-fast
   - 外部只允许传完整 `DataPack + backtest`
   - 不允许把外部预切的 active-only `backtest` 当成正式输入
   - 内部切片只能读取：
     - `data.ranges[data.base_data_key].warmup_bars`
     - `data.ranges[data.base_data_key].pack_bars`
   - 时间列只能读取：
     - `data.mapping["time"][warmup..pack]`
   - 后续绩效统计只能基于内部 `active_backtest_with_time`
   - `has_leading_nan` 不允许进入绩效统计逻辑
   - 输出仍保持通用指标字典口径：`Option<HashMap<String, f64>>`
5. 时间投影 / coverage 共享真值链
   - `exact_index_by_time(...)`
     - 找不到目标时间必须 fail-fast
     - 同一 source 内若目标时间不唯一，必须 fail-fast
   - `map_source_row_by_time(...)`
     - 若给定时间无法 backward 映射到合法 source 行，必须 fail-fast
   - `map_source_end_by_base_end(...)`
     - `base_end_exclusive_idx = 0` 的边界语义必须单独锁死
     - 非空 `base` 区间若无法映射到合法 `end_exclusive`，必须 fail-fast
   - `validate_coverage(...)`
     - 空 `base` 区间语义必须单独锁死
     - 首覆盖不足必须 fail-fast
     - 尾覆盖不足必须 fail-fast
     - 不允许把 coverage 失败静默接受成截断、空结果或第二套宽松语义
   - coverage、单点时间投影与右边界投影所使用的 `interval_ms` 必须统一来自 `resolve_source_interval_ms(source_key)`，不允许出现第二套本地推导

### 2.1.1 第一层补充：`DataPackFetchPlanner` 状态机 contract

目标：

1. 把摘要 `02` 已写死的 planner 状态机边界锁成单独 contract。
2. 防止实现成“能跑通一次 happy path，但 quietly wrong”。

最小必测项：

1. `next_request() / ingest_response(...) / is_complete() / finish()` 的一致性：
   - 未完成前，`finish()` 必须 fail-fast
   - `is_complete() == false` 时，不允许提前 `finish()`
   - `is_complete() == true` 后，`next_request()` 不得再返回新的有效请求
2. `ingest_response(...)` 的结构性非法输入必须直接报错：
   - 缺少 `time` 列
   - `time` 列类型不是 `Int64`
   - `time` 列存在 null
   - `time` 列不是严格递增
   - `time` 列存在重复时间戳
   - `request.source_key` 与当前挂起请求不匹配
3. Python 空响应重试边界必须单独锁死：
   - 空 DF 最多重试 `2` 次
   - 重试后仍为空，Python 直接报错
   - 不允许把空快照继续喂给 Rust `ingest_response(...)`
4. 三段补拉状态机必须锁死：
   - `ensure_tail_coverage(...)`
   - `ensure_head_time_coverage(...)`
   - `ensure_head_warmup_bars(...)`
   对结构合法但覆盖不足的快照，必须继续补拉，而不是静默完成
5. 重试 / round 上限必须 fail-fast：
   - 任一 source 在达到状态机上限后仍不能满足尾覆盖、头覆盖或 warmup 条件，必须直接报错
6. `resolve_backtest_exec_warmup_base(wf_params.backtest)`
   - 必须在这一层就单独做 contract 测试
   - 对会影响 warmup 的可优化字段，锁死：
     - `optimize = false -> Param.value`
     - `optimize = true -> Param.max`
   - 不能把 `wf_params.backtest` 先手工物化成另一套 concrete params 再送进 helper
   - planner 只能消费这条已经冻结的共享 helper 口径，不允许在窗口层再解释第二套规则
7. `interval_ms`
   - planner 初始化对每个 `source_key` 的 `interval_ms` 必须直接复用 `resolve_source_interval_ms(source_key)`
   - 任一 key 解析失败必须在初始化阶段 fail-fast
8. `source_keys` 生成规则必须单独锁死：
   - 唯一公式是 `unique({base_data_key} ∪ {"ohlcv_" + timeframe})`
   - `base_data_key` 必须恰好通过这条公式进入 `source_keys`
   - `indicators_params` 中出现的 `source_key` 必须全部属于 `source_keys`
   - 不允许在 planner 初始化时再从别处派生第二套 `source_keys`
9. base 有效段长度 contract
   - 必须显式构造“非空但 `< effective_limit`”的 base 首次响应
   - 这类输入必须在 planner 阶段直接 fail-fast
   - 不允许把有效执行段静默缩短成 `< effective_limit`
10. 完成条件必须一致：
   - 只有所有 source 都满足共享基础 warmup、尾覆盖、头覆盖后，`is_complete()` 才能变成 `true`
   - `finish()` 构建出的 `DataPack` 必须与最后一轮内部状态一致，不允许再隐式补拉或重算第二套 planner 状态

### 2.2 第二层：`extract_active(...)` 专项测试

目标：

1. 锁死唯一显式例外路径。
2. 防止后续实现误走 builder 或漏掉 mapping 重基。
3. 锁死 `RunArtifact` 的同源配对边界。

建议新增测试文件：

1. `py_entry/Test/backtest/test_extract_active_contract.py`

最小必测项：

1. `RunArtifact` 语义必须成立：
   - `extract_active(...)` 的输入必须是一对同源 `DataPack / ResultPack`
   - 不允许把不同来源的容器与结果拼成伪配对继续切片
2. `new_result.mapping.time == new_data.mapping.time`
3. `new_result.ranges[base].pack_bars == new_result.mapping.height()`
4. 若 `signals / backtest` 存在，高度必须等于 `new_result.mapping.height()`
5. `new_result.indicators.keys() ⊆ new_data.source.keys()`
6. `new_result.base_data_key == new_data.base_data_key`
7. 对每个 `k ∈ new_result.indicators.keys()`：
   - `new_result.ranges[k] == new_data.ranges[k]`
   - `new_result.mapping[k] == new_data.mapping[k]`
   - `new_result.indicators[k]["time"] == new_data.source[k].time`
8. `performance` 直接继承，不重新计算
9. 若输入 `data.skip_mask` 存在：
   - `new_data.skip_mask.height() == new_data.mapping.height()`
   - `new_data.skip_mask["skip"]` 必须严格等于输入 `skip_mask` 在 base `active` 区间上的切片
   - `new_data.skip_mask` 仍然只挂在新的 base 轴上
   - 不允许按旧 pack 轴、source 轴或第二套 warmup 语义重切

### 2.3 第三层：WF 窗口规划与切片测试

这层先测“窗口索引与切片”，不要一上来就跑完整优化。

建议新增测试文件 / 落点：

1. Rust 同模块单测：
   - `src/backtest_engine/walk_forward/plan.rs`
   - `src/backtest_engine/walk_forward/next_window_hint.rs`
2. Python contract：
   - `py_entry/Test/walk_forward/test_window_slice_contract.py`
   - `py_entry/Test/walk_forward/test_wf_ignore_indicator_warmup_contract.py`

最小必测项：

1. `step = test_active_bars`
2. `P_train = 0` 时：
   - `train_warmup` 允许空区间
3. `warmup_mode` 的几何差异必须作为独立 contract 锁死：
   - `BorrowFromTrain` 下：
     - `test_warmup = [P_train + T - P_test, P_train + T)`
     - `test_active = [P_train + T, P_train + T + S)`
     - `test_warmup` 与 `train_active` 尾部允许重叠
   - `ExtendTest` 下：
     - `test_warmup = [P_train + T, P_train + T + P_test)`
     - `test_active = [P_train + T + P_test, P_train + T + P_test + S)`
     - `train_active / test_warmup / test_active` 在 base 轴上必须顺排
   - 不允许把两种 mode 静默收敛成同一套窗口公式
4. `BorrowFromTrain` 的可行性约束必须单独锁死：
   - `P_test <= T`
   - 若 `P_test > T`，必须 fail-fast
   - 不允许静默截断、回退到 `ExtendTest` 或接受成未定义行为
5. 第 `0` 窗：
   - `train_warmup / train_active / test_warmup` 不足直接报错
   - `test_active` 允许截短
6. `test_active < 3`
   - 第 `0` 窗报错
   - 后续最后一窗不生成
   - `test_active = 2` 也必须显式视为非法：
     - carry 信号位于 active 第一根
     - 继承开仓在第二根 active bar 开盘执行
     - 尾部强平写在 `pack_bars - 2`
     - 三条语义在 `active_bars = 2` 时会冲突
7. `slice_data_pack_by_base_window(...)`
   - `source_ranges` 直接切旧 `DataPack.source`
   - `ranges_draft` 直接写新 pack 的 `ranges`
   - `mapping` 由 `build_data_pack(...)` 统一重建
   - 若原 `DataPack.skip_mask` 存在：
     - 新窗口 `DataPack.skip_mask.height() == new_pack.mapping.height()`
     - `new_pack.skip_mask["skip"]` 必须严格等于旧 `skip_mask` 在当前窗口 base `pack` 区间上的切片
     - 不允许沿用旧 `skip_mask` 高度，也不允许按 source 轴或第二套 base 区间重切
8. `build_window_indices(...)`
   - 必须返回 `WalkForwardPlan`
   - `WalkForwardPlan` 必须只承接：
     - `required_warmup_by_key`
     - `windows`
   - `WindowPlan` 必须只绑定：
     - `window_idx`
     - `indices: WindowIndices`
   - 不允许在 `WindowPlan` 上重复挂一份 `test_active_base_row_range`
   - `WindowIndices` 必须显式产出 `test_active_base_row_range`
   - 它表示当前窗口 `test_active` 在原始 WF 输入 `DataPack.base` 轴上的绝对半开区间
   - 后续 stitched `backtest_schedule` 只能消费这份区间做重基
   - 必须构造至少一个 coverage 左扩场景：
     - 某个 `k` 的 `warmup_by_key[k] > W_required[k]`
     - 该放大量必须来自当前窗口真实 coverage / source 投影，而不是第二套手工加值
     - `ranges_draft[k].warmup_bars` 必须取放大后的 `warmup_by_key[k]`
     - 进入真正切片后不允许再回退到 `W_required[k]` 重新裁数据
9. `best_params`
   - 必须单独做 contract 测试
   - 与 `rebuild_param_set(...)` 对齐：保留原始参数树形状与 `min / max / step / optimize`，只覆盖各叶子 `.value`
   - 后续 stitched / replay 消费必须只认 `.value`
   - 不允许把 `best_params` 当成搜索空间再按 `.optimize / .max / .min / .step` 二次解释
10. `min_warmup_bars`
   - 只作为 WF-local constraint 测试
   - 不反向要求初始 planner 前推处理
11. `WindowMeta` 的 `*_time_range`
   - 必须单独做 contract 测试
   - 统一按已经物化好的 `train_pack_data / test_pack_data` 的 base `time` 列与 `ranges[base]` 真值生成
   - 统一只读取 `pack.mapping["time"]`
   - 不允许从 `full_data` 反推
   - 不允许从 `WindowPlan` 的 bars / range 反推
   - `warmup_time_range`
     - 空区间映射为 `None`
     - 非空区间取对应区间首尾两根 bar 的时间
   - `active_time_range / pack_time_range`
     - 都必须非空
     - 都取对应区间首尾两根 bar 的时间
   - 不允许在不同调用点手写第二套时间范围生成逻辑
12. `NextWindowHint`
   - 必须作为独立 contract 锁死
   - 完整窗口场景下：
     - `last_window_is_complete = true`
     - `expected_window_switch_time_ms = last_window.meta.test_active_time_range.end`
     - `eta_days = 0`
   - 多窗口且最后一窗不完整时：
     - 必须按历史完整窗口 `test_active_time_range` 跨度的中位数做 heuristic
   - 单窗口 fallback 时：
     - 必须使用
       - `observed_test_active_span_ms`
       - `config.test_active_bars / observed_test_active_bars`
       做比例估算
   - 若 `observed_test_active_bars < 3`，必须 fail-fast
   - `based_on_window_id` 必须等于最后一窗 `window_id`
   - 不允许把 `NextWindowHint` 静默降级成空值、固定 0 或第二套估算公式
13. 阶段 D1 的窗口规划 / `NextWindowHint` contract
   - 默认落到 Rust 同模块单测
   - 不要求为了阶段 D1 gate 额外新增 PyO3 专用入口
   - 若阶段 E 还需要 Python 黑盒回归，再单独补 `walk_forward` 端到端测试
14. `build_window_time_ranges(...)`
   - 必须作为 dedicated helper 单独测试
   - 不允许在 `WindowMeta` 填充点、stitched 组装点或 Python 包装层再手写第二套范围生成逻辑
15. `ignore_indicator_warmup = false / true`
   - 必须进入阶段 D2 gate，而不是只留在补充测试
   - `true` 时只能把 `applied_contract_warmup_by_key` 截获为 `0`
   - `backtest_exec_warmup_base` 与 `required_warmup_by_key[base]` 的执行预热分量不受影响
   - `false / true` 两种配置都必须在同一小样本窗口规划链路上可运行
   - `true` 只作为 dedicated contract，用来锁死开关语义；不把它当成正规预热正确性基线

### 2.4 第四层：WF 跨窗注入测试

目标：

1. 锁死当前最容易 quietly wrong 的流程段。
2. 这层只测注入规则，不需要大数据量。

继续使用并扩展：

1. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`

最小必测项：

1. `detect_last_bar_position(...)`
   - `Ok(Some(Long)) / Ok(Some(Short)) / Ok(None)`
   - 双边同时成立直接报错
2. `build_carry_only_signals(...)`
   - 只允许注入测试 active 第一根同向开仓
   - 不允许提前注入窗口尾部强平
   - carry 注入行必须验证 4 个布尔列的整行真值
   - 当前正式语义接受保守延迟：
     - 这笔跨窗继承开仓会在第二根 active bar 开盘执行
   - 因而这层 contract 还必须显式验证：
     - `active_bars = 2` 非法
     - 最小合法 `active_bars = 3`
3. `build_final_signals(...)`
   - 只在 `carry_only_signals` 基础上追加倒数第二根双向离场
   - 强平行必须验证 4 个布尔列的整行真值
4. `natural_test_pack_backtest_result`
   - 必须只由 `carry_only_signals` 跑到 `Backtest` 得到
   - 不进入正式返回值，不进入 stitched，不参与正式 performance
5. `has_cross_boundary_position`
   - 必须等于 `detect_last_bar_position(natural_test_pack_backtest_result.backtest).is_some()`
6. `prev_last_bar_position`
   - 必须在窗口主循环里按顺序回写给下一窗
   - 来源必须是 `natural_test_pack_backtest_result.backtest`
7. `final_test_pack_result`
   - 必须只由 `final_signals` 跑到 `Performance` 得到
   - 不能再被用作下一窗 carry 来源
   - 必须显式验证：即使 `final_test_pack_result.backtest` 与 `natural_test_pack_backtest_result.backtest` 在末根状态上不同，下一窗 carry 来源仍然只能读取 `natural_test_pack_backtest_result.backtest`
8. `optimize_metric`
   - 必须只来自 `WalkForwardConfig.optimizer_config.optimize_metric`
   - 默认值 contract 固定为 `OptimizeMetric::CalmarRatioRaw`
   - `WindowMeta` 不再保留该字段
   - 只允许在 `WalkForwardResult.optimize_metric` 保留一次
9. `min_warmup_bars`
   - 默认值 contract 固定为 `0`
   - 只有显式配置为更大值时，才允许改变 `P_train / P_test` 的额外下界
10. `settings.execution_stage / settings.return_only_final`
   - 在 WF 内部必须被忽略并由阶段逻辑强制覆盖
   - 不允许外部单次回测返回控制反向影响 `raw_signal_stage_result / natural_test_pack_backtest_result / final_test_pack_result` 的必需字段产出
11. `ResultPack` 阶段产出契约
   - `raw_signal_stage_result` 必须至少有 `indicators + signals`
   - `natural_test_pack_backtest_result` 必须至少有 `backtest`
   - `final_test_pack_result` 必须有完整 `indicators + signals + backtest + performance`
   - stitched 正式信号来源必须锁死为各窗口 `test_active_result.signals`
   - 不允许再回退去拼完整 `final_signals`

### 2.5 第五层：stitched / segmented replay 专项测试

目标：

1. 锁死 stitched 真值来源、`backtest_schedule` 重基和 `StitchedReplayInput` 输入契约。
2. 锁死最终 stitched `ResultPack` 仍统一走 `strip_indicator_time_columns(...) -> build_result_pack(...)`。
3. 锁死单段 schedule 与旧单次回测 reference 的等价性基线。
4. 锁死 `ResolvedRegimePlan` 所承接的 schedule contract 不会在实现中被拆散漂移。
5. 锁死最终 PyO3 / stub 公共边界只暴露新名，不残留旧字段与旧类型。

建议新增测试文件：

说明：

1. 本节保留 planning 阶段建议新增的测试文件名与覆盖方向。
2. 若后续执行与当前仓库出现路径漂移、替代 gate 或覆盖吸收，统一在 `../04_review/04_execution_backfill_template.md` 记录。

1. `py_entry/Test/walk_forward/test_stitched_contract.py`
2. `src/backtest_engine/backtester/tests.rs`
3. `src/backtest_engine/walk_forward/stitch.rs` 中对应的 Rust 单测
4. `py_entry/Test/test_public_api_stub_contract.py`

其中：

1. 阶段 D2 的 stitched 上游输入 contract 默认走 Rust 单测：
   - `src/backtest_engine/walk_forward/stitch.rs`
   - 不要求为了阶段 D2 gate 额外暴露 PyO3 入口
2. `test_stitched_contract.py` 表示阶段 E 期望存在一条公开黑盒回归，用于覆盖 segmented replay 与最终 stitched 结果 contract。
3. `test_public_api_stub_contract.py` 在阶段 E 作为公共边界 smoke test：
   - 先跑 `just stub`
   - 再检查生成的 `.pyi` 与公开导出只保留新口径

最小必测项：

1. `ResolvedRegimePlan` 的 contract 必须整体成立：
   - `BacktestParamSegment`
   - contiguity
   - schedule policy
   - output schema
   - selector construction
   - 不允许实现时把这几条约束拆成互相漂移的平行规则
2. `StitchedReplayInput` 必须作为 `04 -> 05` 的正式边界对象存在，并只收纳 stitched 阶段已经生成的正式输入真值：
   - `stitched_data`
   - `stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
   - `stitched_indicators_with_time`
   - replay 直接消费前四类
   - 最终 stitched `ResultPack` 构建再消费 `stitched_indicators_with_time`
   - `stitched_indicators_with_time` 的键集固定等于正式 `indicator_source_keys`
   - 不采用 stitched 阶段现取并集键集的写法
   - 任一窗口若缺少某个 `indicator_source_keys` 中的 `k`，必须 fail-fast
3. `backtest_schedule` 的每段 `start_row / end_row` 必须由 `window_results[i].meta.test_active_base_row_range` 做减法重基得到：
   - `base0 = first_window.test_active_base_row_range.start`
   - `start_row_i = original_start_i - base0`
   - `end_row_i = original_end_i - base0`
4. `backtest_schedule` 必须满足 contiguity：
   - 第一个 `start_row == 0`
   - 相邻段首尾相接
   - 最终 `last_end_row == stitched_signals.height()`
   - 最终 `last_end_row == stitched_data.mapping.height()`
   - 若有 `stitched_atr_by_row`，长度也必须等于 `last_end_row`
5. 最终 `WalkForwardResult.stitched_result.meta.backtest_schedule` 必须与 replay 实际使用的 `backtest_schedule` 一致，不能只作为 `04 -> 05` 的临时输入后丢弃。
6. `stitched_atr_by_row` 必须按唯一算法生成：
   - 先按 unique `resolved_atr_period` 计算覆盖首段执行预热的左扩 ATR cache
   - 再按 `backtest_schedule` 做 segment 级 slice + concat
   - 不允许按 row 逐行现算
   - 不允许直接在 active-only `stitched_data.base` 上现算后当成正式答案
   - 还必须校验逐段语义：
     - 若某段启用 ATR 逻辑，则该段每一行都必须等于对应 `resolved_atr_period` 的左扩 full-series cache 在投影回 stitched 行轴后的值
     - 若某段不启用 ATR 逻辑，则该段切片必须为 `null`
   - 必须补一条首段 regression：
     - 构造一个首段启用 ATR 风控、且 `atr_period > 2` 的用例
     - 证明“active-only 直接现算”的前几行结果与正式答案不同
     - 正式答案必须等于左扩上下文投影版
7. `WalkForwardResult.stitched_result.result.mapping.time == stitched_data.mapping.time`
8. `WalkForwardResult.stitched_result.result.indicators[k]["time"] == stitched_data.source[k].time`
9. mapping 语义投影时间一致
10. 非 base `indicators[k]`
   - 0 根重叠：直接拼
   - 1 根重叠：后窗口覆盖前窗口
11. 多窗口 stitched carry 语义必须单独锁成一条端到端 contract：
   - 构造至少两个相邻窗口
   - 第一窗 `natural_test_pack_backtest_result` 末根仍有持仓
   - 第二窗 stitched 正式输入信号必须直接来自 `test_active_result.signals`
   - 第二窗 `active 区间` 第一根必须保留 carry 开仓信号
   - stitched replay 的正式语义必须显式断言：
     - 第二窗 `active 区间` 第一根只保留 carry 信号，不完成继承开仓
     - 第二窗 `active 区间` 第二根开盘才完成继承开仓
   - 也就是说，这条测试锁的不是旧的无缝边界语义，而是当前文档已经写死的保守延迟语义
12. 这条 stitched carry contract 还必须额外验证一件事：
   - carry 语义只依赖 `test_active_result.signals`
   - 不依赖已经被 `extract_active(...)` 裁掉的 warmup 行
   - 否则 stitched 输入虽然长度和 schedule 都对，跨窗语义仍可能 quietly wrong
13. stitched / WF 这条链还必须显式覆盖最小合法长度约束：
   - `active_bars = 2` 必须 fail-fast
   - `active_bars = 3` 是当前正式语义下的最小合法 case
   - >1 根重叠：直接报错
14. 最终 stitched `ResultPack` 必须统一走：
   - `stitched_indicators_with_time -> strip_indicator_time_columns(...) -> build_result_pack(...)`
   - 不允许绕过 builder 直接手写最终结果
   - `WalkForwardResult.stitched_result.result.performance` 仍保持通用指标字典口径：`Option<HashMap<String, f64>>`；键集由 `performance_params.metrics` 与 `PerformanceMetric` 决定
15. multi-segment output schema 的默认值 contract 必须单独锁死：
   - 当前按 segment 启停变化的可选列包括 `atr` 与各类 `f64` 风险价格列
   - 未启用 segment 的默认值统一为 `NaN`
   - 需要显式验证列集合、列顺序、dtype 与默认值同时成立
   - 不能把默认值静默实现成 `0.0`、`null` 或其他占位值
16. `run_backtest_with_schedule(...)`
   - 多段 schedule 的 contiguity 校验
   - 单段 schedule 退化路径
   - `validate_schedule_atr_contract(...)` 必须作为独立 contract 锁死：
     - 若任一 segment 的 `params.validate_atr_consistency()? == true`，则 `atr_by_row` 必须是 `Some(...)`
     - 若所有 segment 的 `params.validate_atr_consistency()? == false`，则 `atr_by_row` 必须是 `None`
     - 若 `atr_by_row.is_some()`，其长度必须严格等于 `stitched_data.mapping.height()`
     - 不允许把 `atr_by_row` 静默接受成“有也行、没有也行”的未定义行为
   - `validate_backtest_param_schedule_policy(...)` 必须作为独立 contract 锁死：
     - 对 `initial_capital / fee_fixed / fee_pct`，构造跨 segment 漂移 case，必须 fail-fast
     - 对文档明确允许 `segment_vary = true` 的字段，构造跨 segment 变化 case，必须允许通过
     - 不允许出现“未显式列入 policy、但实现里静默接受或静默拒绝”的字段
17. multi-segment output schema 必须作为独立 contract 锁死：
   - 列集合必须等于所有 segment 功能列的并集
   - 列顺序必须与 `build_schedule_output_schema(schedule)` 的唯一算法一致：
     - 先固定单段回测 schema 的基底列顺序
     - 再按预定义可选列顺序过滤出并集列
   - 各列 dtype 必须稳定，不允许因某段未启用而漂移
   - 未启用 segment 的功能列必须写入文档定义的非激活态默认值，不能留成未定义行为
   - 单段 schedule 必须退化成当前固定 schema，不允许凭空多列
18. `src/backtest_engine/backtester/tests.rs` 必须至少覆盖：
   - `ParamsSelector`
   - `validate_schedule_contiguity(...)`
   - `validate_backtest_param_schedule_policy(...)`
   - `build_schedule_output_schema(...)`
   这些 Rust 单测属于阶段 E 的最小必测项，不允许只用 Python 端到端回归替代
19. 阶段 gate 使用的 Rust dedicated contract test 必须采用精确测试名，不允许依赖模糊 substring 过滤：
   - `test_build_window_indices_contract`
   - `test_next_window_hint_contract`
   - `test_build_window_time_ranges_contract`
   - `test_stitched_replay_input_contract`
   - `test_wf_signal_injection_contract`
   - `test_ignore_indicator_warmup_contract`
   - `test_params_selector_contract`
   - `test_validate_schedule_contiguity_contract`
   - `test_validate_backtest_param_schedule_policy_contract`
   - `test_build_schedule_output_schema_contract`
20. Rust 等价性测试：
   - 先在旧 `run_backtest(...)` 上清掉 `has_leading_nan` 旧作用链
   - 再冻结成 `legacy_run_backtest_reference(...)`
   - 与新的 `run_backtest(...)` 做严格逐项对比
21. 公共 PyO3 / stub 边界必须有 dedicated smoke test：
   - `just stub` 后，`test_public_api_stub_contract.py` 必须至少锁死：
     - 新公共名存在：
       - `DataPack`
       - `ResultPack`
       - `SourceRange`
     - `WalkForwardConfig` 只保留最终字段口径
     - 旧公共名或旧字段不存在：
       - `DataContainer`
       - `BacktestSummary`
       - `inherit_prior`
       - `transition_*`
       - `WfWarmupMode::NoWarmup`

### 2.6 第六层：少量完整 WF 回归

这层数量必须少，只做最终回归。

继续使用并扩展：

1. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

建议保留的完整回归类型：

1. stitched 边界无事件时资金不出现断崖
2. 单窗口退化场景下，`backtest_schedule` 必须退化成单段 schedule，最终 stitched 必须与该窗口的 `test_active_result` 等价，而不是与完整 `test_pack_result` 等价
3. 无交易场景资金保持常数
4. 同 seed 同配置结果可复现
5. `ignore_indicator_warmup = false / true` 的对照实验链路可运行，但 `true` 不作为严格预热正确性测试

## 3. 必须性能约束

这部分必须写死，避免后面测试越来越慢。

默认规则：

1. 合同测试优先小样本：
   - `num_bars` 默认优先 `200~600`
2. 合同测试优先小窗口：
   - `train_active_bars / test_active_bars` 只取覆盖逻辑所需最小值
3. 优化轮次默认压低：
   - `optimizer_rounds` 优先 `2~8`
4. 只有少数完整回归测试允许：
   - `1000+ bars`
   - `20+ optimizer rounds`
5. 不允许把“完整大样本 WF”当成主力测试手段
6. `ignore_indicator_warmup = true` 的测试不增加额外大样本，只保留 1~2 个小样本对照用例

原因：

1. 本次重构最大的风险是语义漂移，不是算力不够。
2. 大多数 quietly wrong 都能用小样本 contract test 提前抓到。
3. 完整 WF 只负责兜底回归，不负责覆盖全部边界。

建议补充内容见：

1. [06_test_plan_supplementary.md](./06_test_plan_supplementary.md)
