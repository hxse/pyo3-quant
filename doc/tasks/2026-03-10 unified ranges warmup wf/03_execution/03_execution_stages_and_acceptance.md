# 统一 Ranges / Warmup / WF 分阶段执行与验收

对应文档：

1. [01_execution_plan.md](./01_execution_plan.md)
2. [02_test_plan.md](./02_test_plan.md)
3. [../02_spec/04_walk_forward_and_stitched.md](../02_spec/04_walk_forward_and_stitched.md)
4. [../02_spec/05_segmented_backtest_truth_and_kernel.md](../02_spec/05_segmented_backtest_truth_and_kernel.md)
5. [05_pre_execution_ai_review.md](./05_pre_execution_ai_review.md)

## 1. 通用规则

1. 必须按阶段串行执行，不要一次性并行改大块逻辑。
2. 只有当前阶段通过验收，才能进入下一阶段。
3. 开始代码落地前，必须先落定 [05_pre_execution_ai_review.md](./05_pre_execution_ai_review.md)。
4. 每个阶段结束后，必须立刻回填 [../04_review/04_execution_backfill_template.md](../04_review/04_execution_backfill_template.md)。
5. 每个阶段的正式验收顺序固定为：
   - 先 `just check`
   - 再跑该阶段的最小测试
6. 阶段 A1 / A2 / B / C / D1 / D2 / E 都不允许用审阅替代最小测试放行。
7. 执行前 AI 审阅只负责开工 gate，不替代任何阶段验收。
8. 阶段 E 完成后，才允许跑最终总验收：
   - `just check`
   - `just test`
9. 本文保留的是 planning 阶段冻结的历史 gate 名称与验收意图；若后续测试文件重组或路径漂移，当前仓库实际可回放入口统一以 [../04_review/04_execution_backfill_template.md](../04_review/04_execution_backfill_template.md) 为准。

## 2. 阶段与测试映射

| 阶段 | 对应测试层 |
|---|---|
| A1 | `2.1 第一层：Builder / 容器不变量测试` 中 `DataPack / mapping / SourceRange / WarmupRequirements` contract |
| A2 | `2.1 第一层` 中 `ResultPack / strip_indicator_time_columns(...) / analyze_performance(...)` contract、`2.2 第二层：extract_active(...)` 专项测试 |
| B | `2.1.1 第一层补充：DataPackFetchPlanner 状态机 contract` |
| C | 现有单次回测回归测试；建立在 A2 已冻结的 `ResultPack / performance / extract_active` contract 之上 |
| D1 | `2.3 第三层：WF 窗口规划与切片测试` 中窗口几何、`build_window_time_ranges(...)`、`NextWindowHint` |
| D2 | `2.4 第四层：WF 跨窗注入测试`、`2.5` 中 stitched 上游输入 contract |
| E | `2.5 第五层：stitched / segmented replay 专项测试`、`2.6 第六层：少量完整 WF 回归` |

## 3. 阶段 A1

目标：

1. 立住新的共享 helper 与基础容器真值：`WarmupRequirements / DataPack / SourceRange / mapping`。
2. 立住 `build_mapping_frame(...) / build_data_pack(...)`。
3. 冻结 `WarmupRequirements` 的共享 helper 链。
4. 保持现有 `walk_forward` 公开路径编译可用，但不在本阶段做 WF 公共类型切换。

关键约束：

1. `build_mapping_frame(...)` 在生产链路里只由 `build_data_pack(...)` 调用。
2. `resolve_source_interval_ms(source_key)` 必须在 A1 冻结为唯一 shared resolver。
3. coverage、补拉、窗口右边界投影中的 `interval_ms` 都只能消费这条 resolver 的结果。
4. `WarmupRequirements` 必须完整承接：
   - `W_resolved`
   - `W_normalized`
   - `W_applied`
   - `W_backtest_exec_base`
   - `W_required`
5. 本阶段的 `just check` 语义写死为：
   - 新的 `DataPack / ResultPack / SourceRange` 入口与 builder 可以先独立落地
   - 现有 `src/types/outputs/walk_forward.rs` 与 `src/backtest_engine/walk_forward/runner.rs` 保持旧公开形态，不在本阶段切换
   - `src/types/outputs/walk_forward.rs` 继续直接依赖旧 `DataContainer / BacktestSummary`，直到阶段 E 才一次性切换
   - 阶段 A1 只引入新的 `DataPack / SourceRange` 与相关 builder，不做旧 WF 公开类型的桥接改写
   - 不要求 `walk_forward` 在阶段 A1 / A2 就已经改成摘要最终返回结构
6. 因而阶段 A1 不允许：
   - 提前发明新的中间公共 WF 返回类型
   - 提前把旧 `walk_forward` 公开路径切到半成品结构

阶段验收：

说明：

1. 下面列的是 A1 planning 阶段冻结的历史原 gate 路径。
2. 若当前仓库已不存在同名文件，不在本文回写“现行替代路径”；统一以后验回填为准。

1. `just check`
2. `just test-py py_entry/Test/backtest/test_data_pack_contract.py`
3. `just test-py py_entry/Test/backtest/test_mapping_projection_contract.py`

## 4. 阶段 A2

目标：

1. 立住 `ResultPack`、`build_result_pack(...)` 与 `strip_indicator_time_columns(...)`。
2. 冻结 `analyze_performance(...)` 的 dedicated contract。
3. 冻结 `extract_active(...)` 与 `RunArtifact` 的同源配对边界。

关键约束：

1. `build_result_pack(...)` 绝不调用 `build_mapping_frame(...)`。
2. `analyze_performance(...)` 的输入高度校验、内部切片与 fail-fast 必须单独冻结。
3. `extract_active(...)` 是唯一 builder 例外，但不调用 builder。
4. `extract_active(...)` 只做字段切片、mapping 重基、`ranges` 归零与 `performance` 继承。
5. A2 建立在 A1 已冻结的 `DataPack / mapping / WarmupRequirements` contract 之上。

阶段验收：

说明：

1. 下面列的是 A2 planning 阶段冻结的历史原 gate 路径。
2. 若当前仓库已不存在同名文件，不在本文回写“现行替代路径”；统一以后验回填为准。

1. `just check`
2. `just test-py py_entry/Test/backtest/test_result_pack_contract.py`
3. `just test-py py_entry/Test/backtest/test_strip_indicator_time_columns_contract.py`
4. `just test-py py_entry/Test/backtest/test_performance_contract.py`
5. `just test-py py_entry/Test/backtest/test_extract_active_contract.py`

## 5. 阶段 B

目标：

1. Python 只保留网络请求与空响应重试。
2. Rust 统一承担 planner 状态推进、共享 warmup 聚合、首尾覆盖与初始 `DataPack` 构建。

关键约束：

1. planner 初始化必须显式走共享 helper 链。
2. planner 初始化只允许先生成 `source_keys`，再对每个 `source_key` 调用 `resolve_source_interval_ms(source_key)`。
3. 非 base source 的时间投影统一调用：
   - `exact_index_by_time(...)`
   - `map_source_row_by_time(...)`
   - `map_source_end_by_base_end(...)`
4. 不允许在 planner 内部再维护第二套 timeframe -> interval 解析。
5. `required_warmup_by_key` 只表示 planner 与 WF 共享的基础 warmup 下界。
6. `DataPackFetchPlannerInput` 必须正式携带 `backtest_params`。
7. `resolve_backtest_exec_warmup_base(...)` 统一解析：
   - `optimize = true -> Param.max`
   - `optimize = false -> Param.value`
8. 阶段 B 的 planner gate 必须已经单独覆盖：
   - `resolve_backtest_exec_warmup_base(wf_params.backtest)` 的 dedicated contract
   - 不把这条共享 helper 延后到 WF 层再冻结
9. base 首次有效段若拿不满 `effective_limit` 根 live bar，必须在阶段 B 直接 fail-fast；不允许为 base 再引入右侧补拉去凑满有效段长度。

阶段验收：

1. `just check`
2. `just test-py py_entry/Test/data_generator/test_data_fetch_planner_contract.py`

## 6. 阶段 C

目标：

1. 单次回测全链路改成新 `DataPack / ResultPack`。
2. 清掉 `has_leading_nan` 在回测核心链上的旧作用。
3. 把 A2 已冻结的 `ResultPack / performance / extract_active` contract 接入正式单次回测主流程。

关键约束：

1. 信号模块内部处理预热禁开仓。
2. 绩效模块内部处理非预热切片。
3. 本阶段不再重新定义 `analyze_performance(...)` 或 `extract_active(...)` contract，只消费 A2 已冻结的唯一口径。
4. `has_leading_nan` 只保留在 `signals`。

阶段验收：

1. `just check`
2. `just test-py py_entry/Test/backtest/common_tests/test_backtest_regression_guards.py`

## 7. 阶段 D1

目标：

1. 落地窗口几何、窗口切片、`build_window_time_ranges(...)` 与 `NextWindowHint`。
2. 保持内部 `walk_forward` 实现链路编译闭环。
3. 不在本阶段进入跨窗注入或 stitched 上游输入构造。

关键约束：

1. 阶段 D1 不是公共 API 切换阶段。
2. 对外 `walk_forward` 仍保持未切换前的既有公共边界。
3. 阶段 D1 不定义新的中间公共返回结构。
4. `build_window_indices(...)` 是唯一窗口索引入口。
5. `WindowMeta` 的 `*_time_range` 统一由单一 helper 生成。
6. `build_window_time_ranges(...)` 只允许落在独立 helper 模块，不允许在窗口主循环、stitched 组装或 Python 包装层各写一套。
7. `NextWindowHint` 虽然不属于 stitched 输入，但它依赖最小窗口返回脚手架：
   - `last_window.meta.test_active_time_range`
   - `last_window.test_pack_result.ranges[last_window.test_pack_result.base_data_key].active_bars`
   - 因此阶段 D1 允许先立住最小 `WindowArtifact / WindowMeta / test_pack_result` 读取边界
   - 但这只服务窗口几何、时间范围与提示估算，不提前进入 D2 的跨窗注入或 stitched 输入构造
8. 阶段 D1 的最小必测边界还包括：
   - `NextWindowHint` 的单窗口 fallback 与 `observed_test_active_bars >= 3`
   - 窗口切片后的 `skip_mask` 仍与新 base 轴严格对齐
   - coverage 左扩导致的 `warmup_by_key[k] > W_required[k]` 会真实落到 `ranges_draft[k].warmup_bars`
9. 阶段 D1 的测试入口口径固定为：
   - `build_window_indices(...)`、`NextWindowHint`、`build_window_time_ranges(...)` 走 Rust 同模块单测
   - Python gate 只保留当前公开 helper / 黑盒路径能稳定覆盖的窗口切片语义
   - 不为了阶段 D1 额外新增 PyO3 临时入口

阶段验收：

1. `just check`
2. 定向 Rust 单测；不允许用全量 `just test-rust` 或模糊 substring 过滤替代阶段最小 gate：
   - `just test-rust-exact backtest_engine::walk_forward::data_splitter::tests::test_build_window_indices_contract`
   - `just test-rust-exact backtest_engine::walk_forward::next_window_hint::tests::test_next_window_hint_contract`
   - `just test-rust-exact backtest_engine::walk_forward::time_ranges::tests::test_build_window_time_ranges_contract`
3. `just test-py py_entry/Test/walk_forward/test_window_slice_contract.py`
   - 必须实际覆盖：
     - 窗口切片后的 `skip_mask` 对齐
     - coverage 左扩导致的 `warmup_by_key[k] > W_required[k]`
4. 本阶段不要求 Python gate 直接观察 stitched 上游内部真值。

## 8. 阶段 D2

目标：

1. 落地跨窗注入、窗口主循环与 stitched replay 上游输入构造。
2. 只把 `StitchedReplayInput` 构造完整，不在本阶段落地 replay kernel。
3. 保持内部 `walk_forward` 实现链路编译闭环。

关键约束：

1. 阶段 D2 不是公共 API 切换阶段。
2. 对外 `walk_forward` 仍保持未切换前的既有公共边界。
3. 阶段 D2 不定义新的中间公共返回结构。
4. 窗口测试执行固定三段：
   - `raw_signal_stage_result`
   - `natural_test_pack_backtest_result`
   - `final_test_pack_result`
5. stitched 输入桥接步骤写死为：
   - `extract_active(...) -> test_active_result -> stitched_signals`
6. `stitched_signals` 必须直接来自 `test_active_result.signals`。
7. `backtest_schedule` 只允许读取 `test_active_base_row_range` 再做减法重基。
8. `StitchedReplayInput` 只停留在内部 stitched 模块边界，不允许泄漏到公开 Rust / PyO3 返回类型。
9. 阶段 D2 可以合并进主线，但不允许对外暴露半成品 stitched 行为。
10. 阶段 D2 的最小必测边界还包括：
   - stitched carry 的最小合法长度：
     - `active_bars = 2` 非法
     - `active_bars = 3` 最小合法
   - `ignore_indicator_warmup = false / true` 的 dedicated contract：
     - `true` 只截获 `applied_contract_warmup_by_key`
     - 不影响 `backtest_exec_warmup_base`
11. 阶段 D2 的测试入口口径固定为：
   - `StitchedReplayInput` 上游输入 contract 走 Rust 同模块单测
   - Python gate 只保留当前公开 helper / 黑盒路径能稳定覆盖的跨窗注入语义
   - 不为了阶段 D2 额外新增 PyO3 临时入口

阶段验收：

1. `just check`
2. 定向 Rust 单测；不允许用全量 `just test-rust` 或模糊 substring 过滤替代阶段最小 gate：
   - `just test-rust-exact backtest_engine::walk_forward::stitch::tests::test_stitched_replay_input_contract`
   - `just test-rust-exact backtest_engine::walk_forward::injection::tests::test_wf_signal_injection_contract`
   - `just test-rust-exact backtest_engine::data_ops::warmup_requirements::tests::test_ignore_indicator_warmup_contract`
3. `just test-py py_entry/Test/walk_forward/test_wf_signal_injection_contract.py`
4. `just test-py py_entry/Test/walk_forward/test_wf_ignore_indicator_warmup_contract.py`
5. 本阶段不要求 Python gate 直接观察 `StitchedReplayInput`、`backtest_schedule` 或 `NextWindowHint` 内部真值。

## 9. 阶段 E

目标：

1. 落地 `run_backtest_with_schedule(...)`、统一 kernel、单次退化成单段 schedule。
2. 完成最终 stitched replay、`build_result_pack(...)` 回收与 Python 包装层对齐。
3. 一次性切换 `WalkForwardResult.stitched_result` 到摘要定义的最终公共返回结构。
4. 补齐 Rust 等价性测试和完整回归。

关键约束：

1. `run_backtest(...)` 必须在内部先构造单段 `schedule`，再直接调用 `run_backtest_with_schedule(...)`。
2. `ParamsSelector` 只保留单一路径：`schedule + segment_idx`。
3. multi-segment output schema 必须作为独立 contract 落地。
4. 正式 stitched backtest 真值只走 segmented replay 这条链。
5. `WalkForwardResult.stitched_result.meta.backtest_schedule` 在本阶段回填，并直接复用 replay 实际使用的那一份。
6. 本阶段必须一次性完成 `WalkForwardResult.stitched_result` 的最终切换。
7. 不保留阶段 D1 / D2 的中间态返回结构，不保留兼容层或双轨字段。
8. 多窗口 stitched carry 语义必须作为独立 contract 落地。
9. 阶段 E 的 Rust 单测必须实际覆盖：
   - `ParamsSelector`
   - `validate_schedule_contiguity(...)`
   - `validate_backtest_param_schedule_policy(...)`
   - `build_schedule_output_schema(...)`

阶段验收：

1. `just check`
2. `just stub`
3. 定向 Rust 单测；不允许用全量 `just test-rust` 或模糊 substring 过滤替代阶段最小 gate：
   - `just test-rust-exact backtest_engine::backtester::params_selector::tests::test_params_selector_contract`
   - `just test-rust-exact backtest_engine::backtester::schedule_contract::tests::test_validate_schedule_contiguity_contract`
   - `just test-rust-exact backtest_engine::backtester::schedule_policy::tests::test_validate_backtest_param_schedule_policy_contract`
   - `just test-rust-exact backtest_engine::backtester::output_schema::tests::test_build_schedule_output_schema_contract`
4. `just test-py path="py_entry/Test/test_public_api_stub_contract.py"`
5. `just test-py path="py_entry/Test/walk_forward/test_walk_forward_guards.py"`
6. 上述 stitched 测试里必须实际覆盖：
   - 多窗口 stitched carry contract
   - 不能只覆盖 `backtest_schedule / ATR / schema`

## 10. 执行前审阅检查项

执行前审阅应至少覆盖：

1. 旧结构与旧字段是否已清干净：
   - `SourceRange { warmup, total }`
   - `transition_*`
2. builder / extract 路径是否唯一：
   - `build_result_pack(...)` 不误调 `build_mapping_frame(...)`
   - `extract_active(...)` 不误走 builder
3. 单次回测与 stitched 最终落地链是否唯一：
   - `run_backtest(...)` 已退化成单段 `schedule`
   - stitched 最终结果统一走 `strip_indicator_time_columns(...) -> build_result_pack(...)`
4. WF 几何与 stitched 重基是否唯一：
   - `build_window_indices(...)` 已显式产出 `test_active_base_row_range`
   - `backtest_schedule` 只由这份区间做减法重基
5. `walk_forward` 主循环是否已闭环：
   - `window_results.push(...)`
   - `prev_last_bar_position` 回写
   - `has_cross_boundary_position` 回写
6. 窗口三段结果链是否已显式区分：
   - `raw_signal_stage_result`
   - `natural_test_pack_backtest_result`
   - `final_test_pack_result`
7. carry 来源是否唯一：
   - `detect_last_bar_position(...)` 只读取 `natural_test_pack_backtest_result.backtest`
8. Rust 等价性基线是否在清掉 `has_leading_nan` 旧作用链后再冻结为 `legacy_run_backtest(...)`
