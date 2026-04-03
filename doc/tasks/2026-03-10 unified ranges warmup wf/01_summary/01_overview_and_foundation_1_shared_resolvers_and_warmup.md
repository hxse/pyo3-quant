# 统一 Ranges / Warmup / WF 重构总述与基础约束

> 本任务按**破坏性更新**处理，目标是彻底解决 unified ranges / warmup / walk forward 链路中的历史残留，不保留兼容层，不接受旧名残留。
>
> 本组文档是任务摘要，不是长期维护的全局规范。它只服务这次重构：在摘要阶段把算法细节、边界条件、失败策略一次性讲清楚，保证后续执行文档与实现都能直接落地。

全文统一约束：

1. 全文校验策略：Fail-Fast，直接报错，不做静默回退。
2. 全文区间语义：半开区间 `[start, end)`。
3. 全文索引语义：相对于当前容器自身 DataFrame 的局部行号，不是全局绝对索引。
4. 实现风格必须遵守 Rust 单一事实源 + PyO3 暴露 + 自动 stub 范式。

## 0. 文档归属与引用规则

本章是整套文档的 shared truth layer。

本章把 `W_resolved / W_normalized / W_applied / W_backtest_exec_base / W_required` 这一整条共享 warmup 真值链，统一按对象视角称为 `WarmupRequirements`。

后续 `02~05` 里凡是涉及：

1. 指标契约 warmup
2. backtest exec warmup
3. planner / WF 共同依赖的 required warmup
4. “契约 warmup”和“容器真实 warmup”之间的层次差异

都必须先回到这里。

### 0.1 本层负责什么，不负责什么

| 本层负责 | 本层不负责 |
| --- | --- |
| 统一 warmup 真值链命名 | 取数状态机步骤 |
| 定义 shared resolver / helper 的输入、输出与失败语义 | `build_result_pack(...)` 的字段处理 |
| 解释 `W_resolved / W_normalized / W_applied / W_backtest_exec_base / W_required` | WF 窗口公式、切片流程与 stitched 拼接步骤 |
| 解释“契约 warmup”与“容器真实 warmup”不是同一层 | 任何具体流程的阶段返回结构 |

这里统一的是“真值如何被解释”，不是“所有模块共享同一个运行时对象实例”。

### 0.2 warmup 真值链速览

| 名称 | 正式来源 | 含义 | 后续谁直接消费 |
| --- | --- | --- | --- |
| `W_resolved[k]` | `resolve_indicator_contracts(...).warmup_bars_by_source` | 指标契约原始聚合结果；允许不覆盖全部 `S_keys` | `01` |
| `W_normalized[k]` | `normalize_contract_warmup_by_key(...)` | 把 `W_resolved` 补全到当前 `S_keys` | `01` |
| `W_applied[k]` | `apply_wf_warmup_policy(...)` | 在 `W_normalized` 上应用 WF 指标策略后的结果 | `04` |
| `W_backtest_exec_base` | `resolve_backtest_exec_warmup_base(...)` | base 轴回测执行层 warmup | `02`、`04` |
| `W_required[k]` | `merge_required_warmup_by_key(...)` | 把 `W_applied` 与 base exec warmup 合并后的最终 required warmup | `02`、`04` |
| `data.ranges[k].warmup_bars` | 当前容器自身 `ranges` | 当前容器真实前导边界 | `03`、`04`、`05` |

### 0.3 共享真值层的工具函数定义

本节先给 helper 总览，再在 `0.3.1 ~ 0.3.6` 里逐个写详细契约。

| helper | 产物 | 作用 |
| --- | --- | --- |
| `resolve_contract_warmup_by_key(...)` | `W_resolved` | 从指标契约里抽出 source 级原始 warmup 聚合 |
| `normalize_contract_warmup_by_key(...)` | `W_normalized` | 补全到当前 `S_keys` |
| `apply_wf_warmup_policy(...)` | `W_applied` | 应用 WF 指标预热策略 |
| `resolve_backtest_exec_warmup_base(...)` | `W_backtest_exec_base` | 解析 base 轴回测执行层 warmup |
| `merge_required_warmup_by_key(...)` | `W_required` | 合并指标 warmup 与 base exec warmup |
| `get_container_warmup_bars(...)` | `data.ranges[k].warmup_bars` | 读取当前容器真实前导边界 |

#### 0.3.1 工具函数一：解析原始指标契约 warmup

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
7. 这里的 `indicators_params` 直接使用指标参数容器，不允许在 planner / WF 层先手工物化第二套 indicator concrete params。
8. 对 `optimize = true` 的指标参数，唯一合法解释入口仍是 `resolve_indicator_contracts(...)`：
   - `optimize = false` 时取 `Param.value`
   - `optimize = true` 时取 `Param.max`
   - `Param.max` 是正式字段，不存在“`optimize = true` 但缺失 max，于是回退到 `Param.value`”的第二条解释规则
9. 它只回答指标契约层的原始 warmup，不回答容器真实裁剪边界。

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
4. 它仍然只是契约层补全结果，不等于容器真实 `warmup_bars`。

#### 0.3.3 工具函数三：应用 WF 指标预热策略

```rust
fn apply_wf_warmup_policy(
    normalized_contract_warmup_by_key: &HashMap<String, usize>,
    ignore_indicator_warmup: bool,
) -> HashMap<String, usize>
```

语义：

1. 这个函数只负责把 WF 配置作用到**指标契约 warmup** 上。
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
4. `W_applied` 只表示 WF 采用的指标契约 warmup，不表示容器真实左侧保留量，也不直接等于后续真实裁剪边界。

#### 0.3.4 工具函数四：解析回测执行层 warmup

```rust
fn resolve_backtest_exec_warmup_base(
    backtest_params: &BacktestParams,
) -> Result<usize, QuantError>
```

语义：

1. 这个函数只计算回测执行层自身的启动 warmup，不参与指标契约聚合。
2. 当前第一版只作用在 `base_data_key` 对应的 base 轴。
3. 这里的 `BacktestParams` 不是“已经完全物化成 runtime concrete 值的最终回测参数”，而是 `SingleParamSet.backtest` 使用的那份回测参数容器：
   - 固定字段继续按固定值读取
   - 可优化字段仍然可能以 `Param` 叶子存在
4. 因而这个 resolver 的职责不是“直接读取最终 concrete 回测参数”，而是：
   - 先从 `BacktestParams` 这份参数容器里，解析出**会影响 exec warmup 的 concrete 值**
   - 再把这些 concrete 值交给 ATR / PSAR 已有的 warmup primitive
5. 它不允许在 backtest 层再手写第二套 ATR / PSAR 公式，而必须复用本文 `2.6` 里定义的共享 warmup primitive。

解析规则：

1. 对会影响 backtest exec warmup 的可优化字段，沿用与指标 warmup 同级的唯一解析规则：
   - `optimize = false` 时，取 `Param.value`
   - `optimize = true` 时，取 `Param.max`
   - `Param.max` 是正式字段，不存在“`optimize = true` 但缺失 max，于是回退到 `Param.value`”的回退分支
2. 当前第一版真正会改变 exec warmup 的关键字段，至少包括：
   - `atr_period`
3. 是否启用 ATR 风控、是否启用 `TSL_PSAR`，继续按 `BacktestParams` 当前布尔 / 可选字段语义判断。
4. PSAR 分量不允许在 resolver 里猜测或重写公式：
   - 一律直接调用 `psar_required_warmup_bars(...)`
   - 若该 primitive 未来新增入参，也必须先按同一条 `Param.value / Param.max` 规则解析 concrete 值，再委托给 primitive

公式：

```text
W_backtest_exec_base =
    max(
        W_exec_atr,
        W_exec_psar
    )
```

其中：

```text
resolved_atr_period =
    backtest_params.atr_period.value, 若 atr_period.optimize = false
    backtest_params.atr_period.max,   若 atr_period.optimize = true

W_exec_atr =
    atr_required_warmup_bars(resolved_atr_period), 若启用了任一 ATR 风控
    0,                                    其余情况

W_exec_psar =
    psar_required_warmup_bars(), 若启用了 TSL_PSAR
    0,                           其余情况
```

边界：

1. 这里计算的是：base 轴在进入完整可交易态前，还需要额外保留多少 backtest 执行预热。
2. 它不生成按 `S_keys` 展开的 map。
3. 它也不参与 `ignore_indicator_warmup`。
4. 它只是 base 轴执行预热分量，本身还不是最终的 `W_required`，更不是容器真实 `warmup_bars`。
5. 因为它已经在 resolver 内部把 `BacktestParams` 参数容器解析成了 warmup 相关 concrete 值，所以：
   - `02` 的初始 planner
   - `04` 的 WF 窗口主流程
   都必须直接复用这一个 helper，不允许各自再解释一套 `Param.value / Param.max` 规则。

#### 0.3.5 工具函数五：合并最终 required warmup

```rust
fn merge_required_warmup_by_key(
    base_data_key: &str,
    applied_contract_warmup_by_key: &HashMap<String, usize>,
    backtest_exec_warmup_base: usize,
) -> HashMap<String, usize>
```

语义：

1. 这个函数把“指标契约 warmup”与“backtest exec warmup”合并成最终 required warmup。
2. 返回结果就是本文统一命名的 `required_warmup_by_key`，也就是 `W_required`。
3. 它只允许复用前面 helper 已经产出的 `applied_contract_warmup_by_key` 与 `backtest_exec_warmup_base`，不允许在这里重算一套指标或回测 warmup 逻辑。

公式：

```text
W_required[k] =
    max(
        W_applied[k],
        if k == base_data_key { W_backtest_exec_base } else { 0 }
    )
```

边界：

1. 对非 base source，`W_required[k]` 退化为 `W_applied[k]`。
2. 对 base source，`W_required[base]` 可能大于 `W_applied[base]`。
3. planner / WF 窗口规划后续若要决定“当前至少需要多少合法前导数据”，都必须消费 `W_required`，不再只消费指标 warmup。
4. 但一旦某个 `DataPack` 已经构建完成，后续切片和拼接仍应回到容器自身的 `warmup_bars`，不能回退去直接拿 `W_required` 裁数据。

#### 0.3.6 工具函数六：读取容器真实前导边界

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
4. 后续真正切片时，应该读这里，而不是回退去读契约 warmup 或 `W_required`。

### 0.4 后续文档如何引用本章

| 概念 / 工具函数 / 语义 | 归属文档 | 主要消费方 | 说明 |
|---|---|---|---|
| `resolve_indicator_contracts(...)`、`resolve_backtest_exec_warmup_base(...)`、`merge_required_warmup_by_key(...)`、`W_resolved[k]`、`W_normalized[k]`、`W_applied[k]`、`W_required[k]` | 本文 | `02`、`03`、`04` | 共享真值；`01` 负责完整定义，后续只说明各流程如何消费 |
| `DataPack / ResultPack / SourceRange` 的通用结构与 `mapping` 通用约束 | 本文 | `02`、`03`、`04` | 共享容器真值；后续不再重复发明第二套口径 |
| `build_mapping_frame(...)` 与 builder 收口原则 | 本文 | `02`、`03`、`04` | 共享 Pack 构建入口约束 |
| `DataPackFetchPlanner`、取数状态机、Python/Rust IO 边界 | [02_python_fetch_and_initial_build.md](./02_python_fetch_and_initial_build.md) | 执行文档与实现 | 只属于取数规划，不提升为全局通用语义 |
| `build_result_pack(...)` 的结果字段构建细节、`extract_active(...)` | [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) | `04`、执行文档与实现 | 只属于结果包与 active 视图语义 |
| `build_window_indices(...)`、WF 阶段契约、stitched | [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) | 执行文档与实现 | 只属于 WF / stitched；其中 `W_applied[k]` 作为输入直接复用本文定义 |

### 0.5 引用规则

1. 同一个共享概念，只允许在归属文档里完整写一次；其他文档不再复制整张表、整段公式或整段伪代码。
2. 后续文档若消费这套定义，只写：
   - 本章复用哪些共享定义
   - 本章新增哪些局部语义
3. 如果某条规则会直接改变当前章节的控制流、阶段返回值或失败分支，则必须在当前章节再写一遍“本章结论”，不能只丢一个引用链接。
4. 跨文档引用尽量保持单跳，优先直接回到归属文档。
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
| `W_required[k]` | `required_warmup_by_key[k]` 的唯一缩写，表示把 `W_applied[k]` 与回测执行层 warmup 合并后的最终 required warmup；planner / WF 规划统一消费它 |
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
    Param.max,   若 param_i[p].optimize = true
    Param.value, 若 param_i[p].optimize = false

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

- `Strict`：`warmup 区间` `[0, required_warmup_bars)` 全空；`active 区间` `[required_warmup_bars, end)` 不得再出现 NaN/null。
- `Relaxed`：`warmup 区间` `[0, required_warmup_bars)` 全空；`active 区间` 允许结构性空值，但同一行不得全部输出列同时为空。

### 2.6 ATR / PSAR 共享 warmup primitive 与 backtest exec warmup

当前任务里，ATR / PSAR 的 warmup 真值不应只停留在“指标注册表内部定义”，而应进一步收口成共享 primitive。

原因：

1. ATR 指标与 PSAR 指标都已经定义了自己的 `required_warmup_bars(...)`。
2. backtest 执行层又会直接消费 ATR 风控与 `TSL_PSAR`。
3. 若 backtest 层再手写一套 `atr_period` / `2` 这类魔法数字，就会重新引入同一事实多处定义的问题。

因此本文把 ATR / PSAR 的 warmup 真值进一步定义成：

```rust
fn atr_required_warmup_bars(period: i64) -> usize
fn psar_required_warmup_bars() -> usize
```

约束：

1. `AtrIndicator.required_warmup_bars(...)` 必须复用 `atr_required_warmup_bars(...)`。
2. `PsarIndicator.required_warmup_bars(...)` 必须复用 `psar_required_warmup_bars()`。
3. `resolve_backtest_exec_warmup_base(...)` 也必须复用这两份 primitive。
4. 不允许在 backtest exec warmup resolver 中再维护 ATR / PSAR 的第二套硬编码 warmup 规则。

当前真值沿用指标定义：

1. ATR：`atr_required_warmup_bars(period) = period`
2. PSAR：`psar_required_warmup_bars() = 2`

这里还要明确说明问题性质：

1. 当前缺口不是“ATR / PSAR 算错了”，而是“统一 warmup 口径里原先只收了指标 warmup，没有把 backtest exec warmup 一起纳入 `W_required`”。
2. 这个问题不是特别严重，因为当前引擎里已经存在 ATR 进场屏蔽、PSAR 只影响最前面少数 bar 等运行时自保护，不太会直接把结果算坏。
3. 但它仍然必须修复，因为 planner / WF / stitched 若只按指标 warmup 解释 active 合法区间，就会低估 base 轴真正还需要保留的前导数据。

因此，最终统一口径应当是：

1. `W_applied` 仍表示“应用 WF 指标策略后的指标 warmup”
2. `W_backtest_exec_base` 单独表示“回测执行层 warmup”
3. `W_required` 才是后续 planner / WF 真正消费的最终 warmup 真值

还需要把使用场景说死：

1. 当前任务的正式主流程里，并不存在一个“最终只消费指标 warmup、不能额外带上 backtest exec warmup”的真实业务场景。
2. 即使只是看指标、signals 或画图，多带几根前导预热通常也不会破坏结果解释，因此不足以构成必须单独维护“只吃指标 warmup”口径的理由。
3. 因而 `W_applied` 在本文中的角色是中间推导层，不是正式顶层消费终点；正式主流程最终统一收敛到 `W_required`。
