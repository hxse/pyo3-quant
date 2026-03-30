# 统一 Ranges / Warmup / WF 重构总述与基础约束（二）核心类型、builder 与 mapping

## 3. 核心类型

### 3.1 重命名方案

本次直接强制重命名：

| 旧名 | 新名 | 含义 |
|---|---|---|
| `DataContainer` | `DataPack` | 输入侧多周期数据包 |
| `BacktestSummary` | `ResultPack` | 输出侧结果包 |

约束：

1. 不保留旧名，不提供兼容别名。
2. Rust 类型是唯一事实源，通过 PyO3 暴露，再由 `just stub` 生成 Python 存根。
3. Python 侧不维护镜像类型。

### 3.2 DataPack

```rust
struct DataPack {
    source:        HashMap<String, DataFrame>,
    mapping:       DataFrame,                   // 列 = ["time"] + S_keys
    skip_mask:     Option<DataFrame>,
    base_data_key: String,
    ranges:        HashMap<String, SourceRange>, // 必须覆盖全部 S_keys
}
```

### 3.3 ResultPack

```rust
struct ResultPack {
    indicators:  Option<HashMap<String, DataFrame>>, // source key -> 指标结果 DF；每个 DF 都必须显式包含 time 列
    signals:     Option<DataFrame>,
    backtest:    Option<DataFrame>,
    performance: Option<HashMap<String, f64>>,
    base_data_key: String,
    mapping:     DataFrame, // 至少包含 time 列
    ranges:      HashMap<String, SourceRange>, // 只保留 base + indicator_source_keys
}
```

说明：

1. 这里的 `ResultPack` 只定义**通用容器形状**，因此 `indicators / signals / backtest / performance` 统一保留 `Option`。
2. 这样做是为了允许不同执行阶段只产出部分字段，例如：
   - 只跑到 `Signals`
   - 只跑到 `Backtest`
   - 或完整跑到 `Performance`
3. 一旦进入具体流程文档，例如单次回测、WF、stitched，就必须再额外写死“当前阶段哪些字段必然存在”的阶段契约。
4. 因此：
   - `Option` 是总定义
   - 阶段产出契约是具体流程对总定义施加的更强约束
   - 这两层不是冲突关系
5. 对 `indicators[k]` 再补一条硬契约：
   - `indicators[k]` 是 `DataFrame`，不是嵌套结构
   - 最终合法的 `ResultPack.indicators[k]` 必须显式包含一列名为 `time` 的时间列
   - 至于这条 `time` 列由谁补入、补入前后校验哪些条件、遇到同名 `time` 列如何失败，统一归 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 中 `build_result_pack(...)` 的字段构建规则定义

### 3.4 SourceRange

```rust
struct SourceRange {
    warmup_bars: usize,
    active_bars: usize,
    pack_bars:   usize,
}
```

区间推导：

1. 预热段：`[0, warmup_bars)`
2. 非预热有效段：`[warmup_bars, pack_bars)`
3. 整包：`[0, pack_bars)`

说明：

1. 这里显式保留 `warmup_bars / active_bars / pack_bars` 三个字段，避免后续到处写 `total - warmup`。
2. 这三个字段必须同时满足：`warmup_bars + active_bars == pack_bars`。

### 3.5 mapping 结构约束

`mapping` 是一个带 `time` 主列的 base 对齐关系表。

`build_mapping_frame(...)` 在生成 mapping 前，必须完整校验下面这组约束；后续 `4.x` 流程不再把同一组校验重复写第二遍，只直接引用这里。

输出结构约束：

1. `DataPack.mapping` 和 `ResultPack.mapping` 都统一必须包含 `time` 列，而且 `time` 永远是第一列。
2. `mapping.time` 表示当前容器自身的 base 时间真值。
3. 除 `time` 外，其余列值都必须是**非空 `UInt32`**，表示该 base 行对应的 source 局部行号；从类型设计上拒绝 null。
4. 一旦 `mapping.time` 构建完成，后续所有 base 维度操作都只认 `mapping.time`。

输入时间列约束：

1. `time` 列必须存在。
2. `time` 列必须是 `Int64`。
3. `time` 列不允许 null。
4. `time` 列必须严格递增。
5. `time` 列不允许重复时间戳。
6. 本项目彻底不再考虑支持 renko 等重复时间戳 source 数据。
7. `base_data_key` 必须存在于 `DataPack.source` 中；`build_mapping_frame(...)` 在生成 `DataPack.mapping` 前必须先校验这一点。

覆盖约束：

1. 当前容器内，所有 source 都必须对当前 base 时间轴完成**全量覆盖**，不能只覆盖非预热段。
2. 首覆盖：`source_k_first_time <= base_times.first()`
3. 尾覆盖：`source_k_last_time + source_interval_ms(k) > base_times.last()`

DataPack 的 `mapping`：

1. 必须存在。
2. 完整列集合固定为 `["time"] + S_keys`。
3. `mapping.time` 由 `source[base_data_key].time` 提取并构建。

ResultPack 的 `mapping`：

1. 必须存在。
2. 列集合固定为 `["time"] + indicator_source_keys`，其中 `indicator_source_keys ⊆ S_keys`。
3. `ResultPack.mapping` 直接来自对应 `DataPack.mapping` 的子集：
   - `mapping.time` 直接继承 `DataPack.mapping.time`
   - 其余列只保留当前实际存在指标结果的 `indicator_source_keys`
   - 不重新构建映射列，也不调整索引
   理由：`ResultPack` 的其他结果字段如 `indicators / signals / backtest / performance` 都可能在某个阶段为 `None`，因此不能要求 ResultPack 仅靠自身字段稳定拿到一条完整且可信的 base 时间轴；最稳妥也最统一的做法，是直接复用对应 DataPack 已经确定好的 mapping 子集。
4. `ResultPack.base_data_key` 必须显式存在，并直接继承对应 `DataPack.base_data_key`；文中 `ResultPack` 相关的 `base`，始终指 `ResultPack.base_data_key`。
5. 若当前阶段拿不到 `mapping.time`，ResultPack 不合法。

### 3.6 校验收口原则

后续绝大多数容器级操作，都必须回到统一入口函数：

1. 新建 `DataPack`，调用 `build_data_pack(...)`
2. 新建 `ResultPack`，调用 `build_result_pack(...)`
3. 窗口切片后生成新容器，仍然调用对应 builder
4. 唯一例外是 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 定义的 `extract_active(...)`：
   - 它不是“重新构建一个可继续运行的新 Pack”
   - 而是对一对已经同源且已验证的 `DataPack / ResultPack` 做机械化的非预热提取视图
   - 它只做切片、mapping 重基、ranges 归零和字段继承，然后直接构造新对象
   - 因此这里允许不再回到 builder
5. stitched / 拼接后生成新容器，仍然调用对应 builder

`build_data_pack(...)` 内部调用 `build_mapping_frame(...)`；`build_result_pack(...)` 不调用 `build_mapping_frame(...)`，只直接继承对应 `DataPack.mapping` 的子集。

因此：

1. `DataPack` 的 mapping 真值构建与校验统一集中在 `build_mapping_frame(...)`
2. `ResultPack` 不重新构建 mapping，而是直接继承对应 `DataPack.mapping` 的子集
3. 外部流程不再额外维护第二套 mapping 校验
4. 外部只负责准备好原始 DF、`ranges` 和必要参数
5. 真正的时间列校验、覆盖校验、mapping 列类型校验，都由 `build_mapping_frame(...)` 收口到 `DataPack` 这一层

补充说明：

1. 这里说“`build_mapping_frame(...)` 内部调用关系收口到 `build_data_pack(...)`”，只是在定义生产链路里的唯一正式入口。
2. 为了测试与调试方便，`build_mapping_frame(...)` 仍然可以保留 PyO3 暴露，作为小样本 contract test 的工具函数。
3. 这不代表业务流程可以绕过 `build_data_pack(...)`，把 `build_mapping_frame(...)` 当成第二套正式 builder 入口。

### 3.7 ranges 不变式

`DataPack.ranges`：

1. 必须覆盖全部 `S_keys`。
2. `ranges[k].pack_bars == source[k].height()`。

`ResultPack.ranges`：

1. 只保留 `base + indicator_source_keys`，其中 `base` 仍指对应 `DataPack.base_data_key`，且 `indicator_source_keys ⊆ S_keys`。
2. `ranges[base].pack_bars == mapping.height()`。
3. 若 `signals` 存在，则 `ranges[base].pack_bars == signals.height()`。
4. 若 `backtest` 存在，则 `ranges[base].pack_bars == backtest.height()`。
5. 若 `indicators[k]` 存在，则 `ranges[k].pack_bars == indicators[k].height()`。

通用约束：

1. `warmup_bars / active_bars / pack_bars` 都是必填数值字段，不是 `Option`；但数值本身允许为 `0`。
2. `0 <= warmup_bars <= pack_bars`。
3. `0 <= active_bars <= pack_bars`。
4. `warmup_bars + active_bars == pack_bars`。
5. `warmup_bars = 0` 是合法状态。
6. 这三类 contract warmup 记号都只表示契约层预热需求，不等于当前容器里的真实切片边界。
7. 当前容器里的真实前导边界只认 `ranges[k].warmup_bars`；它可能大于契约 warmup，因为 source 还可能为了首尾覆盖额外保留左侧 bar。
8. 因此，任何切片、拼接、重基类工具函数，凡是涉及“裁掉多少前导数据”，都必须以当前容器里的 `ranges[k].warmup_bars` 为准，不能回退去用 `resolve_indicator_contracts(...)` 的契约聚合 warmup。

## 4. Mapping 与覆盖校验

### 4.1 统一时间投影工具函数

本任务里所有“精确时间定位 / 把 base 时间映射到 source 行号 / 把 base 半开右边界映射到 source 半开右边界”的地方，都必须统一收口到下面三个工具函数：

这里不再写成抽象公式，而是直接把目标写法固定成同一套 Polars 伪代码。

```rust
fn exact_index_by_time(
    times: &[i64],
    target_time: i64,
    column_name: &str,
) -> Result<usize, Error>

fn map_source_row_by_time(
    anchor_time: i64,
    src_times: &[i64],
    source_key: &str,
) -> Result<usize, Error>

fn map_source_end_by_base_end(
    base_times: &[i64],
    src_times: &[i64],
    base_end_exclusive_idx: usize,
    source_key: &str,
) -> Result<usize, Error>
```

`exact_index_by_time(...)`：

参数类型与解释：

1. `times: &[i64]`
   - 要做精确时间定位的时间列，要求非空、严格递增、无重复
2. `target_time: i64`
   - 要精确查找的时间戳
3. `column_name: &str`
   - 当前时间列的名字，只用于报错信息
4. 返回值 `Result<usize, Error>`
   - `Ok(idx)` 表示 `target_time` 在该时间列中的唯一局部行号
   - `Err(...)` 表示该时间戳不存在

```text
# 构造一个临时的 Polars DataFrame:
# - time = times
# - idx  = 0..N-1

# 用 Polars 的等值过滤只保留 time == target_time 的那一行
matched = df.filter(col("time").eq(lit(target_time)))

# 要求：
# - 结果必须恰好只有 1 行
# - 否则直接报错

# 取回这一行的 idx
idx = matched["idx"][0]
```

`map_source_row_by_time(...)`：

参数类型与解释：

1. `anchor_time: i64`
   - 要映射到 source 的时间锚点
2. `src_times: &[i64]`
   - 当前 source 的 `time` 列，要求非空、严格递增、无重复
3. `source_key: &str`
   - 当前 source 的 key，只用于报错信息与上下文定位
4. 返回值 `Result<usize, Error>`
   - `Ok(mapped_idx)` 表示 backward asof 映射得到的 source 局部行号
   - `Err(...)` 表示当前时间锚点无法合法映射到该 source
```text
# 构造 left: 一个临时的 Polars DataFrame
#   只包含一行 time = anchor_time

# 构造 right: 一个临时的 Polars DataFrame
#   包含两列：
#   - time = src_times
#   - idx  = source 局部行号 0..N-1

# 用统一的 Polars backward asof 做时间投影
joined = left.join_asof(&right, "time", "time", AsofStrategy::Backward, None)

# 取回 joined["idx"][0]
# 这就是 anchor_time 映射到 source 的局部行号 mapped_idx
```

`map_source_end_by_base_end(...)`：

参数类型与解释：

1. `base_times: &[i64]`
   - 当前 base 的 `time` 列，要求非空、严格递增、无重复
2. `src_times: &[i64]`
   - 当前 source 的 `time` 列，要求非空、严格递增、无重复
3. `base_end_exclusive_idx: usize`
   - base 半开右边界索引，即区间 `[start, base_end_exclusive_idx)` 的右端点
4. `source_key: &str`
   - 当前 source 的 key，只用于报错信息与上下文定位
5. 返回值 `Result<usize, Error>`
   - `Ok(source_end_exclusive_idx)` 表示映射后的 source 半开右边界
   - `Err(...)` 表示该右边界无法合法映射

```text
# 输入：
# - base_times
# - src_times
# - base_end_exclusive_idx

# 先取右边界前一根 base bar 的时间
anchor_time = base_times[base_end_exclusive_idx - 1]

# 再复用同一个 map_source_row_by_time(...)
mapped_idx = map_source_row_by_time(anchor_time, src_times, source_key)

# 最后返回半开右边界
source_end_exclusive_idx = mapped_idx + 1
```

全文强约束：

1. `01~04` 里所有：
   - `time -> 精确行号`
   - `base 行号 -> source 行号`
   - `base 半开右边界 -> source 半开右边界`
   - `anchor_time -> mapped_src_idx`
   - pack/source 投影
   都必须理解为复用这三个工具函数，不允许各处再发明第二套时间映射逻辑。
2. 不允许手写循环扫时间列。
3. 不允许某些地方用私有实现、某些地方再写另一套“看起来等价”的计算。
4. 只允许统一使用同一套 Polars backward asof 向量化能力。

### 4.2 Polars backward asof 依赖说明

`4.1` 已经把统一时间投影工具函数定义清楚了。

这里不再重新定义映射语义，只补两件事：

1. 这些工具函数底层依赖的就是 Polars backward asof
2. 为什么当前任务可以直接把 Polars backward asof 当成唯一实现基础

下面这一行是 `build_mapping_column_unchecked(...)` 与 `4.1` 两个时间投影工具函数内部共同依赖的 Rust 侧 Polars 核心调用：

```rust
let joined = left.join_asof(&right, "time", "time", AsofStrategy::Backward, None)?;
```

自然语言解释：

1. 左表是 `base_times`，右表是 `src_times + idx`。
2. 使用 backward asof join。
3. 取回右表 `idx` 列，就是 backward asof 映射到的 source 局部行号。

适用边界：

1. 适用于当前任务定义下的多周期时间序列，因为这里的 mapping 本质上就是标准的一维时间 backward asof，不需要额外分组键。
2. 适用于当前文档已经拍板的输入约束：`base_times`、`src_times` 都必须是非空 `Int64` 时间列，严格递增且不允许重复。
3. 对于这类单键、有序、按时间回看最近已完成 bar 的映射需求，Polars backward asof 与项目业务语义一致。
4. 重复时间戳 source 场景本轮明确不兼容，直接报错。

工程约束：

1. Rust 侧若要直接使用该能力，需要在 `Cargo.toml` 为 `polars` 开启 `asof_join` feature。
2. `mapping.time` 仍然不通过 join 生成，而是直接写入 `base_times`；`join_asof` 只负责各个 source 的局部索引列。
3. base 自身列仍然直接写为 `0..N_base-1` 自然序列，不必对 base 再做一次 asof join。

### 4.3 首尾覆盖的严格业务语义

在本任务里，source `k` 必须对**当前容器的整个 base 时间轴**完成全量覆盖。

source `k` 严格覆盖 `base_times`，当且仅当：

1. 首覆盖：`source_k_first_time <= base_times.first()`
2. 尾覆盖：`source_k_last_time + source_interval_ms(k) > base_times.last()`

说明：

1. 首覆盖用 `<=`，不是 `<`。
2. 尾覆盖必须是 `last + interval > base_last`，不是 `last >= base_last`。
3. `mapping` 列不允许 null，因此这里的覆盖校验不是“优化项”，而是构建成功的前置条件。
4. backward asof join 只负责生成映射索引；首尾覆盖仍然必须由 `validate_coverage(...)` 单独保证。

### 4.4 覆盖校验函数

```rust
fn validate_coverage(
    base_times: &[i64],
    src_times: &[i64],
    source_interval_ms: i64,
    source_key: &str,
) -> Result<(), Error>
```

规则：

1. `base_times` 为空直接 `Ok`。
   含义不是“空执行区间是正常业务态”，而是这个 helper 在空区间上退化成 no-op：既然当前没有任何 base bar 需要校验覆盖，就没有首尾覆盖问题可判定。
   这条规则的作用是避免调用方在切片、窗口拼接、阶段性中间态里到处手写空区间特判。
   若某个业务流程本身不允许出现空执行区间，应由该流程在更上游单独报错，而不是让 `validate_coverage(...)` 在这里承担业务语义判断。
2. `src_times` 为空直接报错。
3. `source_interval_ms <= 0` 直接报错。
4. `src_times.first() <= base_times.first()`
5. `src_times.last() + source_interval_ms > base_times.last()`

### 4.5 共享 mapping builder 与时间投影的内外分层

对外统一入口：

```rust
fn build_mapping_frame(
    source: &HashMap<String, DataFrame>,
    base_data_key: &str,
) -> Result<DataFrame, QuantError>
```

推荐内部形态：

```rust
exact_index_by_time(times, target_time, column_name) -> usize
map_source_row_by_time(anchor_time, src_times, source_key) -> usize
map_source_end_by_base_end(base_times, src_times, base_end_exclusive_idx, source_key) -> usize
build_mapping_column_unchecked(base_times, src_times, source_key) -> Series
build_mapping_frame(...) -> Result<DataFrame, QuantError>
```

线性流程：

1. 调用 `build_mapping_frame(...)`
   - 内部先取 `base_times = source[base_data_key].time`
   - 第一列直接写入 `time = base_times`
   - 然后按 `source_key` 逐列构建 mapping
2. 每构建一列时：
   - 先执行 `3.5 mapping 结构约束` 里的完整校验
   - 其中覆盖部分由 `validate_coverage(base_times, src_times, interval_ms, source_key)` 承担
   - 再调用 `build_mapping_column_unchecked(base_times, src_times, source_key)`
3. `build_mapping_column_unchecked(...)`
   - 只做 backward asof
   - 不做业务校验
   - 返回单个 `source_key` 的整列 mapping
4. 其余所有“精确时间定位 / 单点时间映射 / 右边界映射”场景，也必须复用同一个：
   - `exact_index_by_time(...)`
   - `map_source_row_by_time(...)`
   - `map_source_end_by_base_end(...)`
   不允许另发明平行 helper。
5. `build_mapping_frame(...)` 对每一列再断言：
   - 结果满足 `3.5` 的输出结构约束
6. 所有 source 列都构建完成后
   - `build_mapping_frame(...)` 返回 `["time"] + source_keys` 的关系表

职责分工：

1. `validate_coverage(...)` 负责判断业务上允不允许映射。
2. `exact_index_by_time(...)` 负责统一精确时间定位。
3. `map_source_row_by_time(...)` / `map_source_end_by_base_end(...)` 负责统一“单点 / 右边界”的时间投影。
4. `build_mapping_column_unchecked(...)` 负责生成整列 mapping 索引。
5. `build_mapping_frame(...)` 负责把这些能力串起来并组装整表。

这样可以保证：

1. DataPack / ResultPack 共用同一套 checked builder。
2. `01~04` 的所有时间定位与时间投影都只认这三个 helper，不再维护项目私有语义分叉。
3. backward asof 的语义可以直接对齐 Polars 官方实现。
4. coverage helper 不会散落到业务代码里。
