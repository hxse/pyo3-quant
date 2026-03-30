# 向前测试、窗口切片、跨窗注入与 stitched（三）stitched 总则与算法

## 8. stitched 总则

这里直接与 [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md) 对齐，写死 stitched 的正式口径：

1. `04` 继续负责窗口级执行、跨窗注入、窗口正式结果与 stitched 上游输入准备。
2. 正式 stitched backtest 不再来自窗口 `backtest` 拼接，也不再做“先拼窗口 backtest，再重建资金列”的后处理。
3. 正式 stitched backtest 统一改由 `05` 定义的 segmented replay 方案生成。
4. 因此本篇 stitched 阶段真正要产出的，是喂给 `05` 的 stitched 输入，而不是旧的 capital rebuild 中间态。

当前任务对 stitched 的正式约束改成：

1. `stitched_data` 直接定义为：从 `run_walk_forward(...)` 最初输入的 `full_data: DataPack` 上，按 stitched 的全局 `test_active` 时间范围重新切出来的新 `DataPack`。
2. stitched 阶段只消费各窗口的 `test_active` 结果，不消费整个 `test_pack`：
   - 所有 stitched `signals / indicators / schedule` 都只能从 `extract_active(...)` 之后的 `test_active_result` 推导
   - 不能回退去直接拼整个 `test_pack_result`
3. `stitched_signals` 的正式语义，直接继承各窗口已经注入完成的 `final_signals`。
4. `backtest_schedule` 的每段参数直接来自对应窗口的 `best_params.backtest`。
5. 若 segmented replay 需要 ATR 输入，则 stitched 阶段还必须额外产出 `stitched_atr_by_row`。
6. 各窗口 `ResultPack` 字段若继续参与 stitched，只允许作为：
   - stitched 正式信号语义来源
   - stitched 可选指标 / 调试产物来源
   - stitched 输入一致性校验来源
   不能再反向充当正式 stitched backtest 真值来源。
7. 最终 stitched 产物里仍然不允许保留任何重复时间。
8. `base` 轴不允许重复时间；一旦重复，直接报错。
9. 非 base `source / indicators` 在相邻窗口的 `test_active` 边界处，最多只允许 1 根时间重叠。
10. 若非 base 边界恰好重叠 1 根，则按“后窗口覆盖前窗口”处理。
11. 若非 base 边界重叠超过 1 根，则直接报错；这说明 stitched 输入不是纯 `test_active`，或窗口切片 / source 投影存在错误。
12. 本项目彻底不再兼容 renko 等重复时间戳 source；若任一窗口内部本身存在重复时间戳，直接报错。

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
4. 再直接从初始 `full_data` 切出 stitched `DataPack` 真值：
   - 这里仍然复用前面 `## 4` 定义好的 `slice_data_pack_by_base_window(...)`
   - 先根据 `stitched_pack_time_range_from_active` 构造一个 stitched 专用的 `WindowSliceIndices`
   - 其中 `WindowSliceIndices` 的构造方式仍然写死为：
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
         - stitched 不再补预热，因此这里只要求 source 覆盖 stitched 的全局 `test_active` 区间
     - `ranges_draft`
       - 对所有 `k` 都写成零预热：
       - `warmup_bars = 0`
       - `pack_bars = source_ranges[k].end - source_ranges[k].start`
       - `active_bars = pack_bars`
   - 然后显式调用：
     - `stitched_data = slice_data_pack_by_base_window(full_data, stitched_indices)`
   - 也就是说，`stitched_data` 仍然来自原始 `full_data` 切片，而不是窗口 `DataPack` 拼接
5. 先对每个 `window_result` 提取 `test_active` 结果视图：
   - 当前 `window_result.test_pack_data / test_pack_result` 仍然包含测试预热
   - 因此 stitched 前，仍然直接复用 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 里定义的 `extract_active(...)`
   - 对每个 `window_result` 执行：
     - `(_, test_active_result) = extract_active(window_result.test_pack_data, window_result.test_pack_result)`
   - 最终保留：
     - `window_active_results: Vec<ResultPack>`
     - 其中每个元素都是对应窗口的 `test_active_result`
   - 这里的总原则再写死一次：
     - stitched 后续只允许消费 `window_active_results`
     - 不再回退去直接拼 `window_result.test_pack_result`
6. 再按窗口顺序准备 stitched 正式输入：
   - `stitched_signals`
     - 行空间直接来自各窗口 `test_active_result.signals`
     - 语义直接继承各窗口已经注入完成的 `final_signals`
     - 因此 stitched 仍然沿用窗口正式结果的跨窗注入与窗口尾部强平语义
     - 拼接算法也仍然要写死：
       - 对任意相邻窗口 `i, i+1`，先比较：
         - `current_end_time = window_active_results[i].mapping.time.last()`
         - `next_start_time = window_active_results[i + 1].mapping.time.first()`
       - 必须满足：
         - `next_start_time > current_end_time`
       - 若不满足，直接报错
       - 只有在这条 base 轴严格单调无重叠成立时，才允许按窗口顺序直接拼接 `signals`
   - `backtest_schedule`
     - 每段参数来自对应窗口的 `best_params.backtest`
     - 每段行区间直接按各窗口 `test_active_result` 在 stitched 绝对行轴上的连续范围落定
   - `stitched_atr_by_row`
     - 若 segmented replay 需要，则在 stitched 阶段一并物化
     - 其详细生成与双层校验统一引用 `05`
7. stitched 阶段必须从 `window_active_results` 中准备 stitched indicators：
   - stitched indicators 属于最终 `stitched_result` 的正式结果字段，不是可省略的特例
   - 这里不再重新调用 `map_source_row_by_time(...)` 或别的 source mapping helper
   - 原因是 `window_active_results[i].indicators[k]["time"]` 这列本身就已经由 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 中 `build_result_pack(...)` 从同源 `DataPack.source[k]["time"]` 注入
   - 而 stitched 前对窗口做的 `extract_active(...)` 又只会做同源切片与重基，不会改变这条 source-local 时间语义
   - 因此 stitched indicators 的拼接，直接按 `indicators[k]["time"]` 比较即可；这里比较的已经是对应 source 上的正式时间真值，不再需要第二次 mapping 计算
   - 其中 stitched indicators 的拼接规则仍然写死为：
     - 对任意相邻窗口 `i, i+1`，先比较 `window_active_results[i].indicators[k]["time"].last()` 与 `window_active_results[i + 1].indicators[k]["time"].first()`
     - 若后者大于前者，直接追加
     - 若两者相等，用后窗口覆盖前窗口
     - 若后者小于前者，直接报错
   - 指标拼完后还必须补一条对齐校验：
     - 对每个保留的 `k`，`stitched_indicators[k]["time"] == stitched_data.source[k].time`
     - 若不一致，直接报错
     - 若后续还要校验 `mapping`，校验目标也必须是映射后的时间语义一致，而不是裸整数索引值一致
   - 这些指标拼接规则仍然属于 `04` 的 owned algorithm，不因为正式 backtest 改由 `05` 生成而消失
   - 若还需窗口级调试 artifact，可以继续从 `window_active_results` 中单独准备，但这不影响 stitched indicators 的正式必需地位
8. 最后把：
   - `stitched_data`
   - `stitched_indicators`
   - `stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
   交给 [05_segmented_backtest_truth_and_kernel.md](./05_segmented_backtest_truth_and_kernel.md) 定义的 segmented replay 链路，生成最终 `stitched_result`

这条边界要写死：

1. `04` 负责窗口级真值与 stitched 上游输入准备。
2. `05` 负责正式 stitched backtest 真值生成。
3. `04` 不再保留旧的 `stitched_result_pre_capital + capital rebuild` 双轨口径。

## 10. stitched 为什么不直接拼窗口 DataPack / backtest

原因现在可以一起写清楚：

1. 大周期 source 在相邻 `test_active` 窗口边界处很可能共享同一根 bar，因此窗口级 `DataPack` 不适合作为 stitched 真值直接拼接。
2. 同理，窗口级 `backtest` 也不再适合作为 stitched 正式真值来源；因为那条路会再次回到“先拼局部结果，再补全局资金列”的混合口径。
3. 因此当前对齐 `05` 后的正式方向是：
   - `stitched_data` 继续以初始 `full_data` 切片为真值
   - stitched 正式信号直接继承窗口 `final_signals`
   - stitched 正式 backtest 统一由 segmented replay 一次性连续生成
