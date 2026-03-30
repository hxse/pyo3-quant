# 回测主流程、ResultPack 构建与非预热切片

本篇承接 DataPack，描述：

1. 单次回测主流程。
2. `ResultPack` 的构建入口。
3. 非预热切片 `extract_active(...)`。

本篇直接复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 已定义的共享内容：

1. `DataPack / ResultPack / SourceRange` 的通用结构
2. `mapping` 通用约束
3. 指标契约与 warmup 命名
4. builder 收口原则

因此下文不再重复解释这些共享定义本身，只补三类本章增量语义：

1. 单次回测如何消费当前 `DataPack.ranges`
2. `build_result_pack(...)` 如何把结果字段落成 `ResultPack`
3. `extract_active(...)` 作为 active 视图例外入口时的专属规则

## 1. 全量回测主流程

```text
输入: DataPack(全量,含预热)
输出: ResultPack(全量,含预热)

1. 指标计算: 全量 source -> indicators
2. 信号生成: 全量 base -> signals
3. 回测执行: 全量 base -> backtest
4. 绩效计算: `analyze_performance(data, backtest, performance_params)` 仍然接受全量 `DataPack` 和全量 `backtest`
5. 绩效统计口径: 函数内部根据当前 `DataPack.ranges`，只统计非预热段 `[data.ranges[data.base_data_key].warmup_bars, data.ranges[data.base_data_key].pack_bars)`
```

### 1.1 预热段禁开仓

旧机制依赖 `has_leading_nan`。

新机制明确改成：

1. 以 `ranges[base].warmup_bars` 作为唯一预热边界。
   - 这里的 `ranges[base].warmup_bars` 按 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 的共享定义理解，表示最终落地到当前 `DataPack` 的真实预热边界。
   - 它可能同时包含：
     - 指标 warmup
     - backtest exec warmup
2. 对 `[0, ranges[base].warmup_bars)`：
   - `entry_long = false`
   - `entry_short = false`
3. 这个“预热禁开仓”规则属于信号模块内部职责：
   - 信号模块在输出 `signals` 时，就必须按 `ranges[base].warmup_bars` 自动把预热段开仓置为 `false`
   - 回测阶段和 WF 都只复用这份统一信号输出，不再额外处理第二遍
4. `exit_long / exit_short` 不强改，但预热段本来也不会有持仓。
5. `has_leading_nan` 仍然保留，但只作为外部调试辅助字段：
   - 只保留在 `signals` 输出里
   - 不再透传到 `backtest` 输出里
   - 不再参与 `performance` 输出或绩效计算

当前代码现状需要特别说明：

1. `src/backtest_engine/backtester/mod.rs` 目前仍会把 `signals.has_leading_nan` 透传到 `backtest`
2. `src/backtest_engine/performance_analyzer/mod.rs` 目前仍会从 `backtest_df` 读取 `has_leading_nan`
3. 本次重构目标是把这两处清掉，收口为“仅 signals 保留、仅供调试”

### 1.1.1 绩效函数的目标口径

为了和单次回测、WF 窗口回测保持统一，绩效函数的目标语义直接定成：

1. `analyze_performance(...)` 接受的是全量 `DataPack` 和全量 `backtest`
2. 外部不需要先手工切成非预热段再计算绩效
3. 这个“只统计非预热段”的规则属于绩效模块内部职责：
   - `analyze_performance(...)` 在内部根据当前 `DataPack.ranges[data.base_data_key].warmup_bars` 只统计非预热区
   - 单次回测和 WF 都直接复用这套行为
4. 因此单次回测和 WF 都统一成“回测完成后直接算绩效”，不再额外发明一套外部切片后再算绩效的流程
5. 关键执行顺序要写死：
   - 先拿到当前 pack 的 `DataPack`
   - 再生成完整 `backtest`
   - 然后立刻调用 `analyze_performance(data, backtest, performance_params)`
   - 最后再把 `performance` 写入 `ResultPack`
6. 因此绩效函数不依赖尚未构建完成的 `ResultPack`，只依赖当前 `DataPack` 和当前 `backtest`

`analyze_performance(...)` 的输入前置校验也要写死：

1. 在进入任何非预热切片与统计前，必须先校验：
   - `backtest.height() == data.mapping.height()`
2. 若不满足，`analyze_performance(...)` 必须直接报错，不允许默认相信上游继续统计。
3. 原因是绩效模块执行早于 `build_result_pack(...)`，因此不能把这条输入一致性校验延后给 `build_result_pack(...)` 兜底。

绩效模块内部的关键切片步骤也要写死：

1. 先取当前 base 边界：
   - `base_warmup = data.ranges[data.base_data_key].warmup_bars`
   - `base_pack_bars = data.ranges[data.base_data_key].pack_bars`
2. 这里的对象来源必须写死：
   - `data` 指当前正在计算绩效的那份 `DataPack`
   - `backtest` 指与这份 `data` 同源的完整 `backtest DataFrame`
   - 此时 `ResultPack` 还没有构建完成，因此绩效模块内部不能依赖 `ResultPack`
3. 绩效模块内部只按 base 行空间切片，不对 `data.source[k]` 或 `indicators[k]` 做额外切片。
4. 内部至少切两样东西：
   - `active_base_time = data.mapping["time"][base_warmup..base_pack_bars]`
     - 这个时间列来自当前 `DataPack.mapping`
   - `active_backtest = backtest[base_warmup..base_pack_bars]`
     - 这个表来自当前完整 `backtest DataFrame`
5. 再把切片出来的 `active_base_time` 附加到切片后的 `active_backtest` 上：
   - 得到新的 `active_backtest_with_time`
   - 这样绩效模块后续可以直接基于“带时间列的回测结果”做统计
   - 这一步只作用于绩效模块内部的新视图，不回写原始 `backtest`
6. 后续所有绩效统计都只基于：
   - `active_backtest_with_time`
7. 因此“切片算法”属于绩效模块内部实现细节：
   - 外部调用方只传完整 `DataPack + backtest`
   - 由 `analyze_performance(...)` 在模块内部先完成这一步 base 轴切片
8. 单次回测、WF、stitched 都复用同一口径：
   - 谁调用绩效模块，谁传当前 pack 对应的完整 `DataPack`
   - 绩效模块内部再统一裁掉 `[0, base_warmup)` 这段预热区

### 1.2 指标 NaN 校验

这部分不在回测主流程里再额外定义第二套更严规则，而是直接复用指标契约。

当前实际设计与 pytest 现状：

1. 指标实例在 Rust 侧已经定义：
   - `required_warmup_bars(...)`
   - `warmup_mode()` (`Strict / Relaxed`)
2. pytest 已有对应契约测试：
   - `py_entry/Test/indicators/test_indicator_warmup_contract.py`
3. 该测试的口径就是当前唯一真值：
   - `warmup == 各输出列前导缺失数量的最大值`
   - `Strict`：非预热段不允许再出现缺失
   - `Relaxed`：非预热段允许结构性缺失，但不允许整行全空

因此本篇只直接引用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里的指标契约定义，不在回测阶段重新追加一层独立 NaN 校验算法。

## 2. ResultPack 构建入口

```rust
fn build_result_pack(
    data:        &DataPack,
    indicators:  Option<HashMap<String, DataFrame>>,
    signals:     Option<DataFrame>,
    backtest:    Option<DataFrame>,
    performance: Option<HashMap<String, f64>>,
) -> Result<ResultPack, QuantError>
```

这里对 `indicators` 再写死一条契约：

1. 只要 `build_result_pack(...)` 收到了 `indicators`，就必须统一为每个 `indicators[k]` 补入 `time` 列。
2. 因此“`ResultPack.indicators[k]` 必须带 `time` 列”是 `build_result_pack(...)` 的正式职责，不要求指标计算模块自己承担。
3. 指标计算模块原始输出可以仍然只包含指标列，不要求每个指标 pipeline 自己携带 `time`。
4. 但一旦进入 `build_result_pack(...)`，若 `indicators[k]` 存在，则 `build_result_pack(...)` 必须统一为它补入 `time` 列。
5. 若上游 `indicators[k]` 已经包含同名 `time` 列，则 `build_result_pack(...)` 必须直接报错，不做覆盖、不做兼容。
6. 这条 `time` 列直接复制自对应的 `data.source[k]["time"]`。
7. 补入前必须先校验：
   - `indicators[k].height() == data.source[k].height()`
8. 补入后必须再校验：
   - `indicators[k]["time"] == data.source[k]["time"]`
9. 因此 `ResultPack.indicators[k]` 的正式契约不是“纯指标列 DF”，而是“带 `time` 列的指标结果 DF”。

使用场景只有一类抽象：

1. 只要要产出一个新的独立 `ResultPack`，就调用一次 `build_result_pack(...)`。
2. 具体包括：
   - 单次回测尾部
   - WF 窗口级切片
   - stitched 拼接
3. 这些场景的共同前提都是：调用前必须已经有对应的新 `DataPack`。
4. 因此这里直接依赖 `DataPack`，不再把 `base_times / ranges / base 身份` 拆成零散参数传入。
5. 它仍然保留 PyO3 暴露，主要服务 Python 侧测试、调试和最小构造场景。

这里再补一条非常关键的衔接规则：

1. `build_result_pack(...)` 的 `indicators` 入参，正式语义是“raw indicators”，也就是**还没带 `time` 列**的指标结果。
2. 因此：
   - 指标计算模块的原始输出，可以直接喂给 `build_result_pack(...)`
   - 但若上游手里拿到的是某个已有 `ResultPack.indicators`，它已经属于“带 `time` 列”的结果态，不能直接再喂回 `build_result_pack(...)`
3. 只要要把已有 `ResultPack.indicators` 再喂回 `build_result_pack(...)`，必须先走统一 helper：
   - `strip_indicator_time_columns(...)`
4. 这条规则尤其直接约束两类链路：
   - WF 主流程里复用 `raw_signal_stage_result.indicators`
   - stitched 里把 `window_active_results[*].indicators` 拼完后再回灌 `build_result_pack(...)`
5. 这里禁止在各处手写 `drop(\"time\")`；一律通过同一个 helper 降级回 raw indicators，避免再次出现多处各写一套处理。

```rust
fn strip_indicator_time_columns(
    indicators_with_time: &HashMap<String, DataFrame>,
) -> Result<HashMap<String, DataFrame>, QuantError>
```

`strip_indicator_time_columns(...)` 的职责写死为：

1. 输入必须是已经属于 `ResultPack.indicators` 形态的指标结果，也就是每个 `indicators[k]` 都带 `time` 列。
2. 对每个 `k`：
   - 若缺少 `time` 列，直接报错
   - 若存在多个同名 `time` 列，直接报错
   - 否则只移除这一个 `time` 列，保留其余指标列
3. 返回结果就是可以再次喂给 `build_result_pack(...)` 的 raw indicators。
4. 它只负责“去掉结果态 `time` 列”，不负责修改其余列名、行数或顺序。

## 3. ResultPack 构建规则

`build_result_pack(...)` 只做五件事：

1. 继承 `data` 的 base 身份：
   - `ResultPack.base_data_key = data.base_data_key`
2. 继承 `data` 的 mapping / ranges 子集：
   - `ResultPack.mapping` 直接取 `data.mapping` 的子集，字段集合为 `indicator_source_keys + time`
   - `ResultPack.ranges` 直接取 `data.ranges` 的子集，字段集合为 `data.base_data_key + indicator_source_keys`
   - 这里只裁掉不需要的字段，不做索引裁减、重基或重新编号
3. 直接接受并写入入参结果字段：
   - `indicators`
   - `signals`
   - `backtest`
   - `performance`
4. 做最小机械一致性校验：
   - `signals.height == data.mapping.height()`（若存在）
   - `backtest.height == data.mapping.height()`（若存在）
   - `indicator_source_keys ⊆ data.source.keys()`
   - `ranges[base].pack_bars == data.mapping.height()`
   - 若 `indicators[k]` 存在，则 `ranges[k].pack_bars == indicators[k].height()`
5. 不重新构建 mapping：
   - `mapping.time` 直接来自 `data.mapping.time`
   - `base` 的相关语义直接来自 `ResultPack.base_data_key`

调用方只需要保证一件事：

1. 传进来的 `data` 必须是当前结果字段的同源 `DataPack`。
2. 若这里的 `data` 是切片后的 `DataPack`，则调用方必须先保证该切片结果本身已经正确。
3. 若这里的 `data` 是 stitched 后的 `DataPack`，则调用方必须先保证 stitched 的 `source / mapping / ranges` 都已经拼对。
4. `build_result_pack(...)` 不负责修正错误的 `DataPack` 输入；若上游 `DataPack` 来源不对，结果也不可能对。

## 4. 非预热切片 `extract_active(...)`

这里是 [01_overview_and_foundation_2_types_and_mapping.md](./01_overview_and_foundation_2_types_and_mapping.md) `3.6 校验收口原则` 的唯一例外：

1. `extract_active(...)` 不负责重新构建一个可继续运行的新 Pack。
2. 它只对一对已经同源且已验证的 `DataPack / ResultPack` 做机械化非预热提取。
3. 因此这里允许不调用 `build_data_pack(...)` / `build_result_pack(...)`，而是直接构造新的 active 视图对象。

```rust
fn extract_active(
    data:   &DataPack,
    result: &ResultPack,
) -> (DataPack, ResultPack)
```

用途锁死：

1. `extract_active(...)` 是一个轻量的 active 视图提取函数。
2. 它直接基于当前 pack 的 `ranges` 裁掉前导预热，不调用任何 build pack 函数。
3. 典型使用场景包括：
   - 单次回测结束后，向 Python / 图表层暴露 active 视图
   - 单次回测结束后，导出 active 结果
   - stitched 前，先把每个窗口的 `test_pack_data / test_pack_result` 提取成 `test_active_data / test_active_result`
4. 它**不用于** WF 运行前的窗口切片；WF 窗口切片仍然走 `slice_data_pack_by_base_window(...)`。

返回值要求：

1. 所有 `ranges[k].warmup_bars = 0`
2. `performance` 直接继承原结果，不重算
3. `mapping` 直接重基，不重新构建
4. `new_result.ranges[new_result.base_data_key].pack_bars == new_result.mapping.height()`
5. 若 `signals / backtest` 存在，则它们的高度都必须等于 `new_result.mapping.height()`

### 4.1 DataPack / ResultPack 强一致性对照校验

`extract_active(...)` 不只是做切片，还应该在输入和输出两侧都对 `DataPack / ResultPack` 做更强的对照校验。

输入前校验：

1. `result.mapping.time == data.mapping.time`
2. `result.ranges[result.base_data_key] == data.ranges[data.base_data_key]`
3. `result.indicators.keys() ⊆ data.source.keys()`
4. 对每个 `k ∈ result.indicators.keys()`：
   - `result.ranges[k] == data.ranges[k]`
5. 对每个 `k ∈ result.mapping.columns - {"time"}`：
   - `result.mapping[k] == data.mapping[k]`
6. 若 `signals / backtest` 存在，则它们高度都必须等于 `data.mapping.height()`

输出后校验：

1. `new_result.mapping.time == new_data.mapping.time`
2. `new_result.ranges[new_result.base_data_key] == new_data.ranges[new_data.base_data_key]`
3. `new_result.indicators.keys() ⊆ new_data.source.keys()`
4. 对每个 `k ∈ new_result.indicators.keys()`：
   - `new_result.ranges[k] == new_data.ranges[k]`
   - `new_result.mapping[k] == new_data.mapping[k]`
5. 若 `signals / backtest` 存在，则它们高度都必须等于 `new_result.mapping.height()`
6. 若 `indicators[k]` 存在，则：
   - `new_result.indicators[k].height() == new_data.source[k].height()`
   - `new_result.indicators[k]["time"] == new_data.source[k]["time"]`

## 5. `extract_active(...)` 的简单设计

这里的前提非常明确：

1. 单次回测的 `performance` 本来就只基于非预热段计算。
2. `extract_active(...)` 只是把 full artifact 裁成 active view，不改变绩效口径。
3. 因此这里没必要像 WF 那样重新构建容器。

记号直接复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里的统一定义；下面不再单独发明第二套记号。

这里有一个容易踩的坑：

1. `extract_active(...)` 里一律以当前容器的 `data.ranges[k].warmup_bars` 为准。
2. 不能回退去用 `resolve_indicator_contracts(...)` 的契约聚合 warmup。
3. 原因是：当前容器里的真实前导边界，可能大于契约 warmup，因为 source 还可能为了首尾覆盖额外保留左侧 bar。

### 5.1 字段切片

DataPack：

| 字段 | 如何处理 | 说明 |
|---|---|---|
| `source[k]` | 对所有 `k` 统一做 `source[k][data.ranges[k].warmup_bars..]` | 每个 source 都直接裁掉自己当前容器里的真实前导预热段 |
| `mapping` | 走统一的 mapping 重基算法 | `DataPack.mapping` 不重建，直接切片并重基 |
| `skip_mask` | `skip_mask[data.ranges[data.base_data_key].warmup_bars..]` | `skip_mask` 挂在 base 行空间上，所以只按 base 的真实前导预热段切片 |
| `base_data_key` | 原样保留 | 切前导预热不会改变 base 身份 |
| `ranges[k]` | 对每个保留的 `k`，写成 `{ warmup_bars: 0, active_bars: data.ranges[k].active_bars, pack_bars: data.ranges[k].active_bars }` | 预热被裁掉后，新容器里的预热长度归零；剩余整包长度与有效段长度相等 |

ResultPack：

| 字段 | 如何处理 | 说明 |
|---|---|---|
| `indicators[k]` | `indicators[k][data.ranges[k].warmup_bars..]` | 指标结果按各自 source 轴存储，所以每组指标都裁掉该 source 自己的真实前导预热段 |
| `signals` | `signals[data.ranges[data.base_data_key].warmup_bars..]` | `signals` 挂在 base 行空间上；这里虽然切片动作仍以同源 `DataPack` 的 base 边界为真值，但其 base 身份与 `result.base_data_key` 相同 |
| `backtest` | `backtest[data.ranges[data.base_data_key].warmup_bars..]` | `backtest` 同样挂在 base 行空间上，切法与 `signals` 完全一致；其 base 身份也与 `result.base_data_key` 相同 |
| `performance` | 原样继承 | 单次回测的 `performance` 本来就只看非预热段，这里只是暴露 active view，不改变绩效口径 |
| `base_data_key` | 原样继承 | 切掉前导预热不会改变 `ResultPack` 的 base 身份 |
| `mapping` | 走统一的 mapping 重基算法 | `ResultPack.mapping` 的处理方式与 `DataPack.mapping` 完全一致 |
| `ranges` | 只保留 `result.base_data_key + 当前实际存在指标结果的 source`，且每个保留的 `k` 写成 `{ warmup_bars: 0, active_bars: data.ranges[k].active_bars, pack_bars: data.ranges[k].active_bars }` | `ResultPack.ranges` 只描述当前结果对象自身，且切掉前导预热后预热长度必须归零 |

### 5.2 mapping 重基算法

`extract_active(...)` 里，`DataPack.mapping` 和 `ResultPack.mapping` 的处理方式完全一致：

1. 先取 `base_cut = data.ranges[data.base_data_key].warmup_bars`
2. `mapping.time = old_mapping.time[base_cut..]`
3. 对每个保留的 `mapping[k]`：
   - 先按 base 行空间切片：`old_mapping[k][base_cut..]`
   - 再按该 source 自己被裁掉的真实前导长度重基：`new_mapping[k] = sliced_mapping[k] - data.ranges[k].warmup_bars`
4. 机械校验：
   - `base_cut < old_mapping.height()`
   - `mapping.time.height() == new_base_len`
   - `mapping.time.first() == new_source[data.base_data_key].time.first()`
   - 对每个保留的 `mapping[k]`，`mapping[k].height() == new_base_len`
   - 对每个保留的 `k`，`data.ranges[k].warmup_bars < old_source[k].height()`
   - 对每个保留的 `k`，`old_mapping[k][base_cut] >= data.ranges[k].warmup_bars`
   - 对每个保留的 `mapping[k]`，重基后的首个值必须是 `0`
   - 对每个保留的 `mapping[k]`，整列都必须满足 `0 <= mapping[k] < new_source[k].height()`
   - 若 `signals` 存在，则 `signals.height() == mapping.height()`
   - 若 `backtest` 存在，则 `backtest.height() == mapping.height()`
   - 若 `indicators[k]` 存在，则 `indicators[k].height() == new_source[k].height()`
5. 完成上述步骤后，所有 `mapping[k]` 都已经转换成“相对于新切片 source[k]”的局部索引

### 5.3 原则

1. 这里不重建 `DataPack`。
2. 这里不重建 `ResultPack`。
3. 这里不调用 `build_data_pack(...)`。
4. 这里不调用 `build_result_pack(...)`。
5. 这里只做切片、mapping 重基、字段继承，然后**直接构造**新的 `DataPack / ResultPack`。
6. 它只负责“当前 pack -> 当前 pack 的 active 视图”这类轻量后处理，不负责 WF 运行前窗口切片。
