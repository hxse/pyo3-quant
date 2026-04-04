# 向前测试、窗口切片、跨窗注入与 stitched（二）窗口执行与返回结构

本篇承接 `WalkForwardPlan`，并在窗口执行阶段直接拥有四类对象：

1. `WindowArtifact`
   - 承接窗口正式返回值与窗口级结构性元数据
2. `StitchedArtifact`
   - 承接 stitched 最终返回值与 stitched 元数据
3. `NextWindowHint`
   - 承接窗口执行结束后的调度提示
4. `StitchedReplayInput`
   - 承接 `04 -> 05` 的正式运行输入

这里的边界固定为：

1. `WindowArtifact / StitchedArtifact / NextWindowHint` 属于返回对象。
2. `StitchedReplayInput` 属于运行输入对象。
3. 本篇只负责把窗口执行结果收口到这些对象，不负责 segmented replay kernel。

## 6. 每个窗口的执行流程

先把会影响主循环的前置约束集中写死：

1. `wf_params.indicators` 是指标 warmup helper 的唯一合法输入路径；不允许在 WF 层先手工物化第二套 concrete indicator params。
2. `wf_params.backtest` 是 backtest exec warmup helper 的唯一合法输入路径；不允许在 WF 层先手工物化第二套 concrete runtime params。
3. `run_walk_forward(...)` 明确忽略外部传入的 `settings.execution_stage` 和 `settings.return_only_final`；WF 内部会自己覆盖这两个字段。
4. stitched 的正式 backtest 真值统一来自 `05` 定义的 segmented replay；本篇只准备窗口正式结果与 stitched 上游输入。

```text
resolved_contract_warmup_by_key =
    resolve_contract_warmup_by_key(wf_params.indicators)

normalized_contract_warmup_by_key =
    normalize_contract_warmup_by_key(S_keys, resolved_contract_warmup_by_key)

applied_contract_warmup_by_key =
    apply_wf_warmup_policy(
        normalized_contract_warmup_by_key,
        config.ignore_indicator_warmup,
    )

backtest_exec_warmup_base =
    resolve_backtest_exec_warmup_base(wf_params.backtest)

required_warmup_by_key =
    merge_required_warmup_by_key(
        data.base_data_key,
        applied_contract_warmup_by_key,
        backtest_exec_warmup_base,
    )

wf_plan = build_window_indices(data, config, required_warmup_by_key)
window_results = []
prev_last_bar_position = None

for window_plan in wf_plan.windows:
    window_id = window_plan.window_idx
    train_pack_data = slice_data_pack_by_base_window(data, window_plan.indices.train_pack)
    test_pack_data = slice_data_pack_by_base_window(data, window_plan.indices.test_pack)

    # 对象边界：
    # RunArtifact 只覆盖确实产生 ResultPack 的路径。
    # 当前窗口里，这条边界只在测试侧复用：
    # test_pack_data 与 raw_signal_stage_result / natural_test_pack_backtest_result /
    # final_test_pack_result 始终保持同源配对。
    # 下面继续沿用局部变量展开流程，只是为了把优化、信号、自然回放、正式回放这几个阶段区别写清楚；
    # 它们不表示本篇放弃 RunArtifact 边界，而是把测试侧的同源配对关系拆成显式阶段变量。

    optimization_result = run_optimization(
        train_pack_data,
        wf_params,
        template,
        settings,
        config.optimizer_config,
    )
    best_params = optimization_result.best_params

    eval_settings = settings.clone()
    eval_settings.execution_stage = Signals
    eval_settings.return_only_final = false
    raw_signal_stage_result = execute_single_backtest(
        test_pack_data,
        best_params,
        template,
        eval_settings,
    )

    carry_only_signals = build_carry_only_signals(
        raw_signal_stage_result,
        prev_last_bar_position,
    )

    raw_test_pack_indicators =
        strip_indicator_time_columns(raw_signal_stage_result.indicators)
    natural_ctx = BacktestContext::new()
    natural_ctx.indicator_dfs = raw_test_pack_indicators
    natural_ctx.signals_df = carry_only_signals
    natural_ctx.execute_backtest_if_needed(
        ExecutionStage::Backtest,
        false,
        test_pack_data,
        best_params.backtest,
    )
    natural_test_pack_backtest_result = build_result_pack(
        test_pack_data,
        None,
        None,
        natural_ctx.backtest_df,
        None,
    )

    last_bar_position = detect_last_bar_position(natural_test_pack_backtest_result.backtest)?
    has_cross_boundary_position = last_bar_position.is_some()

    final_signals = build_final_signals(
        raw_signal_stage_result,
        carry_only_signals,
    )

    raw_test_pack_indicators =
        strip_indicator_time_columns(raw_signal_stage_result.indicators)
    final_ctx = BacktestContext::new()
    final_ctx.indicator_dfs = raw_test_pack_indicators
    final_ctx.signals_df = final_signals
    final_ctx.execute_backtest_if_needed(
        ExecutionStage::Backtest,
        false,
        test_pack_data,
        best_params.backtest,
    )
    final_ctx.execute_performance_if_needed(
        ExecutionStage::Performance,
        false,
        test_pack_data,
        best_params.performance,
    )
    final_test_pack_result = build_result_pack(
        test_pack_data,
        final_ctx.indicator_dfs,
        final_ctx.signals_df,
        final_ctx.backtest_df,
        final_ctx.performance,
    )
    time_ranges = build_window_time_ranges(train_pack_data, test_pack_data)

    test_active_base_row_range = window_plan.indices.test_active_base_row_range
    meta = WindowMeta {
        window_id,
        best_params,
        has_cross_boundary_position,
        test_active_base_row_range,
        train_warmup_time_range: time_ranges.train_warmup_time_range,
        train_active_time_range: time_ranges.train_active_time_range,
        train_pack_time_range: time_ranges.train_pack_time_range,
        test_warmup_time_range: time_ranges.test_warmup_time_range,
        test_active_time_range: time_ranges.test_active_time_range,
        test_pack_time_range: time_ranges.test_pack_time_range,
    }

    window_artifact = WindowArtifact {
        train_pack_data,
        test_pack_data,
        test_pack_result: final_test_pack_result,
        meta,
    }
    window_results.push(window_artifact)

    prev_last_bar_position = last_bar_position

stitched_artifact = stitch_window_results(window_results, data)

return WalkForwardResult {
    optimize_metric: config.optimizer_config.optimize_metric,
    window_results,
    stitched_result: stitched_artifact,
}
```

流程说明：

1. 上面这条 warmup helper 链与初始取数 planner 复用 `01` 里同一套 shared helper。
2. 对 `optimize = true` 的 warmup 相关字段，helper 内部统一按 `Param.max` 解析，因此 planner 和 WF 共享同一份“最坏 warmup 真值”。
3. `ignore_indicator_warmup` 只影响 `applied_contract_warmup_by_key`，不影响 `backtest_exec_warmup_base`。
4. `eval_settings` 继承外部 `settings` 的其余字段，只覆盖 `execution_stage` 与 `return_only_final`。
5. `wf_plan` 是窗口规划阶段的正式产物；窗口主循环只消费 `wf_plan.windows`，不在执行阶段重新推导窗口几何真值。
6. 当前窗口内部虽然仍然按局部变量展开，但对象边界固定不变：
   - `RunArtifact` 只覆盖确实产生 `ResultPack` 的路径
   - 当前窗口里，这条边界只用于测试侧 `test_pack_data + 各阶段 ResultPack 输出`
   - 训练侧保持 `train_pack_data -> best_params` 这条优化路径，不额外引入训练 `RunArtifact`
7. 当前窗口内部必须显式区分 5 个对象名：
   - `raw_signal_stage_result`
   - `carry_only_signals`
   - `natural_test_pack_backtest_result`
   - `final_signals`
   - `final_test_pack_result`
8. `raw_signal_stage_result` 必须至少保证：
   - `indicators` 可用
   - `signals` 可用
9. `natural_test_pack_backtest_result` 只服务跨窗状态传播：
   - 这里的末根状态代表“已经继承上一窗口 carry、但尚未注入当前窗口尾部强平”的结果
   - 它不进入正式返回值，不进入 stitched，不参与正式 performance
10. `natural_test_pack_backtest_result` 必须至少保证：
   - `backtest` 可用
11. `final_test_pack_result` 才是窗口正式结果：
   - 用于 `window_results`
   - 用于 stitched 的正式信号语义来源
   - 用于正式 performance
   - 当前正式语义下，跨窗 carry 开仓写在 active 第一根，因此 `extract_active(...)` 得到的 `test_active_result.signals` 可以直接作为 stitched 正式信号来源
12. `final_test_pack_result` 必须保证：
   - `indicators` 可用
   - `signals` 可用
   - `backtest` 可用
   - `performance` 可用
13. 正式 stitched backtest 真值来源统一写死为 [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md) 定义的 segmented replay 方案。
14. `BacktestContext` 在这里仍然只承载阶段中间字段：
    - `indicator_dfs`
    - `signals_df`
    - `backtest_df`
    - `performance`
    它不构成第二条 `ResultPack` 落地入口。
15. 窗口执行里任何新的独立 `ResultPack` 都必须最终统一回到 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 定义的 `build_result_pack(...)`：
    - `natural_test_pack_backtest_result = build_result_pack(test_pack_data, None, None, natural_ctx.backtest_df, None)`
    - `final_test_pack_result = build_result_pack(test_pack_data, final_ctx.indicator_dfs, final_ctx.signals_df, final_ctx.backtest_df, final_ctx.performance)`
16. 这里的绩效函数直接接受完整 `test_pack_data` 和完整 `backtest`，再由函数内部根据 `test_pack_data.ranges[data.base_data_key].warmup_bars` 只统计测试 `active 区间`。
17. `final_test_pack_result` 自身已经是完整的测试包 `ResultPack`，其预热边界直接由自己的 `ranges` 表达。
18. `prev_last_bar_position` 只在主循环里准备一次：
   - 来自上一窗口 `natural_test_pack_backtest_result.backtest`
   - `build_carry_only_signals(...)` 只接受这个参数
19. WF 侧的窗口切片发生在 `DataPack` 这一层；绩效计算直接消费完整 `test_pack_data + backtest`。
20. 窗口级 `ResultPack` 由回测引擎基于窗口 `DataPack` 统一通过 `build_result_pack(...)` 生成。
21. 这里必须补一条一致性校验：
    - `final_test_pack_result.ranges[final_test_pack_result.base_data_key].warmup_bars == test_pack_data.ranges[test_pack_data.base_data_key].warmup_bars`
    - `final_test_pack_result.ranges[final_test_pack_result.base_data_key].pack_bars == test_pack_data.ranges[test_pack_data.base_data_key].pack_bars`
22. `run_optimization(...)` 的搜索空间来源必须唯一：
   - 直接读取 `run_walk_forward(...)` 输入的 `wf_params: &SingleParamSet`
   - 不允许从 `template` 或 `settings` 再派生第二套搜索空间定义
23. `run_optimization(...)` 的优化目标来源也必须唯一：
   - 直接读取 `config.optimizer_config.optimize_metric`
   - 不允许从 `template`、`settings` 或窗口局部结果再推导第二套优化目标
24. 窗口主循环结束并不等于 `run_walk_forward(...)` 结束：
   - 循环结束后，必须再调用 `stitch_window_results(window_results, data)`
   - stitched 的详细组装算法统一引用 [04_walk_forward_and_stitched_3_stitched_algorithm.md](./04_walk_forward_and_stitched_3_stitched_algorithm.md)
25. `stitch_window_results(...)` 的职责在这里按主线语义固定为：
   - 先基于 `window_results + data` 构造 `StitchedReplayInput`
   - 再调用 `05` 定义并执行的 segmented replay，生成正式 stitched backtest 真值
   - 最后组装 `StitchedArtifact`
   - 也就是说：`04` 负责 orchestration 与最终 artifact 回收，`05` 负责 replay 真值生成算法与 contract
26. `run_walk_forward(...)` 的最终返回值统一写死为：
   - `WalkForwardResult { optimize_metric, window_results, stitched_result }`
   - 因此窗口级返回、stitched 输入构造和 stitched 最终结果都属于同一条 `run_walk_forward(...)` 主流程

### 6.1 ResultPack Stage Output Contract Table

`ResultPack` 在总定义里保留 `Option`，但 WF 主流程对不同阶段对象施加更强约束。这里直接把阶段契约写死：

| Object | indicators | signals | backtest | performance | Notes |
| --- | --- | --- | --- | --- | --- |
| `raw_signal_stage_result` | required | required | not required | not required | Used only for raw indicator/signal stage output |
| `natural_test_pack_backtest_result` | not required | not required | required | not required | Used only to read the natural last-bar state before forced flatten |
| `final_test_pack_result` | required | required | required | required | The formal per-window returned result |
| `test_active_result` | required | required | required | required | The formal active-only window result after `extract_active(...)` |
| `stitched_result` | required | required | required | required | Final formal stitched result, generated by the segmented replay scheme defined in `05` |

说明：

1. 上表是 WF / stitched 对 `ResultPack` 总定义施加的阶段约束，不改变 `01` 里 `ResultPack` 的通用 `Option` 定义。
2. 因此 WF 主流程里直接读取这些字段时，不需要再发明“缺了就跳过”的平行分支；只要当前对象名对应的阶段契约已经写死，就按该契约直接使用。

## 7. WF 返回结构

目标返回结构直接定成：

```rust
struct WindowMeta {
    window_id: usize,                        // 窗口编号
    best_params: SingleParamSet,            // 当前窗口训练得到的最优点参数容器；仍保留原参数树形状，但优化后的运行时真值统一以各字段 `.value` 为准
    has_cross_boundary_position: bool,      // 当前窗口在“未强平前自然末根状态”下是否仍有跨窗持仓
    test_active_base_row_range: Range<usize>, // 虽然作为 WindowMeta 字段对外暴露，但只供 stitched schedule 内部重基使用：当前窗口 test_active 在原始 WF 输入 DataPack.base 轴上的绝对半开区间

    train_warmup_time_range: Option<(i64, i64)>, // 训练预热段时间范围（毫秒时间戳）；若训练预热为空区间则为 None
    train_active_time_range: (i64, i64),    // 训练 active 区间时间范围（毫秒时间戳）
    train_pack_time_range: (i64, i64),      // 训练 pack 区间时间范围（毫秒时间戳）= 训练 warmup 区间 + 训练 active 区间

    test_warmup_time_range: (i64, i64),     // 测试预热段时间范围（毫秒时间戳）；当前方案下测试预热至少为 1，因此这里始终必填
    test_active_time_range: (i64, i64),     // 测试 active 区间时间范围（毫秒时间戳）
    test_pack_time_range: (i64, i64),       // 测试 pack 区间时间范围（毫秒时间戳）= 测试 warmup 区间 + 测试 active 区间
}

struct WindowArtifact {
    train_pack_data: DataPack, // 当前窗口训练包数据，包含训练预热
    test_pack_data: DataPack,  // 当前窗口测试包数据，包含测试预热
    test_pack_result: ResultPack, // 基于 test_pack_data 跑出的窗口结果，包含测试预热
    meta: WindowMeta,          // 当前窗口的结构性元数据
}

struct StitchedMeta {
    window_count: usize,                    // stitched 由多少个窗口拼接而成
    stitched_pack_time_range_from_active: (i64, i64), // stitched pack 区间时间范围（毫秒时间戳）；该范围由 stitched 的测试 active 区间全局边界推导得到
    stitched_window_active_time_ranges: Vec<(i64, i64)>, // 每个参与 stitched 的窗口测试 active 区间时间范围（毫秒时间戳），按拼接顺序返回
    backtest_schedule: Vec<BacktestParamSegment>, // stitched replay 的正式分段参数元数据；后续解释多段 backtest 输出时必须结合它
    next_window_hint: NextWindowHint,       // 下一窗口调度提示
}

struct NextWindowHint {
    expected_window_switch_time_ms: i64, // 下一窗口切换提示时间；不是“下一窗口第一根 bar 的时间”，而是用于调度估算的切换时点
    eta_days: f64,                    // 从当前最后一根测试 K 线到窗口切换提示时间的预计剩余天数；若为负则返回 0
    based_on_window_id: usize,        // 基于哪个窗口推导
}

struct StitchedArtifact {
    stitched_data: DataPack,     // stitched 后的数据容器
    result: ResultPack,          // 基于 stitched_data 跑出的 stitched 结果
    meta: StitchedMeta,          // stitched 的结构性元数据
}

struct StitchedReplayInput {
    stitched_data: DataPack,                          // replay 与最终 StitchedArtifact 结果共用的数据容器
    stitched_signals: DataFrame,                      // replay 直接消费的正式 stitched 信号
    backtest_schedule: Vec<BacktestParamSegment>,     // replay 直接消费的正式 schedule
    stitched_atr_by_row: Option<Series>,              // replay 直接消费的可变 ATR 输入
    stitched_indicators_with_time: HashMap<String, DataFrame>, // 最终 `StitchedArtifact.result` 构建阶段消费的结果态 indicators；key 只表示 `indicator_source_keys` 集合，不表达顺序语义
}

struct WalkForwardResult {
    optimize_metric: OptimizeMetric,   // 本次 WF 的全局优化目标
    window_results: Vec<WindowArtifact>, // 每个窗口的测试包产物
    stitched_result: StitchedArtifact, // 所有窗口 stitched 后的总结果
}
```

约束：

1. `test_pack_result` 这个名字必须写死，不能再用笼统的 `result`
   - 因为这里返回的是**测试包对应的窗口结果**
   - 且它按当前设计**包含测试预热**
2. `test_pack_result` 包含测试预热是对的
   - 因为窗口回测引擎本来就是基于完整 `test_pack_data` 运行
   - 回测引擎返回的 `ResultPack` 也天然包含预热
3. `WindowArtifact` 同时返回 `train_pack_data`
   - 主要是为了测试、调试和窗口级问题排查
   - 但当前窗口只对 `test_pack_data` 运行回测并生成 `test_pack_result`
4. `WindowMeta` 只保存结构性上下文
   - 窗口级统计型元数据统一保留在 `test_pack_result.performance`
5. `test_pack_result.performance` 保持通用指标字典口径：`Option<HashMap<String, f64>>`；键集由 `best_params.performance.metrics` 与 `PerformanceMetric` 决定。
6. 本页只冻结窗口与 stitched 所需的结构性时间元数据：
   - `*_warmup_time_range`
   - `*_active_time_range`
   - `*_pack_time_range`
   - `stitched_pack_time_range_from_active`
   - `stitched_window_active_time_ranges`
   - 这些字段属于 `WindowMeta / StitchedMeta` 的正式 contract
7. `train_pack_range / test_pack_range` 这类泛化索引元数据不单独返回
   - pack 自身已经有 `ranges`
   - 再返回一份容易重复且产生歧义
8. 但 `test_active_base_row_range` 例外，必须保留在 `WindowMeta`
   - 因为它不是窗口局部重基结果，也不是 stitched 行号
   - 它是当前窗口 `test_active` 在原始 WF 输入 `DataPack.base` 轴上的绝对半开区间真值
   - 后续 `backtest_schedule` 需要直接基于它做重基
   - 这个字段应直接从 `build_window_indices(...)` 产出的 `window_plan.indices.test_active_base_row_range` 透传进入 `WindowMeta`
   - 不允许在窗口执行结束后，再根据 `mapping.height()`、时间范围或别的派生量重新反推一遍
   - 虽然它作为 `WindowMeta` 字段对外暴露，但语义上只服务 stitched `backtest_schedule` 重基，不应被理解成通用业务元数据
9. 时间范围元数据必须返回
   - 并且统一在 Rust 侧算好后返回
   - 不把这些计算再丢给 Python 侧
9.1 `best_params` 的正式语义也要写死：
   - 它使用 `SingleParamSet` 这个现有容器类型
   - 但语义上已经不是“待搜索的参数树”，而是“最优点参数容器”
   - 与当前源码 `rebuild_param_set(...)` 一致：保留原始参数树形状与 `min / max / step / optimize` 元数据，只把最优解写回各叶子 `.value`
   - 因而后续 runtime 消费：
     - `best_params.backtest`
     - `best_params.performance`
     都必须只把 `.value` 当成正式运行时真值
   - 不允许在 stitched / replay / Python 返回层再把 `best_params` 当成待解析搜索空间，重新按 `.optimize / .max / .min / .step` 推导第二套 runtime 参数
10. `WindowMeta` 里的时间范围统一分三层
   - `*_warmup_time_range`：预热段时间范围
   - `*_active_time_range`：`active 区间` 时间范围
   - `*_pack_time_range`：`pack 区间` 时间范围
   - 所有时间统一用毫秒级时间戳表达
   - 所有这些字段都必须由同一个 helper 统一生成：
     - `build_window_time_ranges(train_pack_data, test_pack_data)`
   - 该 helper 只允许读取：
     - 已经物化好的 `train_pack_data / test_pack_data`
     - `pack.mapping["time"]`
     - `pack.ranges[base_key]`
   - 不允许从 `full_data` 反推
   - 不允许从 `WindowPlan` 的 bars / range 反推
   - 不允许在不同调用点手写第二套时间范围生成逻辑
   - 唯一算法直接写死为：

```text
fn build_pack_time_ranges(pack: &DataPack) -> PackTimeRanges

base_key = pack.base_data_key
base_times = pack.mapping["time"]
base_range = pack.ranges[base_key]

assert base_range.pack_bars == base_times.height()
assert base_range.active_bars >= 1

pack_time_range =
    (base_times[0], base_times[base_range.pack_bars - 1])

if base_range.warmup_bars == 0:
    warmup_time_range = None
else:
    warmup_time_range =
        (base_times[0], base_times[base_range.warmup_bars - 1])

active_start_idx = base_range.warmup_bars
active_end_idx = base_range.pack_bars - 1
active_time_range =
    (base_times[active_start_idx], base_times[active_end_idx])
```

```text
fn build_window_time_ranges(
    train_pack_data: &DataPack,
    test_pack_data: &DataPack,
) -> WindowTimeRanges

train_ranges = build_pack_time_ranges(train_pack_data)
test_ranges = build_pack_time_ranges(test_pack_data)

assert test_ranges.warmup_time_range.is_some()

return WindowTimeRanges {
    train_warmup_time_range: train_ranges.warmup_time_range,
    train_active_time_range: train_ranges.active_time_range,
    train_pack_time_range: train_ranges.pack_time_range,
    test_warmup_time_range: test_ranges.warmup_time_range.unwrap(),
    test_active_time_range: test_ranges.active_time_range,
    test_pack_time_range: test_ranges.pack_time_range,
}
```
11. `train_warmup_time_range`
   - 允许为空
   - 对空区间直接返回 `None`
   - 对非空区间，本质上就是由同一 helper 基于对应 pack 的 base `time` 真值和 `ranges[base]` 提取首尾值
12. `test_warmup_time_range`
   - 当前方案下始终必填
   - 因为前面已经写死 `P_test >= 1`
   - 因此这里直接返回 `(i64, i64)`
13. 因此只有 `train_warmup_time_range` 使用 `Option<(i64, i64)>`
   - 因为文档前面已经明确允许 `P_train = 0`
   - 这时训练预热段是合法空区间，没有首尾时间可返回
14. `StitchedArtifact` 也沿用同一口径
   - `result.performance` 保存 stitched 统计型元数据
   - `StitchedMeta` 保留 stitched 结构性上下文、schedule 解释元数据与调度提示
14.1 `result.performance` 保持通用指标字典口径：`Option<HashMap<String, f64>>`；键集由 `performance_params.metrics` 与 `PerformanceMetric` 决定。
14.2 `StitchedReplayInput` 是 `04 -> 05` 的正式边界对象：
   - stitched 输入边界统一引用 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 里的“stitched 单一事实块”
   - 它只收纳 stitched 阶段已经产出的正式输入真值
   - 不新增第二套 schedule / ATR / signals / indicators 解释逻辑
   - 其中 replay 直接消费：
     - `stitched_data`
     - `stitched_signals`
     - `backtest_schedule`
     - `stitched_atr_by_row`
   - 最终 `StitchedArtifact.result` 构建阶段再消费：
     - `stitched_indicators_with_time`
15. stitched 的统计型元数据统一保留在 `StitchedArtifact.result.performance`
16. `StitchedMeta` 里的 stitched 总时间范围字段统一命名为 `stitched_pack_time_range_from_active`
    - 这个命名明确表达两层语义：它描述的是 stitched 最终 `pack 区间` 时间范围，但其起止边界是从 stitched 的全局 `test_active` 范围推导出来的
17. `StitchedMeta` 返回 `stitched_window_active_time_ranges`
   - 显式列出每个参与 stitched 的窗口测试 `active 区间` `(start, end)`
    - 这样更利于调试拼接边界与定位窗口级问题
18. `StitchedMeta` 还必须保留 `backtest_schedule`
   - 因为多段 schedule 下，最终 `StitchedArtifact.result.backtest` 的并集列与 `NaN` 解释都依赖这份 schedule
   - 它不是仅供 `04 -> 05` 调用时临时传递的中间输入，而是最终 stitched 结果的正式解释元数据
   - 这里放进 `meta` 即可，不需要再单独挂在 `StitchedArtifact` 顶层
19. `WalkForwardResult.stitched_result.meta.backtest_schedule` 必须直接复用 stitched 阶段已经构造并通过校验的那一份 `backtest_schedule`
   - 不允许在 replay 完成后，再根据 `StitchedArtifact.result.backtest`、时间范围、行数或别的派生量重建第二份 schedule
   - 这份字段的落地语义是“保存 replay 实际使用的正式 schedule 真值”，不是“从 replay 结果反推 schedule”

`NextWindowHint` 说明：
1. 只保留极简估算字段：
   使用场景只是估算“从当前窗口测试已有的最后一根 K 线，到下一窗口切换，还要多久”，方便与实盘对接；它是调度提示，不参与任何核心切片、`ranges`、`mapping`、回测逻辑。
2. `*_time_range = (start, end)` 的语义如下：
   - `start` = 第一根 bar 的时间
   - `end` = 最后一根 bar 的时间
3. 因此 `NextWindowHint` 的核心字段定义为：
   - `expected_window_switch_time_ms`
   - 它表达的是“窗口切换提示时间”，不是“下一窗口第一根 bar 的时间”
4. 这里的时间跨度只是一种提示性估算：
   - 直接使用 `*_time_range.end - *_time_range.start` 作为首尾时间差 heuristic
   - 不把它当作严格的 bar 覆盖长度真值
   - 因此允许存在一个 bar interval 级别的近似误差
   - 这个误差对 `NextWindowHint` 的使用场景是可接受的，因为它只服务提示与调度，不参与任何核心计算
5. 估算算法：
```text
# 先判断最后一窗是否完整
last_window_is_complete =
    last_window.test_pack_result.ranges[last_window.test_pack_result.base_data_key].active_bars == config.test_active_bars

# 若最后一窗已经完整，则说明下一窗口切换时间已经到达
if last_window_is_complete:
    expected_window_switch_time_ms = last_window.meta.test_active_time_range.end
    eta_days = 0
else:
    # 若最后一窗不完整，则历史跨度统计只取除最后一窗外的所有窗口
    history_windows = window_results[0..last]

    # 对 history_windows 中每个窗口 i 计算测试 active 区间跨度
    test_active_span_ms(i) = history_windows[i].meta.test_active_time_range.end - history_windows[i].meta.test_active_time_range.start

    # 当 history_windows 非空时，用这些跨度的中位数作为预期窗口跨度
    if history_windows 非空:
        expected_test_active_span_ms = median(test_active_span_ms(i))
    else:
        # 当前只有 1 个窗口，则按“目标 test_active bars / 当前已观测 test_active bars”的比例估算
        observed_test_active_span_ms = last_window.meta.test_active_time_range.end - last_window.meta.test_active_time_range.start
        observed_test_active_bars    = last_window.test_pack_result.ranges[last_window.test_pack_result.base_data_key].active_bars

        # 当前已观测 test_active bars 必须 >= 3，否则时间跨度估算没有意义
        # 这和前面“合法 test_active 最小长度就是 3”是同一条约束，不是额外新增规则
        if observed_test_active_bars < 3:
            fail("single-window NextWindowHint fallback requires observed test_active bars >= 3")

        expected_test_active_span_ms = observed_test_active_span_ms * (config.test_active_bars as f64 / observed_test_active_bars as f64)

    # 取最后一窗测试 active 区间的起始时间与最后一根时间
    last_test_active_start_ms = last_window.meta.test_active_time_range.start
    last_test_active_end_ms   = last_window.meta.test_active_time_range.end

    # 窗口切换提示时间 = 最后一窗测试 active 区间起始时间 + 预期测试跨度
    expected_window_switch_time_ms = last_test_active_start_ms + expected_test_active_span_ms

    # 用切换提示时间减去当前最后一窗最后一根时间，得到剩余跨度
    remaining_span_ms = expected_window_switch_time_ms - last_test_active_end_ms

    # 最后换算为天数；若小于 0 则直接返回 0
    eta_days = max(remaining_span_ms / MS_PER_DAY, 0)

# 记录当前提示基于哪一个窗口推导
based_on_window_id = last_window.meta.window_id
```
