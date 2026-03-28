# 统一 Ranges / Warmup / WF 重构总述与基础约束

> 本任务按**破坏性更新**处理，目标是彻底解决 unified ranges / warmup / walk forward 链路中的历史残留，不保留兼容层，不接受旧名残留。
>
> 本组文档是任务摘要，不是长期维护的全局规范。它只服务这次重构：在摘要阶段把算法细节、边界条件、失败策略一次性讲清楚，保证后续执行文档与实现都能直接落地。

全文统一约束：

1. 全文校验策略：Fail-Fast，直接报错，不做静默回退。
2. 全文区间语义：半开区间 `[start, end)`。
3. 全文索引语义：相对于当前容器自身 DataFrame 的局部行号，不是全局绝对索引。
4. 实现风格必须遵守当前项目的 Rust 单一事实源 + PyO3 暴露 + 自动 stub 范式。

## 0. 文档归属与引用规则

本组摘要采用“归属文档 + 局部增量”的写法，但这里不能只把目录关系列出来，必须先把这层抽象本身讲清楚。

本节真正要定义的是：

1. 为什么这里需要一层共享真值解析。
2. 这层共享真值解析到底负责什么，不负责什么。
3. 后续文档哪些地方必须直接复用这里的定义，哪些地方必须在本章自己继续展开。

### 0.1 为什么要有这一层

本任务里最容易 quietly wrong 的，不是单个函数长不长，而是同一批真值被多个链路各自解释一遍：

1. 初始取数 planner 要决定“每个 source 至少还要往左保留多少历史”。
2. `build_window_indices(...)` 要决定“每个窗口的 train/test 预热到底按多少算”。
3. `extract_active(...)`、WF、stitched 又要决定“当前容器里真正应该裁掉多少前导数据”。

如果这些地方各自再写一套口径，最容易出现三类漂移：

1. warmup 聚合规则在 planner 和 WF 里慢慢变得不一致。
2. 文档里说的是一套命名，代码里又在不同模块里重复发明新名字。
3. 某个策略开关（例如 `ignore_indicator_warmup`）只改了一个入口，另外入口仍沿用旧语义。

因此，本节要建立的不是“大家共享一个大对象实例”，而是“大家共享一套唯一真值定义”。

### 0.2 这一层到底是什么，不是什么

它是：

1. Rust 内部的共享解析语义层。
2. 少数几个共享 resolver / helper 的正式定义来源。
3. 后续 planner / backtest / WF 文档在术语、公式和失败语义上的统一引用点。

它不是：

1. 一个要在 Python 和 Rust 之间来回传递的大 `RunContract` 对象。
2. 一个新的用户层配置类。
3. 一个要求每个流程都持有同一份运行态实例的“大框架对象”。

也就是说，这里统一的是“真值如何被解释”，不是“所有模块必须共享同一个对象实例”。

### 0.3 共享真值层的工具函数定义

为了让后续实现和审核都更直接，这一层不再只用概念描述，而是直接按“共享工具函数契约”来写。

这里的目标不是要求所有模块共享同一个运行时对象，而是要求所有模块共享同一套 resolver / helper 语义。

#### 0.3.1 工具函数一：解析原始契约 warmup

```rust
fn resolve_contract_warmup_by_key(
    indicators_params: IndicatorsParams,
) -> HashMap<String, usize>
```

语义：

1. 这个函数不是第二套平行聚合逻辑，而是一个**窄语义 helper**。
2. 它的正式实现必须直接调用 `resolve_indicator_contracts(...)`，然后只提取其中的 `warmup_bars_by_source`。
3. 也就是说：

```text
resolve_contract_warmup_by_key(indicators_params)
=
resolve_indicator_contracts(indicators_params).warmup_bars_by_source
```

4. `resolve_indicator_contracts(...)` 的正式聚合公式与边界，统一归本章 `2.2` 说明；这里不再重复写第二遍。
5. 它返回的 map 就是本文统一命名的 `resolved_contract_warmup_by_key`，也就是 `W_resolved`。
6. 这份结果允许只覆盖“实际被指标使用到的 source keys”。

这一步只回答：

1. 指标契约层认为每个 source 至少需要多少 warmup。

#### 0.3.2 工具函数二：补全到当前 source 全集

```rust
fn normalize_contract_warmup_by_key(
    source_keys: &[String],
    resolved_contract_warmup_by_key: &HashMap<String, usize>,
) -> HashMap<String, usize>
```

语义：

1. 这个函数把原始聚合结果补全到当前容器真实使用的全部 `S_keys`。
2. 返回结果就是本文统一命名的 `normalized_contract_warmup_by_key`，也就是 `W_normalized`。

公式：

```text
W_normalized[k] =
    W_resolved[k],  若 k ∈ keys(W_resolved)
    0,              若 k ∉ keys(W_resolved)
```

边界：

1. `source_keys` 必须来自当前流程真实使用的 source 集合，而不是随手传一个推测列表。
2. 返回结果必须完整覆盖全部 `S_keys`。
3. 缺失 key 统一补 `0`，这里不允许再引入别的默认值。

这一步只回答：

1. 在“当前 source 全集”下，每个 source 的契约 warmup 真值是多少。

#### 0.3.3 工具函数三：应用 WF 预热策略

```rust
fn apply_wf_warmup_policy(
    normalized_contract_warmup_by_key: &HashMap<String, usize>,
    ignore_indicator_warmup: bool,
) -> HashMap<String, usize>
```

语义：

1. 这个函数只负责把 WF 配置作用到契约 warmup 上。
2. 返回结果就是本文统一命名的 `applied_contract_warmup_by_key`，也就是 `W_applied`。

公式：

```text
W_applied[k] =
    0,               若 ignore_indicator_warmup = true
    W_normalized[k], 若 ignore_indicator_warmup = false
```

边界：

1. `ignore_indicator_warmup = true` 时，只把契约 warmup 截获成 `0`。
2. 除这一步外，WF 后续窗口规划、切片、拼接逻辑都不新增平行分支。
3. 这个函数不负责 `min_warmup_bars`，因为那是 WF 窗口规划层的额外约束，不是指标契约层语义。

这一步只回答：

1. WF 窗口规划当前实际采用哪份契约 warmup。

它仍然**不**回答：

1. 当前窗口 `DataPack` 真正左边额外保留了多少 source 历史。
2. 当前容器里最终应该裁掉多少真实前导 bar。

#### 0.3.4 工具函数四：读取容器真实前导边界

```rust
fn get_container_warmup_bars(
    data: &DataPack,
    source_key: &str,
) -> usize
```

语义：

1. 这个函数不需要真的单独实现成公共 API，但摘要层必须把它的语义写成正式 helper。
2. 它表达的是：一旦某个 `DataPack` 已经真正构建完成，后续所有切片、重基、拼接，都只能从容器自身读取真实前导边界。

公式：

```text
get_container_warmup_bars(data, k) = data.ranges[k].warmup_bars
```

边界：

1. 这里读到的是“当前容器里的真实前导边界”。
2. 不能回退去读 `W_resolved[k] / W_normalized[k] / W_applied[k]` 来代替它。
3. 原因是当前容器为了首尾覆盖，可能额外保留了更多左侧历史，因此一般只保证：

```text
data.ranges[k].warmup_bars >= W_applied[k]
```

但不要求两者恒等。

这一步回答的是：

1. 当前容器在真正切片时，到底应该裁掉多少前导数据。

### 0.4 共享层与各流程文档的职责边界

为了让后续文档可以被审核，本节把“哪些必须在这里定义，哪些不能偷懒丢给引用”直接写死。

必须在本节完整定义的内容：

1. 共享术语与统一命名。
2. `W_resolved / W_normalized / W_applied` 的公式与边界。
3. 共享 resolver 的输入、输出、失败语义。
4. “契约 warmup”和“容器真实 warmup”不是同一层语义这件事。

不能只放在本节、后续章节仍必须继续展开的内容：

1. planner 的状态机步骤与完成条件。
2. `build_result_pack(...)`、`extract_active(...)` 的字段级处理。
3. `build_window_indices(...)` 的窗口公式、阶段切片与 stitched 规则。

也就是说：

1. 本节负责定义“全局真值怎么解释”。
2. 后续章节负责定义“当前流程怎么消费这份真值”。

### 0.5 归属总表

| 概念 / 工具函数 / 语义 | 归属文档 | 主要消费方 | 说明 |
|---|---|---|---|
| `resolve_indicator_contracts(...)`、`W_resolved[k]`、`W_normalized[k]`、`W_applied[k]` | 本文 | `02`、`04` | 共享真值；`01` 负责完整定义，后续只说明各流程如何消费 |
| `DataPack / ResultPack / SourceRange` 的通用结构与 `mapping` 通用约束 | 本文 | `02`、`03`、`04` | 共享容器真值；后续不再重复发明第二套口径 |
| `build_mapping_frame(...)` 与 builder 收口原则 | 本文 | `02`、`03`、`04` | 共享 Pack 构建入口约束 |
| `DataPackFetchPlanner`、取数状态机、Python/Rust IO 边界 | [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md) | 执行文档与实现 | 只属于取数规划，不提升为全局通用语义 |
| `build_result_pack(...)` 的结果字段构建细节、`extract_active(...)` | [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) | `04`、执行文档与实现 | 只属于结果包与 active 视图语义 |
| `build_window_indices(...)`、WF 阶段契约、stitched | [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) | 执行文档与实现 | 只属于 WF / stitched；其中 `W_applied[k]` 作为输入直接复用本文定义 |

### 0.6 引用规则

在有了上面的逻辑闭环之后，后续文档再按下面这组规则引用：

1. 同一个共享概念，只允许在归属文档里完整写一次；其他文档不再复制整张表、整段公式或整段伪代码。
2. 其他文档若消费这套定义，必须在开头明确写：
   - 本章复用哪几个共享定义
   - 本章只新增哪些局部语义
3. 如果某条规则会直接改变当前章节的控制流、阶段返回值或失败分支，则必须在当前章节再写一遍“本章结论”，不能只丢一个引用链接。
4. 跨文档引用尽量保持单跳：
   - 优先直接回到归属文档
   - 尽量避免链式跳转
5. 执行文档只保留“落地到哪些文件、由哪些入口消费”的实现视角，不再重复摘要层解释。

## 1. 术语与记号

| 记号 | 含义 |
|---|---|
| `base` | 最小周期数据源，即 `base_data_key` 对应的 source |
| `source` | 按 source key 组织的数据源层；在 `DataPack` 中对应 `DataPack.source`，在 `ResultPack` 中对应 `ResultPack.indicators` 的分组语义 |
| `S_keys` | `source` 的全部 key 集合，且包含 `base_data_key` |
| `k` | `S_keys` 中的某个 source key |
| `indicator_source_keys` | `ResultPack.indicators` 中实际存在指标结果的 source key 集合，且 `indicator_source_keys ⊆ S_keys` |
| `W_resolved[k]` | `resolved_contract_warmup_by_key[k]` 的唯一缩写，表示 `resolve_indicator_contracts(...)` 返回的原始聚合预热结果；允许不覆盖全部 `S_keys` |
| `W_normalized[k]` | `normalized_contract_warmup_by_key[k]` 的唯一缩写，表示把原始聚合结果补全到全部 `S_keys` 后的预热值；缺失 key 统一补 `0` |
| `W_applied[k]` | `applied_contract_warmup_by_key[k]` 的唯一缩写，表示在 `W_normalized[k]` 基础上，再应用 WF 配置（如 `config.ignore_indicator_warmup`）后的最终采用值 |
| `N_base` | base DataFrame 行数 |
| `N[k]` | source `k` 的 DataFrame 行数 |

## 2. 指标预热基础

### 2.1 指标契约回调

每个已注册指标都必须实现：

```rust
trait Indicator {
    fn required_warmup_bars(resolved_params: &HashMap<String, f64>) -> usize;
    fn warmup_mode() -> WarmupMode; // Strict | Relaxed
}
```

### 2.2 预热聚合工具函数

```rust
fn resolve_indicator_contracts(indicators_params) -> ResolvedIndicatorContracts

ResolvedIndicatorContracts {
    warmup_bars_by_source: HashMap<String, usize>,
    contracts_by_indicator: HashMap<String, (source, warmup_bars, warmup_mode)>,
}
```

这一节是 `resolve_indicator_contracts(...)` 的**唯一公式归属**。

也就是说：

1. 后文若需要“按 source 聚合后的 warmup map”，统一直接引用这里的定义。
2. 若后文保留 `resolve_contract_warmup_by_key(...)` 这个 helper 名字，它也只是：

```text
resolve_contract_warmup_by_key(indicators_params)
=
resolve_indicator_contracts(indicators_params).warmup_bars_by_source
```

3. 除本节外，其余章节不再重复展开 `resolve_indicator_contracts(...)` 的聚合公式。

聚合公式：

先对每个指标实例 `indicator_i` 定义：

```text
resolved_params_i[p] =
    Param.max,   若 param_i[p].optimize = true 且 max 存在
    Param.value, 其余情况

warmup_i =
    required_warmup_bars(resolved_params_i)

mode_i =
    warmup_mode(indicator_i)

source_i =
    indicator_i 所属 source key
```

再定义返回结构：

```text
contracts_by_indicator[indicator_i] =
    (source_i, warmup_i, mode_i)
```

```text
warmup_bars_by_source[k] =
    max({ warmup_i | source_i = k })
```

补充约定：

```text
若不存在任何 source_i = k 的指标实例，
则 k 可以不出现在 warmup_bars_by_source 中
```

命名口径必须明确分三层：

1. `resolved_contract_warmup_by_key`
   - 指 `resolve_indicator_contracts(...).warmup_bars_by_source` 返回的原始聚合结果
   - 这份结果允许只覆盖“实际被指标使用到的 source keys”
2. `normalized_contract_warmup_by_key`
   - 指把 `resolved_contract_warmup_by_key` 补全到当前 `S_keys` 后的结果
   - 规则是：对每个 `k ∈ S_keys`，缺失就补 `0`
3. `applied_contract_warmup_by_key`
   - 指在 `normalized_contract_warmup_by_key` 基础上，再应用 WF 配置（如 `config.ignore_indicator_warmup`）后的最终采用值
   - 后续 WF 窗口规划只允许读取这份 map

聚合规则：

1. 同一 source 上多个指标，warmup 取 `max`，不求和。
2. 参数解析在聚合函数内部统一完成，调用方只传正常 `indicators_params`。
3. 对 `optimize = true` 的指标参数，`resolve_indicator_contracts(...)` 内部必须统一按 `Param.max` 解析；`optimize = false` 时才读取 `Param.value`。
4. 因此，这份聚合结果天然就是“当前指标参数空间下的最坏预热需求”，可以同时作为：
   - 初始取数 planner 的 warmup 真值
   - WF `build_window_indices(...)` 的 warmup 真值
5. 指标实现只关心 `resolved_params`，不关心 `Param.value/max` 的来源差异。
6. 未被任何指标使用到的 source，允许不出现在 `warmup_bars_by_source` 中。

### 2.3 当前 pytest 校验方式

已落地测试分两层：

第一层：静态契约聚合
- 文件：`py_entry/Test/indicators/test_resolve_indicator_contracts.py`
- 校验返回结构、同 source 按 `max` 聚合、未知指标直接报错、参数解析正确。

第二层：真实输出契约
- 文件：`py_entry/Test/indicators/test_indicator_warmup_contract.py`
- 先调用 `resolve_indicator_contracts(...)` 拿到 warmup，再实际跑指标，检查真实输出的前导缺失数量和 `Strict / Relaxed` 行为是否符合契约。

### 2.4 指标预热清单

| 指标 | `required_warmup_bars` | `warmup_mode` |
|---|---|---|
| `sma` | `period - 1` | Strict |
| `ema` | `period - 1` | Strict |
| `rma` | `0` | Strict |
| `rsi` | `period` | Strict |
| `tr` | `1` | Strict |
| `atr` | `period` | Strict |
| `macd` | `max(fast, slow) + signal - 2` | Strict |
| `adx` | `2 * period + adxr_length - 1` | Strict |
| `cci` | `period - 1` | Strict |
| `bbands` | `period - 1` | Strict |
| `er` | `length` | Strict |
| `psar` | `2` | Relaxed |
| `opening-bar` | `0` | Strict |
| `sma-close-pct` | `period - 1` | Strict |
| `cci-divergence` | CCI 的 `required_warmup_bars` | Strict |
| `rsi-divergence` | RSI 的 `required_warmup_bars` | Strict |
| `macd-divergence` | MACD 的 `required_warmup_bars` | Strict |

### 2.5 运行时校验语义

- `Strict`：预热段 `[0, required_warmup_bars)` 全空；非预热段 `[required_warmup_bars, end)` 不得再出现 NaN/null。
- `Relaxed`：预热段 `[0, required_warmup_bars)` 全空；非预热段允许结构性空值，但同一行不得全部输出列同时为空。

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
