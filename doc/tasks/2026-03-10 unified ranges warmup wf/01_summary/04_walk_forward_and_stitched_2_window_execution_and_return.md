# 向前测试、窗口切片、跨窗注入与 stitched（二）窗口执行与返回结构

## 6. 每个窗口的执行流程

```text
# 先准备窗口规划与循环状态
resolved_contract_warmup_by_key =
    resolve_contract_warmup_by_key(wf_params.indicators)

# 这里的 wf_params.indicators 就是 run_walk_forward(...) 输入 wf_params 的指标参数子树；
# 不是额外派生的新参数对象，也不是从 template / settings 读取的第二套来源

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

# 这里与初始取数 planner 复用 01 里已定义的同一套共享 helper；
# 对 optimize=true 的指标参数，内部统一按 Param.max 解析，因此两边天然共享同一份最坏 warmup 真值
# 这里还要额外补齐 backtest exec warmup；ignore_indicator_warmup 只影响 applied_contract_warmup_by_key，
# 不影响 backtest_exec_warmup_base

windows = build_window_indices(data, config, required_warmup_by_key)
window_results = []
prev_last_bar_position = None

# 再按窗口顺序逐个执行
for (window_id, window) in windows:
    # 先切出当前窗口训练包和测试包
    train_pack_data = slice_data_pack_by_base_window(data, window.train_pack)
    test_pack_data = slice_data_pack_by_base_window(data, window.test_pack)

    # 用训练包训练当前窗口最优参数；优化搜索空间来自 wf_params，优化目标来自 config.optimize_metric
    best_params = run_optimization(train_pack_data, wf_params, config.optimize_metric, ...)

    # 第一次评估只跑到 Signals，拿到当前测试包的原始信号阶段结果
    eval_settings = settings.clone()
    eval_settings.execution_stage = Signals
    eval_settings.return_only_final = false
    raw_signal_stage_result = execute_single_backtest(
        test_pack_data,
        best_params,
        template,
        eval_settings,
    )

    # 先只注入上一窗口 carry 开仓，不注入窗口尾部强平
    carry_only_signals = build_carry_only_signals(
        raw_signal_stage_result,
        prev_last_bar_position,
    )

    # 先跑一遍“未强平前的自然回测结果”，只用于跨窗状态传播
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
    natural_test_pack_backtest_result = natural_ctx.into_summary(false, ExecutionStage::Backtest)

    # 只从“未强平前的自然末根状态”读取下一窗口 carry 来源
    last_bar_position = detect_last_bar_position(natural_test_pack_backtest_result.backtest)?
    has_cross_boundary_position = last_bar_position.is_some()

    # 再在 carry_only_signals 基础上追加窗口尾部强平，得到正式信号
    final_signals = build_final_signals(
        raw_signal_stage_result,
        carry_only_signals,
    )

    # 正式结果复用第一次评估已经算好的 indicators，只重复执行 Backtest + Performance
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
    final_test_pack_result = final_ctx.into_summary(false, ExecutionStage::Performance)

    # 组装当前窗口元数据
    meta = WindowMeta {
        window_id,
        best_params,
        has_cross_boundary_position,
        train_warmup_time_range,
        train_active_time_range,
        train_pack_time_range,
        test_warmup_time_range,
        test_active_time_range,
        test_pack_time_range,
    }

    # 收集当前窗口产物
    window_artifact = WindowArtifact {
        train_pack_data,
        test_pack_data,
        test_pack_result: final_test_pack_result,
        meta,
    }
    window_results.push(window_artifact)

    # 把当前窗口末根持仓方向回写成下一窗口的前序状态
    prev_last_bar_position = last_bar_position
```

补充说明：

1. `run_walk_forward(...)` 明确忽略 `settings.execution_stage` 和 `settings.return_only_final`
   - 这两个字段属于单次回测引擎的阶段返回控制
   - 在 WF 内部必须由当前阶段自己覆盖，不能沿用外部传入值
2. `eval_settings` 继承 WF 输入 `settings` 的其余字段，只覆盖 `execution_stage` 和 `return_only_final`
3. 当前窗口内部必须显式区分 5 个对象名：
   - `raw_signal_stage_result`
   - `carry_only_signals`
   - `natural_test_pack_backtest_result`
   - `final_signals`
   - `final_test_pack_result`
4. `raw_signal_stage_result` 必须至少保证：
   - `indicators` 可用
   - `signals` 可用
5. `natural_test_pack_backtest_result` 只服务跨窗状态传播：
   - 这里的末根状态代表“已经继承上一窗口 carry、但尚未注入当前窗口尾部强平”的结果
   - 它不进入正式返回值，不进入 stitched，不参与正式 performance
6. `natural_test_pack_backtest_result` 必须至少保证：
   - `backtest` 可用
7. `final_test_pack_result` 才是窗口正式结果：
   - 用于 `window_results`
   - 用于 stitched 的正式信号语义来源
   - 用于正式 performance
8. `final_test_pack_result` 必须保证：
   - `indicators` 可用
   - `signals` 可用
   - `backtest` 可用
   - `performance` 可用
9. 这里再把 stitched 的边界写死：
   - `final_test_pack_result.backtest` 不再直接拼成正式 stitched backtest
   - 正式 stitched backtest 统一改由 [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md) 定义的 segmented replay 方案生成
10. `final_ctx` 故意不再走顶层单次执行入口，而是手动构造 `BacktestContext`，直接复用第一次评估已经算好的 `indicators` 和注入后的 `signals`，因此这里只重复执行回测与绩效阶段，不再重复计算指标和信号
11. 这里的绩效函数直接接受完整 `test_pack_data` 和完整 `backtest`，再由函数内部根据 `test_pack_data.ranges[data.base_data_key].warmup_bars` 只统计非预热测试有效段
12. `final_test_pack_result` 自身已经是完整的测试包 `ResultPack`，其预热边界直接由自己的 `ranges` 表达
13. `prev_last_bar_position` 只在主循环里准备一次：
   - 来自上一窗口 `natural_test_pack_backtest_result.backtest`
   - `build_carry_only_signals(...)` 只接受这个参数，不再反向读取上一窗口 `ResultPack`
14. 因此 WF 侧不再为绩效计算额外做一轮窗口切片；窗口切片只发生在 `DataPack` 这一层
15. 同理，WF 侧也不再为 `ResultPack` 设计单独的窗口切片工具函数；每个窗口只切 `DataPack`，窗口级 `ResultPack` 由回测引擎基于窗口 `DataPack` 直接生成
16. 可以补一条一致性校验：
    - `final_test_pack_result.ranges[final_test_pack_result.base_data_key].warmup_bars == test_pack_data.ranges[test_pack_data.base_data_key].warmup_bars`
    - `final_test_pack_result.ranges[final_test_pack_result.base_data_key].pack_bars == test_pack_data.ranges[test_pack_data.base_data_key].pack_bars`
17. `run_optimization(...)` 的搜索空间来源必须唯一：
    - 直接读取 `run_walk_forward(...)` 输入的 `wf_params: &SingleParamSet`
    - 不允许从 `template` 或 `settings` 再派生第二套搜索空间定义
18. `run_optimization(...)` 的优化目标来源也必须唯一：
    - 直接读取 `config.optimize_metric`
    - 不允许从 `template`、`settings` 或窗口局部结果再推导第二套优化目标

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
    best_params: SingleParamSet,            // 当前窗口训练得到的最优参数
    has_cross_boundary_position: bool,      // 当前窗口在“未强平前自然末根状态”下是否仍有跨窗持仓

    train_warmup_time_range: Option<(i64, i64)>, // 训练预热段时间范围（毫秒时间戳）；若训练预热为空区间则为 None
    train_active_time_range: (i64, i64),    // 训练非预热有效段时间范围（毫秒时间戳）
    train_pack_time_range: (i64, i64),      // 完整训练包时间范围（毫秒时间戳）= 训练预热 + 训练有效段

    test_warmup_time_range: (i64, i64),     // 测试预热段时间范围（毫秒时间戳）；当前方案下测试预热至少为 1，因此这里始终必填
    test_active_time_range: (i64, i64),     // 测试非预热有效段时间范围（毫秒时间戳）
    test_pack_time_range: (i64, i64),       // 完整测试包时间范围（毫秒时间戳）= 测试预热 + 测试有效段
}

struct WindowArtifact {
    train_pack_data: DataPack, // 当前窗口训练包数据，包含训练预热
    test_pack_data: DataPack,  // 当前窗口测试包数据，包含测试预热
    test_pack_result: ResultPack, // 基于 test_pack_data 跑出的窗口结果，包含测试预热
    meta: WindowMeta,          // 当前窗口的结构性元数据
}

struct StitchedMeta {
    window_count: usize,                    // stitched 由多少个窗口拼接而成
    stitched_pack_time_range_from_active: (i64, i64), // stitched 整包时间范围（毫秒时间戳）；该范围由 stitched 的测试非预热有效段全局边界推导得到
    stitched_window_active_time_ranges: Vec<(i64, i64)>, // 每个参与 stitched 的窗口测试非预热有效段时间范围（毫秒时间戳），按拼接顺序返回
    next_window_hint: NextWindowHint,       // 下一窗口调度提示
}

struct NextWindowHint {
    expected_window_switch_time_ms: i64, // 下一窗口切换提示时间；不是“下一窗口第一根 bar 的时间”，而是用于调度估算的切换时点
    eta_days: f64,                    // 从当前最后一根测试 K 线到窗口切换提示时间的预计剩余天数；若为负则返回 0
    based_on_window_id: usize,        // 基于哪个窗口推导
}

struct StitchedArtifact {
    stitched_data: DataPack,     // stitched 后的数据容器
    stitched_result: ResultPack, // 基于 stitched_data 跑出的 stitched 结果
    meta: StitchedMeta,          // stitched 的结构性元数据
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
   - 不把 `bars / span_ms / span_days / span_months` 继续放在 `meta`
   - 这些统计型元数据应放进 `test_pack_result.performance`
5. 当前 `performance` 已经有 `span_ms / span_days`
   - 后续应补充 `bars / span_months`
   - 这样窗口测试段的统计型元数据统一由绩效模块返回
6. 不再额外返回 `train_pack_range / test_pack_range / test_active_range` 这类索引元数据
   - pack 自身已经有 `ranges`
   - 这类索引再返回一份容易重复且产生歧义
7. 时间范围元数据仍然必须返回
   - 并且统一在 Rust 侧算好后返回
   - 不把这些计算再丢给 Python 侧
8. `WindowMeta` 里的时间范围统一分三层
   - `*_warmup_time_range`：预热段时间范围
   - `*_active_time_range`：非预热有效段时间范围
   - `*_pack_time_range`：整包时间范围
   - 所有时间统一用毫秒级时间戳表达
9. `train_warmup_time_range`
   - 允许为空
   - 对空区间直接返回 `None`
   - 对非空区间，本质上就是直接从对应 pack 的 `mapping.time` 提取首尾值
10. `test_warmup_time_range`
   - 当前方案下始终必填
   - 因为前面已经写死 `P_test >= 1`
   - 因此这里直接返回 `(i64, i64)`，不再保留 `Option`
11. 因此只有 `train_warmup_time_range` 不能继续用必填 `(i64, i64)`
   - 因为文档前面已经明确允许 `P_train = 0`
   - 这时训练预热段是合法空区间，没有首尾时间可返回
12. `StitchedArtifact` 也沿用同一口径
   - `stitched_result.performance` 保存 stitched 统计型元数据
   - `StitchedMeta` 只保留 stitched 结构性上下文与调度提示
11. 因此 stitched 的 `bars / span_ms / span_days / span_months`
    - 也不再单独挂在 `StitchedArtifact` 顶层
    - 而是统一放进 `stitched_result.performance`
12. `StitchedMeta` 里的 stitched 总时间范围字段，不再用裸 `time_range`
    - 改成 `stitched_pack_time_range_from_active`
    - 这个命名明确表达两层语义：它描述的是 stitched 最终整包时间范围，但其起止边界是从 stitched 的全局 `test_active` 范围推导出来的
13. `StitchedMeta` 仍然返回 `stitched_window_active_time_ranges`
    - 显式列出每个参与 stitched 的窗口测试非预热有效段 `(start, end)`
    - 这样更利于调试拼接边界与定位窗口级问题

`NextWindowHint` 说明：
1. 只保留极简估算字段：
   使用场景只是估算“从当前窗口测试已有的最后一根 K 线，到下一窗口切换，还要多久”，方便与实盘对接；它是调度提示，不参与任何核心切片、`ranges`、`mapping`、回测逻辑。
2. `*_time_range = (start, end)` 的语义继续保持不变：
   - `start` = 第一根 bar 的时间
   - `end` = 最后一根 bar 的时间
   - 这里不把 `end` 改成半开右边界时间
3. 因此 `NextWindowHint` 的核心字段也改成：
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

    # 对 history_windows 中每个窗口 i 计算测试非预热有效段跨度
    test_active_span_ms(i) = history_windows[i].meta.test_active_time_range.end - history_windows[i].meta.test_active_time_range.start

    # 当 history_windows 非空时，用这些跨度的中位数作为预期窗口跨度
    if history_windows 非空:
        expected_test_active_span_ms = median(test_active_span_ms(i))
    else:
        # 当前只有 1 个窗口，则按“目标 test_active bars / 当前已观测 test_active bars”的比例估算
        observed_test_active_span_ms = last_window.meta.test_active_time_range.end - last_window.meta.test_active_time_range.start
        observed_test_active_bars    = last_window.test_pack_result.ranges[last_window.test_pack_result.base_data_key].active_bars

        # 当前已观测 test_active bars 必须 >= 2，否则时间跨度估算没有意义
        # 这和前面“合法 test_active 最小长度就是 2”是同一条约束，不是额外新增规则
        if observed_test_active_bars < 2:
            fail("single-window NextWindowHint fallback requires observed test_active bars >= 2")

        expected_test_active_span_ms = observed_test_active_span_ms * (config.test_active_bars as f64 / observed_test_active_bars as f64)

    # 取最后一窗测试非预热有效段的起始时间与最后一根时间
    last_test_active_start_ms = last_window.meta.test_active_time_range.start
    last_test_active_end_ms   = last_window.meta.test_active_time_range.end

    # 窗口切换提示时间 = 最后一窗测试非预热有效段起始时间 + 预期测试跨度
    expected_window_switch_time_ms = last_test_active_start_ms + expected_test_active_span_ms

    # 用切换提示时间减去当前最后一窗最后一根时间，得到剩余跨度
    remaining_span_ms = expected_window_switch_time_ms - last_test_active_end_ms

    # 最后换算为天数；若小于 0 则直接返回 0
    eta_days = max(remaining_span_ms / MS_PER_DAY, 0)

# 记录当前提示基于哪一个窗口推导
based_on_window_id = last_window.meta.window_id
```
