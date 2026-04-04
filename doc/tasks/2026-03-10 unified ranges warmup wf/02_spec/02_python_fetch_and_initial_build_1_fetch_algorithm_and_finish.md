# Python 网络请求、Rust 取数状态机与 DataPack 构建（一）取数算法与 finish

对应入口页：

1. [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md)

本篇只展开三件事：

1. 两阶段取数算法
2. 初始 `ranges` 如何落地
3. `finish()` 与 `build_data_pack(...)` 的唯一边界

## 1. 两阶段取数算法

这部分不要再理解成“先粗暴估一次，然后希望一次命中”。

更准确的口径是：

1. 先把 `base` 有效段拿到。
2. 再用两个统一工具函数，分别把尾部覆盖和首部预热补齐。
3. 预估永远只是首轮近似；若节假日、停盘、缺口导致估算不足，就继续按剩余缺口循环补拉。
4. 允许多取。
5. `base` 只左裁预热；`source` 不裁。

统一参数：

1. `min_request_bars`：每次循环最少补拉多少根，默认 `10`
2. 作用：避免剩余缺口很小时，每轮只加 `1~2` 根，导致请求次数过多

### 1.1 先请求 base 有效段

1. 先请求 `base`：`since=t_start, limit=L`
2. 得到 `base_effective_df` 后，记录：
   - `base_effective_start_time = base_effective_df.time.first()`
   - `base_effective_end_time = base_effective_df.time.last()`
3. 这里不要假设 `base_effective_start_time == since`
4. `base_effective_df.height()` 必须严格等于 `L = effective_limit`
   - 若 `< L`，直接 fail-fast
   - 当前方案不为 `base` 增加“右侧补拉到凑满 L 根 live bar”的第二套分支
5. 一切后续计算都以**真实返回时间列**为准，不直接拿请求参数时间戳代替

### 1.2 Rust 内部方法一：补齐尾部覆盖

方法名：`ensure_tail_coverage(...)`

作用：

1. 给定目标尾部时间 `target_end_time`
2. 估算当前还差多少根 bar 才能覆盖到右边界
3. 若估算不足，就继续增大 `limit` 循环请求
4. 直到满足尾覆盖：
   - `last_time + interval_ms > target_end_time`

每轮公式：

1. `covered_end_time = last_time + interval_ms`
2. `missing_ms = max(target_end_time - covered_end_time, 0)`
3. `missing_bars = ceil(missing_ms / interval_ms) + 1`
4. `append_bars = max(missing_bars, min_request_bars)`
5. 重新请求时：
   - `since` 不变
   - `limit += append_bars`

这里的 `ensure_tail_coverage(...)` 明确是 **Rust 状态机内部工具函数**，Python 不负责实现这段逻辑。
当前 source 的 `since / limit / df` 都由状态机自己持有和更新；这个方法的职责是循环补拉并更新状态机内部的当前请求状态，而不是单独返回一个 `df`。

### 1.3 Rust 内部方法二：补齐首部时间覆盖

方法名：`ensure_head_time_coverage(...)`

作用：

1. 只处理左侧时间覆盖不足。
2. 每轮请求后，都用**真实返回时间列**重新判断：
   - `first_time <= target_start_time`
3. 若不满足，就继续前移 `since` 并扩大 `limit`。

这里的变量来源：

1. `first_time`
   - 就是当前这轮返回 DF 的第一根时间
   - 即 `df.time.first()`
2. `target_start_time`
   - 就是当前这份数据至少要覆盖到的目标起点时间
   - `base` 时：`target_start_time = base_effective_start_time`
   - `source` 时：`target_start_time = base_full_start_time`
   - 其中 `base` 路径是数学上的 no-op：
     - 当前 `df` 就是 `base_effective_df`
     - 因而 `first_time == base_effective_start_time == target_start_time`
     - 这一步保留只是为了状态机步骤对称，不表示 `base` 还要额外做一轮左侧时间覆盖补拉

每轮公式：

1. `missing_by_head_coverage = ceil(max(first_time - target_start_time, 0) / interval_ms)`
2. `prepend_bars = max(missing_by_head_coverage, min_request_bars)`
3. 重新请求时：
   - `since = old_since - prepend_bars * interval_ms`
   - `limit += prepend_bars`

这里的 `ensure_head_time_coverage(...)` 是 **Rust 状态机内部方法**，Python 不负责实现这段逻辑。
当前 source 的 `since / limit / df` 都由状态机自己持有和更新。

### 1.4 Rust 内部方法三：补齐首部预热数量

方法名：`ensure_head_warmup_bars(...)`

作用：

1. 只处理左侧预热 bar 数量不足。
2. 每轮请求后，都用**真实返回时间列**重新判断：
   - 把 `anchor_time` 映射到当前 `src_times`
   - 得到 `mapped_src_idx`
   - 要求 `mapped_src_idx >= required_bars`

这里的变量来源：

1. `anchor_time`
   - 是用来检查“左侧是否已经拿到足够预热 bar”的锚点时间
   - `base` 时：`anchor_time = base_effective_start_time`
   - `source` 时：`anchor_time = base_first_live_time`
2. `mapped_src_idx`
   - 用严格 backward asof 把 `anchor_time` 映射到当前 `src_times` 后得到的 source 行索引
   - 这里必须直接复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里定义的统一时间投影工具函数 `map_source_row_by_time(...)`
   - 也就是说，和 `build_mapping_column_unchecked(...)` 构建 mapping 时使用的是**同一套** Polars backward asof 向量化能力，不额外发明第二套映射逻辑
3. `required_bars`
   - 不是重新估算 warmup
   - `base` 时：`required_bars = W_required[base]`
   - `source` 时：`required_bars = W_required[k]`

每轮公式：

1. `missing_by_warmup = max(required_bars - mapped_src_idx, 0)`
2. `prepend_bars = max(missing_by_warmup, min_request_bars)`
3. 重新请求时：
   - `since = old_since - prepend_bars * interval_ms`
   - `limit += prepend_bars`

这里的 `ensure_head_warmup_bars(...)` 也是 **Rust 状态机内部方法**，Python 不负责实现这段逻辑。
当前 source 的 `since / limit / df` 同样由状态机自己持有和更新。

### 1.5 Rust 侧主流程：先 base，再 source

1. 先取到 `base_effective_df`
   - 且它必须已经满足 `base_effective_df.height() == effective_limit`
2. 用 `ensure_head_time_coverage(...)` 补齐 `base` 左侧时间覆盖
   - `target_start_time = base_effective_start_time`
   - 这一步固定直接通过，不触发额外补拉；保留该调用只为统一状态机步骤
3. 再用 `ensure_head_warmup_bars(...)` 补齐 `base` 自己的预热
   - `anchor_time = base_effective_start_time`
   - `required_bars = W_required[base]`
4. `base` 补完预热后，只做一次**左侧精确裁减**：
   - 在补完后的 `base_full_raw` 里找到 `base_effective_start_time` 对应的索引 `live_start_idx`
   - `base_slice_start = live_start_idx - W_required[base]`
   - `base_full_df = base_full_raw[base_slice_start..]`
5. 这里不裁右侧：
   - `limit = L` 的语义本来就是“需要 L 根非预热 base bar”
   - 因此 `base` 只裁多出来的左侧预热，不额外裁减右侧
6. 得到最终 `base_full_df` 后，记录：
   - `base_full_start_time = base_full_df.time.first()`
   - `base_full_end_time = base_full_df.time.last()`
   - `base_first_live_time = base_full_df.time[W_required[base]]`
7. 对每个非 base source `k`：
   - 首轮请求：
     - `since = base_full_start_time`
     - `limit = ceil((base_full_end_time - base_full_start_time) / interval_ms(k)) + 1`
   - 先调用 `ensure_tail_coverage(...)`
     - 目标：`base_full_end_time`
   - 再调用 `ensure_head_time_coverage(...)`
     - `target_start_time = base_full_start_time`
   - 再调用 `ensure_head_warmup_bars(...)`
     - `anchor_time = base_first_live_time`
     - `required_bars = W_required[k]`
8. 若任一循环达到重试上限仍未满足条件，直接报错

最终状态：

1. `base_full` 已包含完整预热段与有效执行段
2. 所有 `source` 都对 `base_full` 完成**全量覆盖**
3. 所有 `source` 都已满足各自的最终 required warmup
4. `base` 只裁减多出来的左侧预热，不裁右侧
5. `source` 允许多取，但不做隐式裁减
6. 因此后续构建出来的 mapping 列不允许出现 null

## 2. Rust 侧初始 ranges 计算

这一步在 Rust 取数状态机内部完成，而且直接基于**真实返回时间列**计算，不使用预估值。

### 2.1 base 的 ranges

1. `ranges[base].warmup_bars = W_required[base]`
2. `ranges[base].pack_bars = source[base].height()`
3. `ranges[base].active_bars = ranges[base].pack_bars - ranges[base].warmup_bars`

这里有一个前提：

1. 前面已经对 `base` 做过精确的左侧预热裁减
2. 因此这里的 `source[base]` 已经是“左侧恰好保留 `W_required[base]` 根预热”的最终 `base_full`

这里保留两个状态机内部一致性断言：

1. `source[base].height() >= W_required[base] + 1`
2. `source[base].time[W_required[base]] == base_effective_start_time`

若任一不成立，直接报错，说明前面的 `base` 预热补拉或左侧精确裁减位置错误。

### 2.2 非 base source 的 ranges

核心思想：

1. 只看 base 的首个非预热 bar。
2. 看它在 source `k` 上严格 backward asof 映射到哪一根。
3. 该根之前的所有行，就是 source `k` 的预热段。

算法：

1. 取 `base_first_live_time = source[base].time[W_required[base]]`
2. 对每个非 base `k`：
   - 只探测这一根 `base_first_live_time`
   - 直接复用统一时间投影工具函数 `map_source_row_by_time(base_first_live_time, source[k].time, k)`，得到 `mapped_src_idx`
   - `ranges[k].warmup_bars = mapped_src_idx`
   - `ranges[k].pack_bars = source[k].height()`
   - `ranges[k].active_bars = ranges[k].pack_bars - ranges[k].warmup_bars`
3. 再做状态机内部一致性断言：
   - `mapped_src_idx >= W_required[k]`
   - 若不成立，说明前面的取数阶段其实没有把该 source 的最终 required warmup 补够，直接报错

强约束：

1. 只找一根 `base_first_live_time` 的映射，不扫描整段 base。
2. 必须严格符合 backward asof 语义。
3. 必须统一复用 `map_source_row_by_time(...)`，其内部再使用 Polars 向量化 API，例如 `join_asof(..., strategy="backward")` 或等价实现。
4. 不允许手写循环扫时间列，也不允许在这里再单独实现一套“看起来等价”的时间映射。
5. 因为上一步已经保证 source 对 `base_full` 全量覆盖，所以这里的 `mapped_src_idx` 必然存在，不允许为 null。
6. 这里得到的 `mapped_src_idx` 就是最终 warmup 真值，不再额外 `max(...)` 修正。

## 3. Rust 状态机 finish 后如何返回 DataPack

```rust
fn build_data_pack(
    source:        HashMap<String, DataFrame>,
    base_data_key: String,
    ranges:        HashMap<String, SourceRange>,
    skip_mask:     Option<DataFrame>,
) -> Result<DataPack, QuantError>
```

关键口径：

1. `build_data_pack(...)` 仍然是统一入口。
2. 但在这套架构里，它由 Rust 取数状态机内部调用。
3. Python 侧不再直接调用 `build_data_pack(...)`。
4. `build_data_pack(...)` 仍然保留 PyO3 暴露，主要服务 Python 侧测试、调试和最小构造场景。
5. `planner.finish()` 的职责就是：
   - 拿当前状态机里已经准备好的 `base_full + source + ranges`
   - 在 Rust 内部调用 `build_data_pack(...)`
   - 返回最终 `DataPack`

## 4. Rust builder 的职责边界

这里必须定死：

1. `build_data_pack(...)` 不再自己推导 `ranges`。
2. `ranges` 必须由调用方先算好。
3. `build_data_pack(...)` 不做任何隐式 `align / trim / source 裁减`。
4. `mapping` 只描述关系，不参与裁减 source。
5. 当前没有明确需要 builder 裁 source 的场景。
6. 在本方案里，`ranges` 的调用方不是 Python，而是 Rust 取数状态机。

这条边界很重要：

1. 一旦让 mapping 或 builder 参与裁 source，很容易把左侧预热裁没。
2. 规划层如果需要裁数据，应由 Rust 取数状态机或后续切片/拼接第一层处理。
3. 统一入口只做 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 中定义的统一校验、构建与组装，不修改输入。
