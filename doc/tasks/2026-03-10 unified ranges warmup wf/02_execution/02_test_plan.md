# 统一 Ranges / Warmup / WF 重构测试文档

对应文档：

1. [01_execution_plan.md](./01_execution_plan.md)
2. [../01_summary/task_summary.md](../01_summary/task_summary.md)
3. [../01_summary/01_overview_and_foundation.md](../01_summary/01_overview_and_foundation.md)
4. [../01_summary/03_backtest_and_result_pack.md](../01_summary/03_backtest_and_result_pack.md)
5. [../01_summary/04_walk_forward_and_stitched.md](../01_summary/04_walk_forward_and_stitched.md)
6. [../01_summary/05_segmented_backtest_truth_and_kernel.md](../01_summary/05_segmented_backtest_truth_and_kernel.md)

本文只回答四件事：

1. 这次重构测试什么
2. 先测哪些工具函数
3. WF 测试怎么控性能
4. 测试文件建议落在哪

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

## 2. 当前测试现状总结

从现有测试看，项目已经形成了三条比较好的习惯：

1. 偏 contract test / regression guard，而不是大而全黑盒乱跑。
2. 通过 `py_entry/Test/shared/backtest_builders.py` 复用共享构造器，避免大段测试样板代码。
3. WF 测试已经有性能意识，但后续新方案仍然要进一步压小默认数据量与优化轮次。

当前现有测试里，最值得继续复用的风格是：

1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
2. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
3. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`
4. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
5. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

## 3. 推荐保留的 PyO3 测试工具函数

为了让测试文档和测试代码都更好写，建议保留少量稳定、可测试、不会污染主工作流的 PyO3 工具函数。

推荐保留：

1. `build_mapping_frame(...)`
2. `build_data_pack(...)`
3. `build_result_pack(...)`
4. `slice_data_pack_by_base_window(...)`
5. `extract_active(...)`

保留理由：

1. 它们本身就是正式真值入口或高风险切片入口。
2. 用它们可以直接写小样本 contract test，不必每次都跑完整 WF。
3. 这些函数的输入输出稳定、契约清楚，适合长期保留。
4. 其中 `build_mapping_frame(...)` 需要特别区分：
   - 在生产链路里仍只由 `build_data_pack(...)` 调用
   - 但对测试 / 调试层允许保留 PyO3 暴露，不视为第二套业务入口

不建议为了测试而暴露的函数：

1. 只服务单个临时实现细节的内部 helper
2. 会诱导调用方绕开主工作流的半成品构造函数
3. 没有稳定输入输出、后续很可能继续改名或改语义的内部状态函数

## 4. 测试分层

### 4.1 第一层：Builder / 容器不变量测试

这层优先级最高，必须先写。

目标：

1. 把 `DataPack / ResultPack / SourceRange` 的基础真值锁死。
2. 这层不依赖完整 WF。
3. 默认只用小样本数据。

建议新增或改造测试文件：

1. `py_entry/Test/backtest/test_data_pack_contract.py`
2. `py_entry/Test/backtest/test_result_pack_contract.py`
3. `py_entry/Test/backtest/test_mapping_projection_contract.py`
4. `py_entry/Test/backtest/test_data_fetch_planner_contract.py`

最小必测项：

1. `build_data_pack(...)`
   - `mapping.time` 严格递增
   - `mapping.height() == source[base].height()`
   - `ranges[base].pack_bars == mapping.height()`
   - `warmup_bars + active_bars == pack_bars`
   - `DataPackFetchPlannerInput.effective_limit = 0` 必须直接 fail-fast 报错
2. `build_result_pack(...)`
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
3. 三个统一时间工具函数
   - `exact_index_by_time(...)`
   - `map_source_row_by_time(...)`
   - `map_source_end_by_base_end(...)`
   输入输出必须和文档一致

### 4.1.1 第一层补充：`DataPackFetchPlanner` 状态机 contract

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
6. 完成条件必须一致：
   - 只有所有 source 都满足共享基础 warmup、尾覆盖、头覆盖后，`is_complete()` 才能变成 `true`
   - `finish()` 构建出的 `DataPack` 必须与最后一轮内部状态一致，不允许再隐式补拉或重算第二套 planner 状态

### 4.2 第二层：`extract_active(...)` 专项测试

目标：

1. 锁死唯一显式例外路径。
2. 防止后续实现误走 builder 或漏掉 mapping 重基。

建议新增测试文件：

1. `py_entry/Test/backtest/test_extract_active_contract.py`

最小必测项：

1. `new_result.mapping.time == new_data.mapping.time`
2. `new_result.ranges[base].pack_bars == new_result.mapping.height()`
3. 若 `signals / backtest` 存在，高度必须等于 `new_result.mapping.height()`
4. `new_result.indicators.keys() ⊆ new_data.source.keys()`
5. `new_result.base_data_key == new_data.base_data_key`
6. 对每个 `k ∈ new_result.indicators.keys()`：
   - `new_result.ranges[k] == new_data.ranges[k]`
   - `new_result.mapping[k] == new_data.mapping[k]`
   - `new_result.indicators[k]["time"] == new_data.source[k].time`
7. `performance` 直接继承，不重新计算

### 4.3 第三层：WF 窗口规划与切片测试

这层先测“窗口索引与切片”，不要一上来就跑完整优化。

建议新增测试文件：

1. `py_entry/Test/walk_forward/test_window_indices_contract.py`
2. `py_entry/Test/walk_forward/test_window_slice_contract.py`

最小必测项：

1. `step = test_active_bars`
2. `P_train = 0` 时：
   - `train_warmup` 允许空区间
3. 第 `0` 窗：
   - `train_warmup / train_active / test_warmup` 不足直接报错
   - `test_active` 允许截短
4. `test_active < 3`
   - 第 `0` 窗报错
   - 后续最后一窗不生成
   - `test_active = 2` 也必须显式视为非法：
     - carry 信号位于 active 第一根
     - 继承开仓在第二根 active bar 开盘执行
     - 尾部强平写在 `pack_bars - 2`
     - 三条语义在 `active_bars = 2` 时会冲突
5. `slice_data_pack_by_base_window(...)`
   - `source_ranges` 直接切旧 `DataPack.source`
   - `ranges_draft` 直接写新 pack 的 `ranges`
   - `mapping` 由 `build_data_pack(...)` 统一重建
6. `build_window_indices(...)`
   - 必须显式产出 `test_active_base_row_range`
   - 它表示当前窗口 `test_active` 在原始 WF 输入 `DataPack.base` 轴上的绝对半开区间
   - 后续 stitched `backtest_schedule` 只能消费这份区间做重基
7. `resolve_backtest_exec_warmup_base(wf_params.backtest)`
   - 必须单独做 contract 测试
   - 对会影响 warmup 的可优化字段，锁死：
     - `optimize = false -> Param.value`
     - `optimize = true -> Param.max`
   - 不能把 `wf_params.backtest` 先手工物化成另一套 concrete params 再送进 helper
8. `best_params`
   - 必须单独做 contract 测试
   - 与 `rebuild_param_set(...)` 对齐：保留原始参数树形状与 `min / max / step / optimize`，只覆盖各叶子 `.value`
   - 后续 stitched / replay 消费必须只认 `.value`
   - 不允许把 `best_params` 当成搜索空间再按 `.optimize / .max / .min / .step` 二次解释
9. `min_warmup_bars`
   - 只作为 WF-local constraint 测试
   - 不反向要求初始 planner 前推处理

### 4.4 第四层：WF 跨窗注入测试

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
   - 必须只来自 `WalkForwardConfig.optimize_metric`
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

### 4.5 第五层：stitched / segmented replay 专项测试

目标：

1. 锁死 stitched 真值来源、`backtest_schedule` 重基和 segmented replay 输入契约。
2. 锁死最终 stitched `ResultPack` 仍统一走 `strip_indicator_time_columns(...) -> build_result_pack(...)`。
3. 锁死单段 schedule 与旧单次回测 reference 的等价性基线。

建议新增测试文件：

1. `py_entry/Test/walk_forward/test_stitched_contract.py`
2. `src/backtest_engine/backtester/tests.rs`

最小必测项：

1. `backtest_schedule` 的每段 `start_row / end_row` 必须由 `window_results[i].meta.test_active_base_row_range` 做减法重基得到：
   - `base0 = first_window.test_active_base_row_range.start`
   - `start_row_i = original_start_i - base0`
   - `end_row_i = original_end_i - base0`
2. `backtest_schedule` 必须满足 contiguity：
   - 第一个 `start_row == 0`
   - 相邻段首尾相接
   - 最终 `last_end_row == stitched_signals.height()`
   - 最终 `last_end_row == stitched_data.mapping.height()`
   - 若有 `stitched_atr_by_row`，长度也必须等于 `last_end_row`
3. 最终 `WalkForwardResult.stitched_result.meta.backtest_schedule` 必须与 replay 实际使用的 `backtest_schedule` 一致，不能只作为 `04 -> 05` 的临时输入后丢弃。
4. `stitched_atr_by_row` 必须按唯一算法生成：
   - 先按 unique `resolved_atr_period` 计算 stitched base 全量 ATR cache
   - 再按 `backtest_schedule` 做 segment 级 slice + concat
   - 不允许按 row 逐行现算
   - 还必须校验逐段语义：
     - 若某段启用 ATR 逻辑，则该段每一行都必须等于对应 `resolved_atr_period` 的 full-series cache 在同一绝对行号上的值
     - 若某段不启用 ATR 逻辑，则该段切片必须为 `null`
5. `stitched_result.mapping.time == stitched_data.mapping.time`
6. `stitched_result.indicators[k]["time"] == stitched_data.source[k].time`
7. mapping 语义投影时间一致
8. 非 base `indicators[k]`
   - 0 根重叠：直接拼
   - 1 根重叠：后窗口覆盖前窗口
9. 多窗口 stitched carry 语义必须单独锁成一条端到端 contract：
   - 构造至少两个相邻窗口
   - 第一窗 `natural_test_pack_backtest_result` 末根仍有持仓
   - 第二窗 stitched 正式输入信号必须直接来自 `test_active_result.signals`
   - 第二窗 `active 区间` 第一根必须保留 carry 开仓信号
   - stitched replay 的正式语义必须显式断言：
     - 第二窗 `active 区间` 第一根只保留 carry 信号，不完成继承开仓
     - 第二窗 `active 区间` 第二根开盘才完成继承开仓
   - 也就是说，这条测试锁的不是旧的无缝边界语义，而是当前文档已经写死的保守延迟语义
10. 这条 stitched carry contract 还必须额外验证一件事：
   - carry 语义只依赖 `test_active_result.signals`
   - 不依赖已经被 `extract_active(...)` 裁掉的 warmup 行
   - 否则 stitched 输入虽然长度和 schedule 都对，跨窗语义仍可能 quietly wrong
11. stitched / WF 这条链还必须显式覆盖最小合法长度约束：
   - `active_bars = 2` 必须 fail-fast
   - `active_bars = 3` 是当前正式语义下的最小合法 case
   - >1 根重叠：直接报错
9. 最终 stitched `ResultPack` 必须统一走：
   - `stitched_indicators_with_time -> strip_indicator_time_columns(...) -> build_result_pack(...)`
   - 不允许绕过 builder 直接手写最终结果
10. multi-segment output schema 的默认值 contract 必须单独锁死：
   - 当前按 segment 启停变化的可选功能列全部是 `f64` 风险价格列
   - 未启用 segment 的默认值统一为 `NaN`
   - 需要显式验证列集合、列顺序、dtype 与默认值同时成立
   - 不能把默认值静默实现成 `0.0`、`null` 或其他占位值
10. `run_backtest_with_schedule(...)`
   - 多段 schedule 的 contiguity 校验
   - 单段 schedule 退化路径
11. multi-segment output schema 必须作为独立 contract 锁死：
   - 列集合必须等于所有 segment 功能列的并集
   - 列顺序必须稳定且与 `build_schedule_output_schema(schedule)` 一致
   - 各列 dtype 必须稳定，不允许因某段未启用而漂移
   - 未启用 segment 的功能列必须写入文档定义的非激活态默认值，不能留成未定义行为
   - 单段 schedule 必须退化成当前固定 schema，不允许凭空多列
12. Rust 等价性测试：
   - 先在旧 `run_backtest(...)` 上清掉 `has_leading_nan` 旧作用链
   - 再冻结成 `legacy_run_backtest_reference(...)`
   - 与新的 `run_backtest(...)` 做严格逐项对比

### 4.6 第六层：少量完整 WF 回归

这层数量必须少，只做最终回归。

继续使用并扩展：

1. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

建议保留的完整回归类型：

1. stitched 边界无事件时资金不出现断崖
2. 单窗口退化场景下，`backtest_schedule` 必须退化成单段 schedule，最终 stitched 必须与该窗口的 `test_active_result` 等价，而不是与完整 `test_pack_result` 等价
3. 无交易场景资金保持常数
4. 同 seed 同配置结果可复现
5. `ignore_indicator_warmup = false / true` 的对照实验链路可运行，但 `true` 不作为严格预热正确性测试

## 5. WF 测试性能约束

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

## 6. 推荐测试数据策略

优先级：

1. 先用小样本、无 gaps、固定 seed 的合成数据
2. 再用少量带交易的场景
3. 最后只保留极少数 stitched / WF 回归用较大样本

建议：

1. 所有 contract test 默认固定 seed
2. 所有工具函数测试优先无 gaps
3. stitched / segmented replay 测试优先选择“有边界、但样本不大”的场景

## 7. 建议新增测试文件清单

建议新增：

1. `py_entry/Test/backtest/test_data_pack_contract.py`
2. `py_entry/Test/backtest/test_result_pack_contract.py`
3. `py_entry/Test/backtest/test_mapping_projection_contract.py`
4. `py_entry/Test/backtest/test_extract_active_contract.py`
5. `py_entry/Test/walk_forward/test_window_indices_contract.py`
6. `py_entry/Test/walk_forward/test_window_slice_contract.py`
7. `py_entry/Test/walk_forward/test_stitched_contract.py`
8. `py_entry/Test/walk_forward/test_wf_ignore_indicator_warmup_contract.py`
9. `src/backtest_engine/backtester/tests.rs`

继续沿用并扩展：

1. `py_entry/Test/indicators/test_indicator_warmup_contract.py`
2. `py_entry/Test/indicators/test_resolve_indicator_contracts.py`
3. `py_entry/Test/walk_forward/test_wf_precheck_contract.py`
4. `py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
5. `py_entry/Test/walk_forward/test_walk_forward_guards.py`

## 8. 执行顺序

建议按这个顺序补测试：

1. 先补 builder / mapping / `SourceRange` 不变量测试
2. 再补 `extract_active(...)`
3. 再补窗口索引与窗口切片
4. 再补跨窗注入
5. 再补 stitched / segmented replay
6. 最后才补完整 WF 回归

## 9. AI 审阅清单

执行测试前，先用 AI 审一遍是否踩到下面问题：

1. 是否过度依赖完整 `Backtest.walk_forward(...)` 黑盒入口
2. 是否遗漏了 PyO3 工具函数级 contract test
3. 是否出现大样本、过多优化轮次的慢测试
4. 是否把摘要文档里的强不变量漏成了弱断言
5. 是否在 stitched 测试里直接比较了不该直接比较的原始 `mapping` 整数值
6. 是否仍按旧的资金列重建口径写 stitched 测试，而没有切到 `run_backtest_with_schedule(...)` 与 `backtest_schedule` 重基契约
