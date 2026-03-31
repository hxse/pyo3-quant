# 向前测试、窗口切片、跨窗注入与 stitched（三）stitched 总则与算法

## 8. stitched 总则

本篇和 `05` 的边界直接写死：

1. `04` 负责窗口级执行、跨窗注入、窗口正式结果与 stitched 上游输入准备。
2. 正式 stitched backtest 真值由 `05` 定义的 segmented replay 方案生成。
3. 本篇 stitched 阶段产出的是交给 `05` 的 stitched 输入。

先把 stitched 正式产物压成一张表：

| 产物 | 正式来源 | 说明 |
| --- | --- | --- |
| `stitched_data` | 从最初输入的 `full_data: DataPack` 上按 stitched 全局 `test_active` 时间范围重新切片 | 不是窗口 `DataPack` 直接拼接 |
| `window_active_results` | 对每个窗口执行 `extract_active(...)` 后得到的 `test_active_result` | stitched 后续只允许消费这组 active 结果 |
| `stitched_signals` | 各窗口 `test_active_result.signals` | 也就是窗口 `final_signals` 的 active-only 可见部分；直接继承窗口正式信号语义 |
| `backtest_schedule` | `window_results[i].meta.best_params.backtest` + `test_active_base_row_range` 重基 | replay 的正式 schedule 输入 |
| `stitched_atr_by_row` | stitched 阶段按 schedule 语义物化 | 只有 schedule 需要 ATR 时才存在 |
| `stitched_indicators_with_time` | stitched 阶段 own algorithm 产物 | 最终回灌 `build_result_pack(...)` 前仍需先降级成 raw indicators |

补充硬约束：

1. stitched 只消费各窗口的 `test_active_result`。
2. `window_results[i].meta.best_params.backtest` 在 stitched / replay 链上只按各字段 `.value` 解释。
3. 各窗口 `ResultPack` 字段若参与 stitched，只允许作为：
   - 正式信号语义来源
   - 可选指标 / 调试产物来源
   - 输入一致性校验来源
4. 正式 stitched backtest 真值来源是 `05` 的 segmented replay 输出。
5. 最终 stitched 产物里不允许保留重复时间：
   - `base` 轴不允许重复时间；一旦重复直接报错
   - 非 base `source / indicators` 在相邻窗口 `test_active` 边界处最多只允许 1 根时间重叠
   - 若恰好重叠 1 根，按“后窗口覆盖前窗口”处理
   - 若重叠超过 1 根，直接报错
6. 本项目彻底不兼容 renko 等重复时间戳 source；若任一窗口内部本身存在重复时间戳，直接报错。

## 9. stitched 算法

```rust
fn stitch_window_results(
    window_results: &[WindowArtifact],
    full_data: &DataPack,
) -> StitchedArtifact
```

本篇只保留 `04` 自己负责的 stitched 上游步骤；真正的 segmented replay 与通用 kernel 细节统一引用 `05`。

步骤：

1. stitched 发生在所有窗口都已经执行完成、`window_results` 已经完整产出之后。
2. 先从 `window_results` 里取：
   - `first_window = window_results.first()`
   - `last_window = window_results.last()`
3. 再确定 stitched 的全局 `test_active` 时间范围，并据此落成 `stitched_pack_time_range_from_active`：
   - `stitched_pack_time_range_from_active.start = first_window.meta.test_active_time_range.start`
   - `stitched_pack_time_range_from_active.end = last_window.meta.test_active_time_range.end`
   - 这里直接使用 [04_walk_forward_and_stitched_2_window_execution_and_return.md](./04_walk_forward_and_stitched_2_window_execution_and_return.md) 已定义的 `*_time_range = (start, end)` 语义：`end` 表示最后一根 bar 的时间，不是半开右边界
4. 先构造交给 `05` 的 `stitched_data: DataPack`：
   - 这里直接调用前面 `## 4` 定义好的 `slice_data_pack_by_base_window(...)`
   - 先根据 `stitched_pack_time_range_from_active` 构造一个 stitched 专用的 `WindowSliceIndices`
   - 其中 `WindowSliceIndices` 的构造方式写死为：
     - `source_ranges`
       - 对 `data.base_data_key`
         - `start_time = stitched_pack_time_range_from_active.start`
         - `end_time = stitched_pack_time_range_from_active.end`
         - `base_start_idx = exact_index_by_time(full_data.mapping.time, start_time, "mapping.time")`
         - `base_end_idx = exact_index_by_time(full_data.mapping.time, end_time, "mapping.time")`
         - `source_ranges[data.base_data_key] = [base_start_idx, base_end_idx + 1)`
       - 对每个非 base `k`
         - `src_start_idx = map_source_row_by_time(full_data.mapping.time[base_start_idx], full_data.source[k].time, k)`
         - `src_end_exclusive_idx = map_source_end_by_base_end(full_data.mapping.time, full_data.source[k].time, base_end_idx + 1, k)`
         - `source_ranges[k] = [src_start_idx, src_end_exclusive_idx)`
       - stitched 的 source 覆盖要求只覆盖全局 `test_active` 区间
     - `ranges_draft`
       - 对所有 `k` 都写成零预热：
       - `warmup_bars = 0`
       - `pack_bars = source_ranges[k].end - source_ranges[k].start`
       - `active_bars = pack_bars`
   - 然后显式调用：
     - `stitched_data = slice_data_pack_by_base_window(full_data, stitched_indices)`
   - `stitched_data` 来自原始 `full_data` 切片，而不是窗口 `DataPack` 拼接
5. 先对每个 `window_result` 提取 `test_active` 结果视图：
   - `window_result.test_pack_data / test_pack_result` 包含测试预热
   - 因此 stitched 前，直接复用 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 里定义的 `extract_active(...)`
   - 对每个 `window_result` 执行：
     - `(_, test_active_result) = extract_active(window_result.test_pack_data, window_result.test_pack_result)`
   - 最终保留：
     - `window_active_results: Vec<ResultPack>`
     - 其中每个元素都是对应窗口的 `test_active_result`
   - 这里的总原则再写死一次：
     - stitched 后续只消费 `window_active_results`
6. 再按窗口顺序准备交给 `05` 的 stitched replay 输入：
   - `stitched_signals: DataFrame`
     - 行空间直接来自各窗口 `test_active_result.signals`
     - 语义等于各窗口 `final_signals` 的 active-only 可见部分
     - 当前正式语义下，跨窗 carry 开仓写在 active 第一根，因此 `extract_active(...)` 会保留 carry 行
     - stitched 正式信号直接继承窗口正式结果的跨窗注入与窗口尾部强平语义
     - 拼接算法写死如下：
       - 对任意相邻窗口 `i, i+1`，先比较：
         - `current_end_time = window_active_results[i].mapping.time.last()`
         - `next_start_time = window_active_results[i + 1].mapping.time.first()`
       - 必须满足：
         - `next_start_time > current_end_time`
       - 若不满足，直接报错
       - 只有在这条 base 轴严格单调无重叠成立时，才允许按窗口顺序直接拼接 `signals`
   - `backtest_schedule: Vec<BacktestParamSegment>`
     - 每段参数直接来自对应窗口 `window_results[i].meta.best_params.backtest`
     - 每段行区间直接来自 `test_active_base_row_range` 的重基结果。
     - stitched 阶段只允许消费各窗口已经保存好的：
       - `window_results[i].meta.test_active_base_row_range`
     - 这条区间是真正的单一来源：
       - 它表示当前窗口 `test_active` 在原始 WF 输入 `DataPack.base` 轴上的绝对半开区间
       - 不属于 stitched 行轴，也不是窗口局部重基后的行号
       - 它在窗口执行阶段只是从 `build_window_indices(...)` 产出的窗口切分真值透传进 `WindowMeta`
       - stitched 阶段不允许再按 `mapping.height()` 或时间范围重新推一次原始区间
     - stitched 这里只做重基：
       - 取 `base0 = window_results[0].meta.test_active_base_row_range.start`
       - 对每个窗口 `i`，记：
         - `original_start_i = window_results[i].meta.test_active_base_row_range.start`
         - `original_end_i = window_results[i].meta.test_active_base_row_range.end`
       - 定义：
         - `start_row_i = original_start_i - base0`
         - `end_row_i = original_end_i - base0`
       - 再产出：
         - `BacktestParamSegment { start_row: start_row_i, end_row: end_row_i, params: window_results[i].meta.best_params.backtest }`
     - 因而 stitched `backtest_schedule: Vec<BacktestParamSegment>` 不是第二次窗口规划，而只是对窗口切分真值做重基投影。
     - 这里的 `start_row / end_row` 统一采用 stitched 绝对行轴上的半开区间语义 `[start_row, end_row)`
     - 重基后必须补五条硬校验：
       - `original_end_i > original_start_i`
       - 对任意相邻窗口：
         - `next.original_start == current.original_end`
       - `end_row_i - start_row_i == window_active_results[i].mapping.height()`
       - 最终 `last_end_row == stitched_signals.height()`
       - 最终 `last_end_row == stitched_data.mapping.height()`
     - 若 `stitched_atr_by_row.is_some()`，还必须满足：
       - `stitched_atr_by_row.len() == last_end_row`
   - `stitched_atr_by_row: Option<Series>`
     - 若 segmented replay 需要，则在 stitched 阶段一并物化
     - 其正式物化算法也在 stitched 阶段写死：

```text
segment_has_any_atr_param =
    [
        segment.params.validate_atr_consistency()?
        for segment in backtest_schedule
    ]

resolved_atr_periods_by_segment =
    [
        if segment_has_any_atr_param[i] {
            segment.params.atr_period.as_ref().unwrap().value as i64
        } else {
            None
        }
        for (i, segment) in enumerate(backtest_schedule)
    ]

has_any_schedule_atr_param =
    any(segment_has_any_atr_param)

if !has_any_schedule_atr_param:
    stitched_atr_by_row = None
else:
    unique_resolved_atr_periods =
        unique(non_null(resolved_atr_periods_by_segment))
    # 这里只是为了避免对相同 atr_period 重复计算 full-series ATR cache；
    # 不会丢段，因为后面仍按完整的 resolved_atr_periods_by_segment 和 backtest_schedule 顺序逐段取 slice

    base_ohlcv =
        stitched_data.base.select(["high", "low", "close"])

    atr_series_by_period = {}

    for p in unique_resolved_atr_periods:
        atr_series_by_period[p] =
            atr_eager(base_ohlcv, ATRConfig::new(p))
        # 返回一条与 stitched_data.base 等长的 Polars Series

    atr_segment_slices = []

    for (segment, resolved_atr_period_i) in zip(backtest_schedule, resolved_atr_periods_by_segment):
        if resolved_atr_period_i.is_some():
            atr_segment_slices.push(
                atr_series_by_period[resolved_atr_period_i].slice(
                    offset = segment.start_row,
                    length = segment.end_row - segment.start_row,
                )
            )
        else:
            atr_segment_slices.push(
                full_null_series(length = segment.end_row - segment.start_row)
            )

    stitched_atr_by_row =
        pl.concat(atr_segment_slices)
```

     - 上面这段伪代码的行级语义可以直接理解成：
       - 若某个 stitched 绝对行号 `row` 落在第 `i` 段
       - 且该段 `segment.params.validate_atr_consistency()? = true`
       - 则 `stitched_atr_by_row[row]` 必须直接取自：
         - `atr_series_by_period[resolved_atr_period_i][row]`
       - 若该段 ATR 逻辑未启用，则该段对应切片直接填 `null`
       - 这里的 `full_null_series(...)` 只是表达“构造一段与 segment 长度相同的全 null Polars Series”，不是新的业务 helper
       - 也就是说，先在 stitched 全局 base 轴上把 ATR 按 period 整条算好，再按 segment 把对应行区间切出来
     - 这里不允许按 row 做逐行 for 循环物化 ATR；真正允许的结构性循环只有：
       - 按 unique ATR period 计算缓存
       - 按 segment 做向量化 slice + concat
     - 这段伪代码依赖 Polars 的向量化 API：
       - `DataFrame.select(...)`
       - `Series.slice(...)`
       - `pl.concat(...)`
       而不是按 row 逐个取值
     - 这里还要把“复用现有实现”和“伪代码占位”区分写死：
       - 必须直接复用现有实现：
         - `segment.params.validate_atr_consistency()?`
         - `atr_eager(base_ohlcv, ATRConfig::new(p))`
       - 必须直接复用现有字段取值语义：
         - `segment.params.atr_period.as_ref().unwrap().value as i64`
       - 不应再额外新建同义业务 helper，例如：
         - `segment_uses_any_atr_logic(...)`
         - `resolve_schedule_segment_atr_period(...)`
         - `calculate_atr_series(...)`
       - 这里只允许把这些现有实现包进局部变量或伪代码步骤名里，不允许再造一层平行语义
       - `unique(...)`、`non_null(...)`、`pl.concat(...)`、`full_null_series(...)` 这些只是集合处理 / Polars API / 伪代码占位，不是新的业务真值函数
     - 这样做的语义是：
       - ATR 真值先在 stitched 全局 base 轴上按 period 向量化计算
       - schedule 只负责从这些 full-series cache 中切出对应区间并拼回 stitched 行轴
     - 其双层校验统一引用 `05`
7. 再构造最终 `stitched_result` 所需的 `stitched_indicators_with_time`：
   - `stitched_indicators_with_time` 是 stitched 阶段 owned algorithm 的正式产物
   - 它已经属于结果态 indicators，带 `time` 列
   - 它最终仍对应 `stitched_result` 的正式指标字段，但在回灌 `build_result_pack(...)` 前必须先降级回 raw indicators
   - 这里不重新调用 `map_source_row_by_time(...)` 或别的 source mapping helper
   - 原因是 `window_active_results[i].indicators[k]["time"]` 这列本身就已经由 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 中 `build_result_pack(...)` 从同源 `DataPack.source[k]["time"]` 注入
   - 而 stitched 前对窗口做的 `extract_active(...)` 又只会做同源切片与重基，不会改变这条 source-local 时间语义
   - 因此 stitched indicators 的拼接，直接按 `indicators[k]["time"]` 比较即可；这里比较的已经是对应 source 上的正式时间真值，不需要第二次 mapping 计算
   - 其中 stitched indicators 的拼接规则写死为：
     - 对任意相邻窗口 `i, i+1`，先比较 `window_active_results[i].indicators[k]["time"].last()` 与 `window_active_results[i + 1].indicators[k]["time"].first()`
     - 若后者大于前者，直接追加
     - 若两者相等，用后窗口覆盖前窗口
     - 若后者小于前者，直接报错
   - 指标拼完后还必须补一条对齐校验：
     - 对每个保留的 `k`，`stitched_indicators_with_time[k]["time"] == stitched_data.source[k].time`
     - 若不一致，直接报错
     - 若后续还要校验 `mapping`，校验目标也必须是映射后的时间语义一致，而不是裸整数索引值一致
   - 这些指标拼接规则属于 `04` 的 owned algorithm
   - 若还需窗口级调试 artifact，可以从 `window_active_results` 中单独准备，但这不影响 stitched indicators 的正式必需地位
   - 但这里还要把总契约写死：
     - `stitched_indicators_with_time` 不能直接喂给最终 `build_result_pack(...)`
     - 在最终生成新的独立 `stitched_result` 前，必须先统一调用 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 中定义的 `strip_indicator_time_columns(...)`
     - 得到 `stitched_raw_indicators`
     - 再把 `stitched_raw_indicators` 作为 `build_result_pack(...)` 的正式 indicators 入参
8. 最后把这些交给 `05`：
   - `stitched_data`
   - `stitched_indicators_with_time`
   - `stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
   交给 [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md) 定义的 segmented replay 链路，生成最终 `stitched_result`
   - 最终结果保存 replay 实际使用的这份 `backtest_schedule` 到 `stitched_result.meta.backtest_schedule`
   - 因为最终多段 backtest 输出的解释层仍要依赖这份正式 schedule 元数据
   - 这里的保存动作必须直接复用 replay 实际使用并已完成 contiguity / 长度校验的同一份 `backtest_schedule`
   - 不允许在 replay 完成后，再依据 `stitched_result.backtest` 二次计算或重新生成另一份 `meta.backtest_schedule`

这条边界要写死：

1. `04` 负责窗口级真值与 stitched 上游输入准备。
2. `05` 负责正式 stitched backtest 真值生成。
3. `04` 的正式 stitched 输入链不包含 `stitched_result_pre_capital + capital rebuild` 这条路线。
4. stitched 正式信号只拼 active-only 的 `test_active_result.signals`：
   - 不拼完整 `test_pack_result.signals`
   - 当前方案接受 carry 开仓保守延后一根 active bar，以换取 stitched 输入行轴完全自洽

## 10. stitched 为什么不直接拼窗口 DataPack / backtest

原因现在可以一起写清楚：

1. 大周期 source 在相邻 `test_active` 窗口边界处很可能共享同一根 bar，因此窗口级 `DataPack` 不适合作为 stitched 真值直接拼接。
2. 同理，窗口级 `backtest` 不适合作为 stitched 正式真值来源；因为那条路会再次回到“先拼局部结果，再补全局资金列”的混合口径。
3. 因此当前对齐 `05` 后的正式方向是：
   - `stitched_data` 以初始 `full_data` 切片为真值
   - stitched 正式信号直接继承窗口 `final_signals` 的 active-only 可见部分
   - stitched 正式 backtest 统一由 segmented replay 一次性连续生成
