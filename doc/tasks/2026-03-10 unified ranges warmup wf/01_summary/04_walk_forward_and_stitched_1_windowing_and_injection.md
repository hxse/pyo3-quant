# 向前测试、窗口切片、跨窗注入与 stitched

## 1. 输入与模式

```rust
fn run_walk_forward(
    data: &DataPack,
    wf_params: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &WalkForwardConfig,
) -> WalkForwardResult
```

本篇里出现的函数签名、伪代码和流程代码块，默认都按“语义伪代码”理解：

1. 重点是表达主干流程、对象来源、阶段顺序与失败语义。
2. 可以省略一部分 Rust 可编译签名细节，但不能省掉会改变控制流的契约信息。
3. 若和执行文档的最终签名存在细节差异，以本篇的主干流程和失败语义为准，以执行文档和源码落实具体签名。

`WalkForwardConfig` 至少需要明确这些字段：

```rust
struct WalkForwardConfig {
    train_active_bars: usize,
    test_active_bars: usize,
    min_warmup_bars: usize,
    warmup_mode: WfWarmupMode,
    ignore_indicator_warmup: bool,
    optimize_metric: OptimizeMetric,
}
```

字段含义先压成一张表：

| 字段                      | 含义                                     | 默认 / 约束                           |
| ------------------------- | ---------------------------------------- | ------------------------------------- |
| `train_active_bars`       | 每窗训练 `active 区间` 长度              | 必填                                  |
| `test_active_bars`        | 每窗测试 `active 区间` 长度              | 必填                                  |
| `min_warmup_bars`         | 训练包和测试包至少保留多少 base 预热 bar | 默认 `0`                              |
| `warmup_mode`             | WF 预热处理模式                          | `BorrowFromTrain` 或 `ExtendTest`     |
| `ignore_indicator_warmup` | 是否在 WF 内部忽略指标聚合预热           | 默认 `false`                          |
| `optimize_metric`         | WF 全局优化目标                          | 默认 `OptimizeMetric::CalmarRatioRaw` |

### 1.1 当前 WF 的产品边界

1. 窗口步长固定取 `step = test_active_bars`。
2. 只支持相邻窗口 `test_active` 在 base 轴上首尾相接。
3. 不支持 `step < test_active_bars` 的重叠滚动窗口。
4. 原因很直接：
   - 当前已经有“跨窗口持仓继承 + 测试预热开仓注入”，不需要再靠大量 `test_active` 重叠来模拟连续性。
   - 当前已经有 `train_warmup / test_warmup` 和自动 warmup 规划，不需要再靠小步长窗口重叠来缓解预热浪费。
   - 若强行支持更小步长滚动，会显著增加 stitched 去重、覆盖、绩效口径和真值定义复杂度。

### 1.2 `min_warmup_bars` 的边界

1. `min_warmup_bars` 当前只属于 WF 层约束，不参与初始取数 planner。
2. 若第 `0` 窗左侧历史不足以满足它，WF 会在窗口合法性校验阶段直接 fail-fast。
3. 因而当前 planner 与 WF 只在共享基础 warmup 下界上对齐；`min_warmup_bars` 是 WF-local constraint。
4. 所以“同一份 WF 配置由框架一次性规划完整输入”当前并不成立；首窗若不足，会在 WF 阶段报错，而不是 planner 阶段前推处理。

### 1.3 参数来源唯一性

先把参数来源写成一张表：

| 对象                             | 正式来源                       | 明确不允许                                                    |
| -------------------------------- | ------------------------------ | ------------------------------------------------------------- |
| 优化搜索空间                     | `wf_params: &SingleParamSet`   | 从 `template` 或 `settings` 再派生第二套搜索空间              |
| 指标 warmup helper 输入          | `wf_params.indicators`         | 在 WF 层手工物化第二套 concrete indicator params              |
| backtest exec warmup helper 输入 | `wf_params.backtest`           | 在 WF 层手工物化第二套 concrete runtime params                |
| 优化目标                         | `config.optimize_metric`       | 从窗口局部结果、`template` 或 `settings` 再推导第二套优化目标 |
| `template`                       | 模板与执行规则                 | 优化搜索空间或优化目标                                        |
| `settings`                       | 执行阶段、返回控制与运行时设置 | 优化搜索空间或优化目标                                        |

补充说明：

1. `SingleParamSet` 是整棵参数树，叶子节点 `Param` 同时包含 `value / min / max / step / optimize`。
2. 因此同一棵 `SingleParamSet` 既能表达固定单组参数，也能表达优化搜索空间。
3. `run_optimization(...)` 只允许从这份 `wf_params` 读取搜索空间：
   - `optimize = true` 的字段进入优化域
   - `optimize = false` 的字段保持固定
4. `resolve_contract_warmup_by_key(...)` / `resolve_indicator_contracts(...)` 一律只消费 `wf_params.indicators`。
5. `resolve_backtest_exec_warmup_base(...)` 一律只消费 `wf_params.backtest`。
6. 对会影响 warmup 的可优化字段，统一在 helper 内部按 `Param.value / Param.max` 规则解析。

预热模式：

```rust
enum WfWarmupMode {
    BorrowFromTrain,
    ExtendTest,
}
```

### 1.4 预热模式与 `ignore_indicator_warmup`

`ignore_indicator_warmup` 的语义必须写死：

1. `false`：
   - 正常使用 `resolve_indicator_contracts(...)` 返回的真实聚合预热需求
   - 这是默认值，也是唯一推荐口径
   - 参数解析规则直接沿用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里 `resolve_indicator_contracts(...)` 的定义
2. `true`：
   - 在 WF 内部把聚合预热结果统一截获为 `0`
   - 后续正常走 `BorrowFromTrain | ExtendTest` 的窗口规划、切片、跨窗注入与 stitched
3. 这个开关只用于：
   - “开启预热 vs 关闭预热”的对照实验
   - 备胎方案
4. 打开后，当前窗口 `active` 允许早于指标真正稳定点，因此该模式下的结果属于非严格预热口径。
5. 因此 `ignore_indicator_warmup = true` 不是默认推荐模式；只有在明确要做对照实验或启用备胎方案时才允许开启。

## 2. 窗口索引总工具函数

这里把 base 索引和 source 索引统一收成一个总工具函数：

```rust
struct WindowSliceIndices {
    source_ranges: HashMap<String, Range<usize>>, // WF 输入 DataPack.source 各表的切片区间，必须包含 data.base_data_key
    ranges_draft: HashMap<String, SourceRange>,   // 新窗口 DataPack 的 ranges 草稿
}

struct WindowIndices {
    train_pack: WindowSliceIndices,
    test_pack: WindowSliceIndices,
    test_active_base_row_range: Range<usize>, // 虽然作为 WindowMeta 字段对外暴露，但只供 stitched schedule 内部重基使用：当前窗口 test_active 在原始 WF 输入 data.base 轴上的绝对半开区间
}

fn build_window_indices(
    data: &DataPack,
    config: &WalkForwardConfig,
    required_warmup_by_key: &HashMap<String, usize>,
) -> Vec<WindowIndices>
```

这个工具函数的适用范围要写死：

1. 它只服务 **WF 场景下的 `DataPack` 窗口切片规划**。
2. 它的输入 `data` 就是 `run_walk_forward(...)` 最初接受的 WF 输入 `DataPack`。
3. 它不是通用索引规划工具，不承担 `ResultPack` 单独切片、任意容器切片或别的复用场景。
4. `ResultPack` 不单独做窗口索引规划；窗口 `DataPack` 切好后，`ResultPack` 由回测引擎直接基于这个窗口 `DataPack` 生成。

本节里的 `2.1 / 2.2 / 2.3` 都只是 `build_window_indices(...)` 内部的 3 个私有函数说明：

1. 它们不对外暴露。
2. 它们只服务当前 WF 场景，不追求抽象成通用规划能力。
3. 它们只是把 `build_window_indices(...)` 内部算法封装成 3 个私有步骤，避免正文太散。

内部流程分三步：

1. 先调用私有函数 `build_base_window_ranges(...)`，生成每个窗口的 base 规划。
2. 再调用私有函数 `project_pack_source_ranges(...)`，计算每个 pack 里各个 `source[k]` 在 WF 输入 `DataPack.source` 上的切片区间。
3. 最后调用私有函数 `build_pack_ranges_draft(...)`，基于这些 `source_ranges` 和 `warmup_by_key`，一次性算出每个 pack 的 `ranges_draft`。

返回值 `Vec<WindowIndices>` 里，每个元素都同时包含：

1. 当前窗口训练包容器和测试包容器各自的 `source_ranges`
2. 当前窗口训练包容器和测试包容器各自已经算好的 `ranges_draft`
3. 当前窗口 `test_active` 在原始 WF 输入 `DataPack.base` 轴上的绝对半开区间 `test_active_base_row_range`

这里要明确区分两类索引空间：

1. `source_ranges` 指向 WF 输入 `DataPack.source` 中各个 `DataFrame` 的行号区间。
2. 因为这里讨论的是 `DataPack` 的窗口切片，所以 `source_ranges` 必须覆盖全部 `S_keys`，并且必然包含 `data.base_data_key`。
3. `source_ranges[data.base_data_key]` 就是当前 pack 在 WF 输入 `DataPack.source` 里 base 那张表上的切片区间。
4. `ranges_draft` 只描述**新窗口 `DataPack` 自身**的 `warmup_bars / active_bars / pack_bars`，和 WF 输入 `DataPack` 的索引空间无关。
5. `ranges_draft` 不能直接拿去切 WF 输入 `DataPack`；它只服务新容器构建。

### 2.1 私有函数：`build_base_window_ranges(...)`

定义：

1. `N = data.mapping.height()`
2. `T = train_active_bars`
3. `S = test_active_bars`
4. `P_min = min_warmup_bars`
5. `W_required[base]` 就是 `required_warmup_by_key[base]`
6. `P_train = 训练包的 base 预热长度`
7. `P_test = 测试包的 base 预热长度`
8. `w = window_idx`，即第几个窗口，从 `0` 开始

`P_train / P_test` 的计算：

```text
BorrowFromTrain | ExtendTest:
    P_train = max(W_required[base], P_min)
    P_test  = max(W_required[base], P_min, 1)
```

说明：

1. `P_train` 和 `P_test` 必须拆开写，不能再混成一个统一的 `P`。
2. 训练预热严格讲可以为 `0`，因此 `P_train` 不强行要求至少 `1`。
3. 测试预热必须至少为 `1`，因为后续跨窗信号继承与注入依赖测试预热段存在。

算法：

1. 先定义第 `0` 窗。
2. 后续第 `w` 窗，都在第 `0` 窗基础上整体平移 `w * S`。

第 `0` 窗：

```text
BorrowFromTrain:
    train_warmup_0 = [0, P_train)
    train_active_0 = [P_train, P_train + T)
    test_warmup_0 = [P_train + T - P_test, P_train + T)
    test_active_0 = [P_train + T, P_train + T + S)

ExtendTest:
    train_warmup_0 = [0, P_train)
    train_active_0 = [P_train, P_train + T)
    test_warmup_0 = [P_train + T, P_train + T + P_test)
    test_active_0 = [P_train + T + P_test, P_train + T + P_test + S)
```

第 `w` 窗：

```text
shift = w * S

train_warmup_w = train_warmup_0 + shift
train_active_w = train_active_0 + shift
test_warmup_w = test_warmup_0 + shift
test_active_w = test_active_0 + shift
```

补充说明：

1. `ExtendTest` 下，这四段在 base 轴上是顺排的。
2. `BorrowFromTrain` 下，`test_warmup` 是借训练尾部，因此会与 `train_active` 尾部重叠。
3. 所以这里的 `train_warmup / train_active / test_warmup / test_active` 表示四个逻辑角色，不要求四段在 base 轴上互不重叠。

`train_warmup / train_active / test_warmup / test_active` 这四段主要作为 `build_window_indices(...)` 的**内部规划变量**存在，不整组原样外露；但其中 `test_active` 在原始 base 轴上的绝对半开区间，必须进一步落成 `test_active_base_row_range`，供后续 stitched `backtest_schedule` 重基使用。

规则：

1. 窗口步长取 `S`，即 `test_active` 段长度。
2. 因此前一窗的 `test_active` 段，会自然成为后一窗训练数据的一部分。
3. 这里不是按训练窗长度 `T` 滑动，而是按测试窗长度 `S` 滑动。
4. 第 `0` 窗若训练预热数据不足，直接报错。
5. 第 `0` 窗若训练 `active 区间` 数据不足，直接报错。
6. 第 `0` 窗若测试预热数据不足，直接报错。
7. 第 `0` 窗只对 `train_warmup / train_active / test_warmup` 做硬校验；`test_active` 若越界则统一截短处理。
8. 若某一窗的 `test_active.end > N`，则该窗 `test_active.end` 直接取 `N`；允许最后一窗测试数据不足，以贴近实盘滚动到数据尾部时的行为。
9. 若第 `0` 窗同时也是最后一窗，则它的 `test_active` 也走同一条截短规则，不单独报错。
10. 残缺 `test_active` 必须满足最小测试长度：
    - 若第 `0` 窗截短后 `< 3`，则直接报错，表示无法生成任何合法窗口。
    - 若后续窗口截短后 `< 3`，则最后一窗不生成。
    - 当前正式语义下，`test_active` 的最小合法长度必须是 `3`：
      - 第 `1` 根 active bar 承载 carry 开仓信号
      - 第 `2` 根 active bar 开盘执行继承开仓
      - 尾部强平仍固定写在 `pack_bars - 2`
      - 若 `active_bars = 2`，carry 行与尾部强平行会落在同一根 bar 上，语义冲突
11. 对每个最终保留的窗口，还必须把：
    - `test_active_base_row_range = [test_active.start, test_active.end)`
    显式写进 `WindowIndices`。
12. 这条区间属于当前窗口在**原始 WF 输入 `DataPack.base` 轴**上的单一真值：
    - 它不是 stitched 行轴
    - 也不是窗口局部重基后的行号
    - 虽然它最终会作为 `WindowMeta` 字段对外暴露，但语义上只供 stitched `backtest_schedule` 内部重基使用
13. 后续 stitched 生成 `backtest_schedule` 时，直接对这份原始绝对区间做重基。

窗口索引校验：

1. `T >= 1, S >= 3`
2. `P_train >= 0`
3. `P_test >= 1`
4. `BorrowFromTrain` 时 `P_test <= T`
5. 至少生成 1 个窗口
6. 对每个窗口都必须满足：
   - `train_warmup.start <= train_warmup.end`
   - `train_active.start < train_active.end`
   - `test_warmup.start <= test_warmup.end`
   - `test_active.start < test_active.end`
   - 语义上：
     - 当 `warmup` 长度为 `0` 时，对应 `start == end`
     - 当 `warmup` 长度大于 `0` 时，对应 `start < end`
7. 第 `0` 窗还必须满足：
   - `train_warmup_0.start == 0`
   - `train_warmup_0.end <= N`
   - `train_active_0.start == train_warmup_0.end`
   - `train_active_0.end <= N`
   - `test_warmup_0.end <= N`
8. 对每个生成出来的窗口都必须满足：
   - `0 <= train_warmup.start <= train_warmup.end <= N`
   - `0 <= train_active.start < train_active.end <= N`
   - `0 <= test_warmup.start <= test_warmup.end <= N`
   - `0 <= test_active.start < test_active.end <= N`
9. 相邻窗口必须满足：
   - `train_warmup_{w+1}.start - train_warmup_w.start == S`
   - `train_active_{w+1}.start - train_active_w.start == S`
   - `test_warmup_{w+1}.start - test_warmup_w.start == S`
   - `test_active_{w+1}.start - test_active_w.start == S`

### 2.2 私有函数：`project_pack_source_ranges(...)`

这里不是“测试算法”，而是 **窗口 pack 级别** 的 source 索引投影算法。
当前任务里只有两个 pack：

1. `train_pack`
2. `test_pack`

本函数接受 `2.1 build_base_window_ranges(...)` 生成的窗口分段：

1. `train_warmup / train_active`
2. `test_warmup / test_active`

先定义两个 pack 的 base 语义：

```text
train_pack_base_range = [train_warmup.start, train_active.end)
train_pack_active_start = train_active.start

test_pack_base_range = [test_warmup.start, test_active.end)
test_pack_active_start = test_active.start
```

这里不额外发明 `map(...) / end_map(...)` 记号，本节所有 source 投影都直接复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里定义的真实工具函数，不允许局部再写一套时间映射逻辑。

然后分别对 `train_pack` 和 `test_pack` 各执行一次，统一使用同一套投影公式：

```text
pack_src_start = map_source_row_by_time(
    data.mapping.time[pack_base_range.start],
    data.source[k].time,
    k,
)

pack_src_end = map_source_end_by_base_end(
    data.mapping.time,
    data.source[k].time,
    pack_base_range.end,
    k,
)

source_active_start = map_source_row_by_time(
    data.mapping.time[pack_active_start],
    data.source[k].time,
    k,
)

if source_active_start < W_required[k]:
    fail("source 左侧数据不足，无法满足窗口预热")

contract_start = source_active_start - W_required[k]
source_run_start = min(pack_src_start, contract_start)
source_run_end = pack_src_end
```

含义：

1. `pack_src_start ~ pack_src_end` 保证 source 对整个 pack 的 base 区间完成全量覆盖。
2. `contract_start = source_active_start - W_required[k]` 保证 source 在 pack 的 `active` 起点之前还额外保留足够的左侧合法预热。
3. 最终起点取两者较小值，表示“既要覆盖整个 pack，又要保留 `active` 起点前的 source 预热”。
4. 这里必须先校验 `source_active_start >= W_required[k]`，再做减法；不能写成“先减后判负”，因为全文索引语义都是局部行号，实际实现应按 `usize` 对待，直接先减会下溢。
5. 一旦 `source_active_start < W_required[k]`，说明上游取数没保够，直接报错。
6. `source_run_end = pack_src_end`，表示右边界不额外延伸；当前窗口只要求 source 覆盖到该 pack 的末端。
7. `warmup_by_key` 也直接由这里顺手得到：
   - 对 `k = data.base_data_key`，`warmup_by_key[k] = pack_active_start - pack_base_range.start`
   - 对非 base `k`，`warmup_by_key[k] = source_active_start - source_run_start`
8. `source_ranges` 也在这里直接落成：
   - `source_ranges[k] = [source_run_start, source_run_end)`

特殊情况：

1. 对 `k = data.base_data_key`，不需要再做 backward asof 投影。
2. 直接令 `source_ranges[data.base_data_key] = pack_base_range` 即可。

这里要把两个阶段彻底分开：

1. `W_applied[k]`
   - 只表示“指标 warmup 在 WF 指标策略作用后的结果”
   - 它是共享真值，但不是本篇窗口规划真正直接消费的最终下界
2. `W_required[k]`
   - 才属于本篇真正直接消费的窗口规划下界
   - 它表示：在当前 WF 配置下，`source[k]` 至少还需要保留多少左侧合法预热
   - 对非 base source，它通常退化为 `W_applied[k]`
   - 对 base source，它还可能额外包含 backtest exec warmup
3. `warmup_by_key[k]`
   - 属于 `build_window_indices(...)` 内部
   - 但它已经不是“契约下界”，而是当前窗口最终真正决定写进新容器的预热长度
   - 这个值可能等于 `W_required[k]`，也可能因为首尾覆盖而更大
4. `ranges[k].warmup_bars`
   - 是 `warmup_by_key[k]` 写入新窗口 `DataPack` 之后的最终落地形式
   - 后续真正切片、重基、绩效统计、`extract_active(...)` 都只能认这个真值

所以这里的规则是：

1. 先用 `W_required[k]` 规划“至少要保留多少左侧预热”
2. 再由 `warmup_by_key[k]` 把当前窗口的真实预热长度定死
3. 最后由 `ranges[k].warmup_bars` 把这份真实预热写入新容器

一旦进入真正的切片 / 重基步骤，就直接沿用本篇开头第 3 条，不用 `W_required[k]` 裁数据。

### 2.3 私有函数：`build_pack_ranges_draft(...)`

本函数接受 `2.2 project_pack_source_ranges(...)` 生成的：

1. `source_ranges`
2. `warmup_by_key`

规则：

1. 对任意一个切片目标：
   - `ranges_draft[base].warmup_bars = warmup_by_key[base]`
   - `ranges_draft[base].pack_bars = source_ranges[data.base_data_key].end - source_ranges[data.base_data_key].start`
   - `ranges_draft[base].active_bars = ranges_draft[base].pack_bars - ranges_draft[base].warmup_bars`
2. 对每个非 base `k`：
   - `ranges_draft[k].warmup_bars = warmup_by_key[k]`
   - `ranges_draft[k].pack_bars = source_ranges[k].end - source_ranges[k].start`
   - `ranges_draft[k].active_bars = ranges_draft[k].pack_bars - ranges_draft[k].warmup_bars`
3. 因为 `source_ranges[k]` 本身已经是半开区间 `[start, end)`，所以这里的 `pack_bars` 可以直接由索引长度算出，不需要等到真正切 DataFrame 后再反推。
4. `active_bars` 直接由 `pack_bars - warmup_bars` 得到，外部无需再做一次 `total - warmup` 计算。
5. 这样 `slice_data_pack_by_base_window(...)` 就只负责按索引切片并调用 `build_data_pack(...)`，不重复计算 `ranges`。

`build_window_indices(...)` 最终接受并组装的内容：

1. 对每个窗口，产出：
   - `train_pack = { source_ranges, ranges_draft }`
   - `test_pack = { source_ranges, ranges_draft }`
   - `test_active_base_row_range = [test_active.start, test_active.end)`
2. `build_window_indices(...)` 最终返回的 `Vec<WindowIndices>`，就是由这两部分组装而成。

## 4. DataPack 窗口切片工具函数

```rust
fn slice_data_pack_by_base_window(
    data: &DataPack,
    indices: &WindowSliceIndices,
) -> DataPack
```

参数语义：

1. `indices.source_ranges[k]`：当前这个切片目标里每个 `source[k]` 在 WF 输入 `DataPack.source` 上应取的切片区间。
2. `indices.source_ranges[data.base_data_key]`：当前这个切片目标在 WF 输入 `DataPack` 的 base 轴上的区间，本身就是可直接使用的半开区间 `[start, end)`。
3. `indices.ranges_draft`：当前这个切片目标在新窗口 `DataPack` 里应写入的 `ranges` 草稿。

核心原则：

1. `WindowSliceIndices` 已经是最终切片结果：
   - `source_ranges` 可以直接用于切片
   - `ranges_draft` 可以直接用于赋值
2. 因此 `slice_data_pack_by_base_window(...)` 不做额外索引计算。
3. 它只负责按现成索引处理各字段，然后调用 `build_data_pack(...)`。

DataPack 各字段处理：

1. `source`
   - 对每个 `k ∈ S_keys`，直接按 `indices.source_ranges[k]` 切 `data.source[k]`
   - 切完后的结果写入 `source_slice_map`
   - 这里不做任何再次 mapping 计算；`indices.source_ranges` 本身就是最终可直接使用的切片索引
2. `mapping`
   - 这里直接丢弃旧 `mapping`
   - 统一交给 `build_data_pack(...)` 重新构建
3. `skip_mask`
   - 若存在，则按 `indices.source_ranges[data.base_data_key]` 切
   - 因为 `skip_mask` 挂在 base 轴上
4. `base_data_key`
   - 原样保留 `data.base_data_key`
5. `ranges`
   - 这里直接丢弃旧 `ranges`
   - 新窗口 `DataPack` 直接使用 `indices.ranges_draft`

执行步骤：

1. 构造 `source_slice_map`
2. 构造 `skip_mask_slice`
3. 取 `base_data_key = data.base_data_key`
4. 取 `ranges_draft = indices.ranges_draft`
5. 调 `build_data_pack(source_slice_map, base_data_key, ranges_draft, skip_mask_slice)`
6. 返回新的窗口 `DataPack`

## 5. 跨窗信号注入

这里先把跨窗持仓方向的最小类型定义清楚：

```rust
enum CrossSide {
    Long,
    Short,
}
```

### 5.1 末根持仓方向判定

```rust
fn detect_last_bar_position(
    backtest: &DataFrame,
) -> Result<Option<CrossSide>, QuantError>
```

规则：

1. 这里直接复用 `doc/backtest/state_machine_constraints.md` 里已经定义好的价格驱动状态约束；这四列不是一次性成交事件列。
2. 读取 `backtest` 最后一根 base 行上的：
   - `entry_long_price`
   - `exit_long_price`
   - `entry_short_price`
   - `exit_short_price`
3. 若 `entry_long_price` 非空且 `exit_long_price` 为空，则判定末根仍持有 `Long`
4. 若 `entry_short_price` 非空且 `exit_short_price` 为空，则判定末根仍持有 `Short`
5. 若两者同时成立，直接报错
6. 若两者都不成立，则返回 `Ok(None)`
7. 因此这里的返回契约必须写成 `Result<Option<CrossSide>, QuantError>`：
   - `Ok(Some(Long))`
   - `Ok(Some(Short))`
   - `Ok(None)`
   - `Err(...)`

### 5.2 只注入 carry 的信号

```rust
fn build_carry_only_signals(
    raw_signal_stage_result: &ResultPack,
    prev_last_bar_position: Option<CrossSide>,
) -> DataFrame
```

参数含义：

1. `raw_signal_stage_result`
   - 当前窗口测试包第一次评估得到的 `ResultPack`
   - 这里至少需要用到：
     - `raw_signal_stage_result.signals`
     - `raw_signal_stage_result.base_data_key`
     - `raw_signal_stage_result.ranges[raw_signal_stage_result.base_data_key]`
2. `prev_last_bar_position`
   - 由外部主循环提前准备好的、上一窗口未注入强平前最后一根持仓方向
   - 若当前是第 `0` 窗，则为 `None`

规则：

1. `raw_signal_stage_result` 就是第一次评估得到的测试包 `ResultPack`；这里一律从 `raw_signal_stage_result.ranges[raw_signal_stage_result.base_data_key]` 读取已经落地好的预热边界
2. 测试预热段禁开仓属于回测引擎内部信号模块职责：
   - 在生成 `raw_signal_stage_result.signals` 时，内部实际使用的是对应 `test_pack_data.ranges[test_pack_data.base_data_key].warmup_bars`
   - `build_carry_only_signals(...)` 不重新定义这条规则，只在后处理阶段复用 `raw_signal_stage_result` 里已经表达好的等价边界
3. 先取：
   - `raw_signals = raw_signal_stage_result.signals`
   - `test_pack_base_warmup = raw_signal_stage_result.ranges[raw_signal_stage_result.base_data_key].warmup_bars`
4. 再对整个 `raw_signals` 做一份 Polars 浅拷贝；后续 carry 注入都在这份副本上完成；不要假设对原始 `DataFrame` 做原地修改
5. 计算跨窗开仓注入位置：
   - 这里指的是当前注入目标 `signals` 这个 `DataFrame` 上，测试 `active 区间` 的第一根 base 行
   - `test_pack_active_first_idx = test_pack_base_warmup`
6. 若 `prev_last_bar_position` 表示上一窗口末根仍有持仓，则在 `test_pack_active_first_idx` 注入同向开仓：
   - `Long`：该行必须整行覆盖成：
     - `entry_long = true`
     - `entry_short = false`
     - `exit_long = false`
     - `exit_short = false`
   - `Short`：该行必须整行覆盖成：
     - `entry_long = false`
     - `entry_short = true`
     - `exit_long = false`
     - `exit_short = false`
7. 若 `prev_last_bar_position = None`：
   - `carry_only_signals` 必须与原始 `raw_signals` 完全一致
   - 不做任何额外改写
8. 这里显式接受一条保守语义：
   - 由于当前引擎按 `prev_bar.signal -> current_bar.open` 执行
   - carry 开仓信号写在 active 第一根
   - 真正的继承开仓会在第二根 active bar 的开盘执行
   - 这属于有意接受的一根延迟，窗口边界不追求无缝衔接
   - 这类跨窗继承带来的额外偏差可以视为悲观预估；若希望尽量减小这部分额外偏差，建议使用更小的进场周期
### 5.3 最终正式信号

```rust
fn build_final_signals(
    raw_signal_stage_result: &ResultPack,
    carry_only_signals: &DataFrame,
) -> DataFrame
```

规则：

1. `build_final_signals(...)` 以 `carry_only_signals` 为输入，再追加窗口尾部强平
2. 先取：
   - `test_pack_base_pack_bars = raw_signal_stage_result.ranges[raw_signal_stage_result.base_data_key].pack_bars`
3. 再计算离场注入位置：
   - `test_pack_exit_idx = test_pack_base_pack_bars - 2`
4. 该行必须按“强制全平”整行覆盖成：
   - `entry_long = false`
   - `entry_short = false`
   - `exit_long = true`
   - `exit_short = true`
5. 原因是信号通常在下一根 bar 才真正触发，因此要在倒数第二根注入，才能保证最后一根完成平仓

### 5.4 两份信号的职责边界

1. `carry_only_signals`
   - 只用于判定“当前窗口如果不做尾部强平，是否会自然把仓位带到下一窗口”
2. `final_signals`
   - 才用于当前窗口正式返回、正式 stitched、正式 performance
   - 这里的跨窗 carry 开仓位于 active 第一根
   - 因此后续 `extract_active(...)` 之后，carry 行保留在 active 视图里
