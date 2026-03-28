# 向前测试、窗口切片、跨窗注入与 stitched

本篇只讲 walk-forward 相关链路。

本篇直接复用两个上游归属文档里的共享定义：

1. [01_overview_and_foundation.md](./01_overview_and_foundation.md)
   - `resolve_indicator_contracts(...)`
   - `W_resolved[k] / W_normalized[k] / W_applied[k]`
   - `DataPack / ResultPack / SourceRange / mapping` 通用约束
2. [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md)
   - `build_result_pack(...)` 的结果包构建语义
   - `extract_active(...)` 的 active 视图语义

因此下文不再重复定义这些共享内容本身，只定义 WF / stitched 专属的派生规则、窗口索引、阶段契约与跨窗语义。

这里把边界再写死一次，避免和 `01` 的定义权打架：

1. `W_applied[k]` 的定义权属于 [01_overview_and_foundation.md](./01_overview_and_foundation.md)。
2. 本篇不重新定义 `W_applied[k]` 的公式，只定义它在 WF 中如何被消费。
3. 因此本篇出现 `W_applied[k]` 时，一律按“WF 输入真值”理解，而不是本篇新引入的一层命名。

一个容易踩坑的总原则先写在前面：

1. 本篇直接沿用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 已定义的 `W_applied[k]`；它表示应用 `config.ignore_indicator_warmup` 后，WF 当前实际采用的契约预热值。
2. 任何真正的切片、拼接、重基、写 `ranges`，都必须以当前窗口的**真实预热边界**为准。
   - 在 builder 调用前，这个值叫 `warmup_by_key[k]`
   - 在 builder 写入新容器后，这个值就落成 `ranges[k].warmup_bars`
   - 两者不是两套规则，而是同一语义在不同阶段的名字
3. 不能回退去用 `W_applied[k]` 直接裁数据；否则会漏掉 source 为首尾覆盖额外保留的左侧 bar。
4. 本篇所有切片都默认直接使用 Polars 的切片/复制语义；因为 Polars 的 `DataFrame / Series` 切片与 copy 默认都是浅拷贝，这里按轻量操作理解，不额外讨论深拷贝优化。
5. 本篇命名统一采用三段后缀：
   - `*_pack`：整包，包含预热段和非预热有效段
   - `*_warmup`：预热段
   - `*_active`：非预热有效段
   - 配置字段也统一采用明确命名，不保留裸 `train_bars / test_bars`
6. 当前 WF 的产品边界也直接写死：
   - 窗口步长固定取 `step = test_active_bars`
   - 只支持相邻窗口 `test_active` 在 base 轴上首尾相接
   - 不支持 `step < test_active_bars` 的重叠滚动窗口
7. 原因也直接定死：
   - 从跨窗口连续性的角度看，当前已经有“跨窗口持仓继承 + 测试预热开仓注入”，不需要再靠 `test_active` 大量重叠来模拟连续性
   - 从预热利用率的角度看，当前已经有 `train_warmup / test_warmup` 和自动 warmup 规划，不需要再靠小步长窗口重叠来缓解预热浪费
   - 若强行支持更小步长滚动，会显著增加 stitched 的去重、覆盖、绩效口径和真值定义复杂度，收益远小于新增复杂度

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

这里先统一说明一条摘要层约束：

1. 本篇里出现的函数签名、伪代码和流程代码块，主要用于表达主干流程、对象来源、阶段顺序与失败语义。
2. 这些代码块默认按“语义伪代码”理解，不要求把 Rust 真实签名里的错误包装、生命周期、借用形式、PyO3 细节全部展开。
3. 因此：
   - 摘要层可以省略一部分 `Result<..., QuantError>` 包装噪音
   - 但不能省掉“这里存在直接报错分支”这个事实
4. 若摘要层代码块与执行文档里的正式接口签名存在细节差异：
   - 主干流程、对象来源、边界条件与失败语义以本篇为准
   - 具体函数签名、返回包装与实现细节以 `02_execution/*.md` 和最终源码为准

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

字段含义：

1. `train_active_bars`：每窗训练非预热有效段长度
2. `test_active_bars`：每窗测试非预热有效段长度
3. `min_warmup_bars`：训练包和测试包都至少应保留多少 base 预热 bar；默认值为 `0`
4. `warmup_mode`：向前测试的预热处理模式
5. `ignore_indicator_warmup`：是否在 WF 内部忽略指标聚合预热；默认值必须为 `false`
6. `optimize_metric`：WF 的全局优化目标；默认值为 `OptimizeMetric::CalmarRatioRaw`

这里再补一条边界说明：

1. `min_warmup_bars` 当前只属于 WF 层约束，不参与初始取数 planner；默认值为 `0`，表示不额外提高 WF 预热下界。
2. 这不会造成 quietly wrong：
   - 若第 `0` 窗左侧历史不足以满足 `min_warmup_bars`
   - WF 会在窗口合法性校验阶段直接报错
   - 不会继续带着错误窗口结果往后运行
3. 在典型 WF 使用场景里，输入数据通常远大于单窗需求，因此即使初始取数 planner 不显式感知 `min_warmup_bars`，第 `0` 窗左侧历史也往往天然足够。
4. 因此这个问题当前更像职责边界选择，而不是正确性漏洞：
   - 常规大样本场景下通常无影响
   - 只有在小样本、左边界贴近、limit 较紧时，才可能在第 `0` 窗显式触发不足报错
5. 在尚未形成“用户只定义一次、框架内部自动同时喂给 planner 与 WF”的统一入口之前，暂不把 `min_warmup_bars` 前推到初始取数 planner。

这里还要把 WF 的参数来源写死：

1. `run_walk_forward(...)` 的优化搜索空间，直接来自输入参数 `wf_params: &SingleParamSet`。
2. 这里要把两个类型的层级关系说清楚：
   - `SingleParamSet`：整棵参数树
   - `Param`：参数树里的单个叶子参数节点
3. `SingleParamSet` 这棵参数树里的每个 `Param` 节点都已经包含：
   - `value`
   - `min`
   - `max`
   - `step`
   - `optimize`
4. 因此 `SingleParamSet` 这棵参数树既能表达“固定单组参数”，也能表达“优化搜索空间”。
5. `run_optimization(...)` 只允许从这份 `wf_params` 读取搜索空间：
   - `optimize = true` 的字段进入优化域
   - `optimize = false` 的字段保持固定
6. `wf_params` 这棵参数树里，指标参数子树的唯一读取路径也必须写死为：
   - `wf_params.indicators`
7. 后续所有指标契约 warmup 相关共享 helper：
   - `resolve_contract_warmup_by_key(...)`
   - `normalize_contract_warmup_by_key(...)`
   - `apply_wf_warmup_policy(...)`
   一律只允许消费这份 `wf_params.indicators`。
8. 因此在本篇里：
   - `wf_params` 表示 `run_walk_forward(...)` 的整棵输入参数树
   - `wf_params.indicators` 表示从这棵参数树直接取出的“指标参数子树”
   - 后文若出现 `wf_params.indicators`，都按这个固定对象来源理解；它也是当前实现唯一合法的指标参数读取入口
   - 任何 WF 内部涉及指标契约 warmup 的读取，只要没有走这条路径，就视为违背本任务契约
9. 这条读取路径已与当前源码结构对齐：
   - Rust `SingleParamSet` 直接定义 `pub indicators: IndicatorsParams`
   - PyO3 stub 也直接暴露 `SingleParamSet.indicators`
   - 因此这里不是文档侧额外发明的新 extractor 约定
10. `run_optimization(...)` 的优化目标唯一来自 `config.optimize_metric`。
11. `template` 只提供模板与执行规则，不提供优化搜索空间或优化目标。
12. `settings` 只提供执行阶段、返回控制与运行时设置，不提供优化搜索空间或优化目标。

预热模式：

```rust
enum WfWarmupMode {
    BorrowFromTrain,
    ExtendTest,
}
```

`ignore_indicator_warmup` 的语义必须写死：

1. `false`：
   - 正常使用 `resolve_indicator_contracts(...)` 返回的真实聚合预热需求
   - 这是默认值，也是唯一推荐口径
   - 参数解析规则直接沿用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里 `resolve_indicator_contracts(...)` 的定义
2. `true`：
   - 在 WF 内部把聚合预热结果统一截获为 `0`
   - 后续仍正常走 `BorrowFromTrain | ExtendTest` 的窗口规划、切片、跨窗注入与 stitched
3. 这个开关只用于：
   - “开启预热 vs 关闭预热”的对照实验
   - 备胎方案
4. 打开后，当前窗口 `active` 允许早于指标真正稳定点，因此该模式下的结果不再具备“严格预热口径”下的同等可信度。
5. 因此 `ignore_indicator_warmup = true` 不是默认推荐模式；只有在明确要做对照实验或启用备胎方案时才允许开启。

## 2. 窗口索引总工具函数

这里不再把 base 索引和 source 索引拆成很多小 planning 函数，而是统一收成一个总工具函数：

```rust
struct WindowSliceIndices {
    source_ranges: HashMap<String, Range<usize>>, // WF 输入 DataPack.source 各表的切片区间，必须包含 data.base_data_key
    ranges_draft: HashMap<String, SourceRange>,   // 新窗口 DataPack 的 ranges 草稿
}

struct WindowIndices {
    train_pack: WindowSliceIndices,
    test_pack: WindowSliceIndices,
}

fn build_window_indices(
    data: &DataPack,
    config: &WalkForwardConfig,
    applied_contract_warmup_by_key: &HashMap<String, usize>,
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
5. `W_applied[base]` 就是 `applied_contract_warmup_by_key[base]`
6. `P_train = 训练包的 base 预热长度`
7. `P_test = 测试包的 base 预热长度`
8. `w = window_idx`，即第几个窗口，从 `0` 开始

`P_train / P_test` 的计算：

```text
BorrowFromTrain | ExtendTest:
    P_train = max(W_applied[base], P_min)
    P_test  = max(W_applied[base], P_min, 1)
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

`train_warmup / train_active / test_warmup / test_active` 这四段只作为 `build_window_indices(...)` 的**内部规划变量**存在，不再作为最终对外返回结构的一部分。

规则：

1. 窗口步长取 `S`，即 `test_active` 段长度。
2. 因此前一窗的 `test_active` 段，会自然成为后一窗训练数据的一部分。
3. 这里不是按训练窗长度 `T` 滑动，而是按测试窗长度 `S` 滑动。
4. 第 `0` 窗若训练预热数据不足，直接报错。
5. 第 `0` 窗若训练有效段数据不足，直接报错。
6. 第 `0` 窗若测试预热数据不足，直接报错。
7. 第 `0` 窗只对 `train_warmup / train_active / test_warmup` 做硬校验；`test_active` 若越界则统一截短处理。
8. 若某一窗的 `test_active.end > N`，则把该窗 `test_active.end` 改成 `N` 后保留；允许最后一窗测试数据不足，以贴近实盘滚动到数据尾部时的行为。
9. 若第 `0` 窗同时也是最后一窗，则它的 `test_active` 也走同一条截短规则，不单独报错。
10. 残缺 `test_active` 仍然必须满足最小测试长度：
    - 若第 `0` 窗截短后 `< 2`，则直接报错，表示无法生成任何合法窗口。
    - 若后续窗口截短后 `< 2`，则最后一窗不生成。

窗口索引校验：

1. `T >= 1, S >= 2`
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

这里不再额外发明 `map(...) / end_map(...)` 记号，本节所有 source 投影都直接复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里定义的真实工具函数，不允许局部再写一套时间映射逻辑。

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

if source_active_start < W_applied[k]:
    fail("source 左侧数据不足，无法满足窗口预热")

contract_start = source_active_start - W_applied[k]
source_run_start = min(pack_src_start, contract_start)
source_run_end = pack_src_end
```

含义：

1. `pack_src_start ~ pack_src_end` 保证 source 对整个 pack 的 base 区间完成全量覆盖。
2. `contract_start = source_active_start - W_applied[k]` 保证 source 在 pack 的 `active` 起点之前还额外保留足够的左侧契约预热。
3. 最终起点取两者较小值，表示“既要覆盖整个 pack，又要保留 `active` 起点前的 source 预热”。
4. 这里必须先校验 `source_active_start >= W_applied[k]`，再做减法；不能写成“先减后判负”，因为全文索引语义都是局部行号，实际实现应按 `usize` 对待，直接先减会下溢。
5. 一旦 `source_active_start < W_applied[k]`，说明上游取数没保够，直接报错。
6. `source_run_end = pack_src_end`，表示右边界不再额外延伸；当前窗口只要求 source 覆盖到该 pack 的末端。
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
   - 只属于**窗口规划阶段**
   - 它表示：在当前 WF 配置下，`source[k]` 至少还需要保留多少左侧契约预热
   - 因此它只参与 `source_run_start / source_run_end` 的估算
2. `warmup_by_key[k]`
   - 仍然属于 `build_window_indices(...)` 内部
   - 但它已经不是“契约下界”，而是当前窗口最终真正决定写进新容器的预热长度
   - 这个值可能等于 `W_applied[k]`，也可能因为首尾覆盖而更大
3. `ranges[k].warmup_bars`
   - 是 `warmup_by_key[k]` 写入新窗口 `DataPack` 之后的最终落地形式
   - 后续真正切片、重基、绩效统计、`extract_active(...)` 都只能认这个真值

所以这里的规则是：

1. 先用 `W_applied[k]` 规划“至少要保留多少左侧预热”
2. 再由 `warmup_by_key[k]` 把当前窗口的真实预热长度定死
3. 最后由 `ranges[k].warmup_bars` 把这份真实预热写入新容器

一旦进入真正的切片 / 重基步骤，就不能再跳回去直接用 `W_applied[k]`，否则会漏掉 source 为首尾覆盖额外保留的左侧 bar。

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
4. `active_bars` 直接由 `pack_bars - warmup_bars` 得到，不再要求外部再做一次 `total - warmup` 计算。
5. 这样 `slice_data_pack_by_base_window(...)` 就只负责按索引切片并调用 `build_data_pack(...)`，不再重复计算 `ranges`。

`build_window_indices(...)` 最终接受并组装的内容：

1. 对每个窗口，产出：
   - `train_pack = { source_ranges, ranges_draft }`
   - `test_pack = { source_ranges, ranges_draft }`
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
2. 因此 `slice_data_pack_by_base_window(...)` 不再做额外索引计算。
3. 它只负责按现成索引处理各字段，然后调用 `build_data_pack(...)`。

DataPack 各字段处理：

1. `source`
   - 对每个 `k ∈ S_keys`，直接按 `indices.source_ranges[k]` 切 `data.source[k]`
   - 切完后的结果写入 `source_slice_map`
   - 这里不再做任何再次 mapping 计算；`indices.source_ranges` 本身就是最终可直接使用的切片索引
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

1. `raw_signal_stage_result` 就是第一次评估得到的测试包 `ResultPack`；这里一律从 `raw_signal_stage_result.ranges[raw_signal_stage_result.base_data_key]` 读取已经落地好的预热边界，不再额外传 `test_warmup_len / test_len`
2. 测试预热段禁开仓属于回测引擎内部信号模块职责：
   - 在生成 `raw_signal_stage_result.signals` 时，内部实际使用的是对应 `test_pack_data.ranges[test_pack_data.base_data_key].warmup_bars`
   - `build_carry_only_signals(...)` 不重新定义这条规则，只在后处理阶段复用 `raw_signal_stage_result` 里已经表达好的等价边界
3. 先取：
   - `raw_signals = raw_signal_stage_result.signals`
   - `test_pack_base_warmup = raw_signal_stage_result.ranges[raw_signal_stage_result.base_data_key].warmup_bars`
4. 再对整个 `raw_signals` 做一份 Polars 浅拷贝；后续 carry 注入都在这份副本上完成；不要假设对原始 `DataFrame` 做原地修改
5. 计算跨窗开仓注入位置：
   - 这里指的是当前注入目标 `signals` 这个 `DataFrame` 上，测试预热段的最后一根 base 行
   - `test_pack_warmup_last_idx = test_pack_base_warmup - 1`
6. 若 `prev_last_bar_position` 表示上一窗口末根仍有持仓，则在 `test_pack_warmup_last_idx` 注入同向开仓：
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

# 这里与初始取数 planner 复用 01 里已定义的同一套共享 helper；
# 对 optimize=true 的指标参数，内部统一按 Param.max 解析，因此两边天然共享同一份最坏 warmup 真值

windows = build_window_indices(data, config, applied_contract_warmup_by_key)
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
    natural_ctx = BacktestContext::new()
    natural_ctx.indicator_dfs = raw_signal_stage_result.indicators
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
    final_ctx = BacktestContext::new()
    final_ctx.indicator_dfs = raw_signal_stage_result.indicators
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
   - 用于 stitched
   - 用于正式 performance
8. `final_test_pack_result` 必须保证：
   - `indicators` 可用
   - `signals` 可用
   - `backtest` 可用
   - `performance` 可用
9. `final_ctx` 故意不再走顶层单次执行入口，而是手动构造 `BacktestContext`，直接复用第一次评估已经算好的 `indicators` 和注入后的 `signals`，因此这里只重复执行回测与绩效阶段，不再重复计算指标和信号
10. 这里的绩效函数直接接受完整 `test_pack_data` 和完整 `backtest`，再由函数内部根据 `test_pack_data.ranges[data.base_data_key].warmup_bars` 只统计非预热测试有效段
11. `final_test_pack_result` 自身已经是完整的测试包 `ResultPack`，其预热边界直接由自己的 `ranges` 表达
12. `prev_last_bar_position` 只在主循环里准备一次：
   - 来自上一窗口 `natural_test_pack_backtest_result.backtest`
   - `build_carry_only_signals(...)` 只接受这个参数，不再反向读取上一窗口 `ResultPack`
13. 因此 WF 侧不再为绩效计算额外做一轮窗口切片；窗口切片只发生在 `DataPack` 这一层
14. 同理，WF 侧也不再为 `ResultPack` 设计单独的窗口切片工具函数；每个窗口只切 `DataPack`，窗口级 `ResultPack` 由回测引擎基于窗口 `DataPack` 直接生成
15. 可以补一条一致性校验：
    - `final_test_pack_result.ranges[final_test_pack_result.base_data_key].warmup_bars == test_pack_data.ranges[test_pack_data.base_data_key].warmup_bars`
    - `final_test_pack_result.ranges[final_test_pack_result.base_data_key].pack_bars == test_pack_data.ranges[test_pack_data.base_data_key].pack_bars`
16. `run_optimization(...)` 的搜索空间来源必须唯一：
    - 直接读取 `run_walk_forward(...)` 输入的 `wf_params: &SingleParamSet`
    - 不允许从 `template` 或 `settings` 再派生第二套搜索空间定义
17. `run_optimization(...)` 的优化目标来源也必须唯一：
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
| `stitched_result_pre_capital` | required | required | required | not required | Temporary stitched result used before capital-column rebuild |
| `stitched_result` | required | required | required | required | Final formal stitched result |

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

## 8. stitched 总则

当前任务对 stitched 的明确约束：

1. stitched 只拼各窗口的 `test_active` 部分，不拼整个 `test_pack`。
2. 最终 stitched 产物里不允许保留任何重复时间。
3. `base` 轴不允许重复时间；一旦重复，直接报错。
4. 非 base `source / indicators` 在相邻窗口的 `test_active` 边界处，最多只允许 1 根时间重叠。
5. 若非 base 边界恰好重叠 1 根，则按“后窗口覆盖前窗口”处理。
6. 若非 base 边界重叠超过 1 根，则直接报错；这说明 stitched 输入不是纯 `test_active`，或窗口切片 / source 投影存在错误。
7. `stitched_data` 直接定义为：从 `run_walk_forward(...)` 最初输入的 `full_data: DataPack` 上，按 stitched 的全局 `test_active` 时间范围重新切出来的新 `DataPack`。
8. 各窗口按顺序拼出来的 `ResultPack` 字段，只负责构造 stitched 的结果字段并做一致性校验，不反过来决定 `stitched_data` 的内容。
9. 本项目彻底不再兼容 renko 等重复时间戳 source；若任一窗口内部本身存在重复时间戳，直接报错。

为什么 stitched 算法能比前面的 WF 窗口切片简单很多，也要明确写出来：

1. WF 窗口切片发生在“窗口运行前”，目标是构造一个还能继续运行的 `DataPack`。
2. 因此前面的窗口切片必须处理：
   - source 左侧预热补回
   - 对 pack base 时间轴的全量覆盖
   - `warmup_by_key`
   - `ranges_draft`
   - `mapping` 重建
3. stitched 发生在“所有窗口都已经跑完之后”。
4. 这时每个窗口真正参与汇总的只是已经算完的 `test_active` 结果，而不是还要继续运行的 `test_pack`。
5. 因此 stitched 不再需要：
   - 把 source 预热补回去
   - 再额外规划首尾覆盖
   - 再构造可运行窗口包
6. stitched 剩下的事情只有：
   - 从初始 `full_data` 直接切出 stitched 的全局 `test_active` 区间
   - 拼接各窗口已经算完的结果字段
   - 做一致性校验
7. 也正因为 stitched 不再关心预热问题，所以这里的算法可以显著简化。
8. stitched 当前这套“直接拼 `test_active`”算法，就是建立在上面这条 `step = test_active_bars` 的总前提之上。

## 9. stitched 算法

```rust
fn stitch_window_results(
    window_results: &[WindowArtifact],
    full_data: &DataPack,
    initial_capital: f64,
) -> StitchedArtifact
```

步骤：

1. stitched 发生在所有窗口都已经执行完成、`window_results` 已经完整产出之后。
2. 先从 `window_results` 里取：
   - `first_window = window_results.first()`
   - `last_window = window_results.last()`
3. 再确定 stitched 的全局 `test_active` 时间范围，并据此落成 `stitched_pack_time_range_from_active`：
   - `stitched_pack_time_range_from_active.start = first_window.meta.test_active_time_range.start`
   - `stitched_pack_time_range_from_active.end = last_window.meta.test_active_time_range.end`
4. 再直接从初始 `full_data` 切出 stitched DataPack 真值：
   - 这里明确复用前面 `## 4` 定义好的 `slice_data_pack_by_base_window(...)`
   - 先根据 `stitched_pack_time_range_from_active` 构造一个 stitched 专用的 `WindowSliceIndices`
   - 其中 `WindowSliceIndices` 的构造方式是：
     - `source_ranges`
       - 对 `data.base_data_key`：
         - 先取 `start_time = stitched_pack_time_range_from_active.start`
         - 再取 `end_time = stitched_pack_time_range_from_active.end`
         - 然后直接复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里定义的统一精确时间定位工具函数 `exact_index_by_time(...)`
         - 具体计算：
           - `base_start_idx = exact_index_by_time(full_data.mapping.time, start_time, "mapping.time")`
           - `base_end_idx = exact_index_by_time(full_data.mapping.time, end_time, "mapping.time")`
         - 最后构造半开区间：`source_ranges[data.base_data_key] = [base_start_idx, base_end_idx + 1)`
         - 这里必须是精确匹配，不允许模糊 asof；若任一时间在 `full_data.mapping.time` 中不存在，`exact_index_by_time(...)` 直接报错
       - 对每个非 base `k`：
         - 继续复用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里定义的统一时间投影工具函数
         - 先取：
           - `base_start_idx`
           - `base_end_exclusive_idx = base_end_idx + 1`
         - 再计算：
           - `src_start_idx = map_source_row_by_time(full_data.mapping.time[base_start_idx], full_data.source[k].time, k)`
           - `src_end_exclusive_idx = map_source_end_by_base_end(full_data.mapping.time, full_data.source[k].time, base_end_exclusive_idx, k)`
         - 最后构造：
           - `source_ranges[k] = [src_start_idx, src_end_exclusive_idx)`
         - 这里 stitched 不再补预热，所以 source 只要求覆盖 stitched 的全局 `test_active` 区间，不再额外向左补 `warmup`
     - `ranges_draft`
       - 对所有 `k` 都写成零预热：
       - `warmup_bars = 0`
       - `pack_bars = source_ranges[k].end - source_ranges[k].start`
       - `active_bars = pack_bars`
   - 然后显式调用：
     - `stitched_data = slice_data_pack_by_base_window(full_data, stitched_indices)`
   - 这里不是手工拼装 `DataPack`；`slice_data_pack_by_base_window(...)` 内部会按现成索引切 `source / skip_mask`，再正式调用 `build_data_pack(...)` 构建 stitched_data
5. 先对每个 `window_result` 提取 `test_active` 结果视图：
   - 当前 `window_result.test_pack_data / test_pack_result` 仍然包含测试预热
   - 因此 stitched 前，直接复用 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 里定义的 `extract_active(...)`
   - 对每个 `window_result` 执行：
      - `(_, test_active_result) = extract_active(window_result.test_pack_data, window_result.test_pack_result)`
    - 这里的 `test_active_data` 只是中间产物；第 5 步最终保留的是 `window_active_results: Vec<ResultPack>`，其中每个元素都是对应窗口的 `test_active_result`
6. 再按窗口顺序，对 `window_active_results` 分别做字段级拼接；这些字段全部拼完后，才合成为 stitched 中间结果 `stitched_result_draft`：
   - `indicators[k]`：
     - 对任意相邻窗口 `i, i+1`，先定义：
       - `current_end_time = window_active_results[i].indicators[k]["time"].last()`
       - `next_start_time = window_active_results[i + 1].indicators[k]["time"].first()`
     - 若 `next_start_time > current_end_time`，直接追加
     - 若 `next_start_time == current_end_time`，用后窗口覆盖前窗口
     - 若 `next_start_time < current_end_time`，直接报错
   - `signals / backtest`：
     - 它们都挂在 base 轴上，按 `window_active_results` 顺序直接拼
     - 对任意相邻窗口 `i, i+1`，先定义：
       - `current_end_time = window_active_results[i].mapping.time.last()`
       - `next_start_time = window_active_results[i + 1].mapping.time.first()`
     - 都必须满足：
       - `next_start_time > current_end_time`
     - 否则直接报错
   - `stitched_result_draft` 不持有 `mapping`
   - 上述字段全部拼完后，得到 `stitched_result_draft`
7. 先构建一个仅用于校验的 stitched 中间结果：

```text
stitched_result_pre_capital = build_result_pack(
    data        = stitched_data,
    indicators  = stitched_result_draft.indicators,
    signals     = stitched_result_draft.signals,
    backtest    = stitched_result_draft.backtest,
    performance = None,
)
```

8. 对这个 stitched 中间结果做一致性校验：
   - `stitched_result_pre_capital.mapping.time == stitched_data.mapping.time`
   - 若不一致，直接报错
   - 对每个 `k ∈ indicator_source_keys`：
     - `stitched_data.source[k].time == stitched_result_pre_capital.indicators[k]["time"]`
     - 若不一致，直接报错
   - 再对每个 `k ∈ indicator_source_keys` 做 mapping 语义校验：
     - 用 `stitched_data.mapping[k]` 投影 `stitched_data.source[k].time`
     - 用 `stitched_result_pre_capital.mapping[k]` 投影 `stitched_result_pre_capital.indicators[k]["time"]`
     - 两边投影得到的时间列必须完全一致
   - 不直接比较 `mapping` 的原始整数值
   - 原因是这里真正要校验的是映射语义，而不是局部索引值本身
9. 再重建 stitched 的全局资金列：
   - `stitched_result_pre_capital.backtest` 此时还只是把各窗口 `test_active_result.backtest` 顺序拼起来
   - 其中 `balance / equity / total_return_pct / fee_cum / current_drawdown` 这些资金列仍然是窗口局部口径，不能直接当作 stitched 全局资金轨迹
   - `trade_pnl_pct` 不在 stitched 资金列重建范围内：
     - 它保留窗口结果拼接后的原值
     - 只表示窗口局部的 bar 级事件输出
     - 不作为 stitched 全局资金轨迹真值的一部分
   - `fee` 也不在 stitched 资金列重建范围内：
      - 它同样保留窗口结果拼接后的原值
      - 只表示窗口局部的单 bar 手续费输出
      - 不作为 stitched 全局资金轨迹真值的一部分
   - 因此必须基于 `stitched_result_pre_capital.backtest` 重建出一份新的 `rebuilt_stitched_backtest`
   - 重建口径直接写死为“按局部资金列增长因子重放”。
   - 这里必须特别说明：**窗口边界不会重置 stitched 全局资金**。
   - 边界行把 `growth_bal = growth_eq = 1` 的真实含义是：
     - `balance[i] = balance[i - 1]`
     - `equity[i] = equity[i - 1]`
   - 也就是 stitched 全局资金在边界行**直接承接上一根**，而不是回到 `initial_capital`。
   - 这里不再用 `boundary_starts` 这种实现味太重的名字，而统一写成：
     - `window_start_rows_in_stitched_backtest`
   - 它表示：
     - 除第一个窗口外，每个后续窗口在 stitched `backtest` 中的首行行号

```text
# 输入
local_balance[i] = stitched_result_pre_capital.backtest.balance[i]
local_equity[i]  = stitched_result_pre_capital.backtest.equity[i]
local_fee[i]     = stitched_result_pre_capital.backtest.fee[i]
window_start_rows_in_stitched_backtest = 除第一个窗口外，每个后续窗口在 stitched backtest 里的首行行号

# 这里不把“资金归零”当成报错；`balance / equity == 0` 视为正常终止状态
# 窗口边界处，局部资金重置不传播成 stitched 全局资金重置
# 同一窗口内部的非边界行，局部资金增长因子仍然直接作用到 stitched 全局资金；若局部增长因子为 0，则 stitched 全局资金也同步乘以 0
# stitched 全局资金一旦归零，后续 stitched 全局资金都保持 0

# 初始化
balance[0]          = initial_capital
equity[0]           = initial_capital
total_return_pct[0] = 0
fee_cum[0]          = local_fee[0]
peak_equity         = initial_capital
current_drawdown[0] = 0

# 对每个 i >= 1
if i in window_start_rows_in_stitched_backtest:
    growth_bal = 1
    growth_eq  = 1
elif balance[i - 1] == 0 or equity[i - 1] == 0:
    growth_bal = 0
    growth_eq  = 0
elif local_balance[i - 1] == 0 or local_equity[i - 1] == 0:
    # 这里已经排除了窗口边界，因此这是同一窗口内部的非边界行
    # 若局部前一根资金已经归零，则当前局部资金也必须继续为 0；否则说明局部资金在同一窗口内部又从 0 恢复成正数，直接报错
    if local_balance[i] > 0 or local_equity[i] > 0:
        fail("stitched capital rebuild found positive local capital after local capital already reached zero on a non-boundary row")
    growth_bal = 0
    growth_eq  = 0
else:
    growth_bal = local_balance[i] / local_balance[i - 1]
    growth_eq  = local_equity[i] / local_equity[i - 1]

balance[i]          = balance[i - 1] * growth_bal
equity[i]           = equity[i - 1] * growth_eq
total_return_pct[i] = equity[i] / initial_capital - 1
fee_cum[i]          = fee_cum[i - 1] + local_fee[i]
peak_equity         = max(peak_equity, equity[i])
current_drawdown[i] = 1 - equity[i] / peak_equity
```

   - 这里在 `window_start_rows_in_stitched_backtest` 对应的边界行强制 `growth_bal = growth_eq = 1`
   - 目的是避免把“下一窗口局部资金列从其局部起点重新展开”误判成 stitched 全局的真实回撤或跳变
10. 再重算 stitched performance：
   - 绩效函数直接接受完整 `stitched_data` 和 `rebuilt_stitched_backtest`
   - 再由绩效模块内部根据 `stitched_data.ranges[data.base_data_key].warmup_bars` 只统计 stitched 的非预热有效段
   - 计算得到：`stitched_performance`
11. 最后再一次性构建最终 stitched 结果：

```text
stitched_result = build_result_pack(
    data        = stitched_data,
    indicators  = stitched_result_draft.indicators,
    signals     = stitched_result_draft.signals,
    backtest    = rebuilt_stitched_backtest,
    performance = stitched_performance,
)
```

   - 这里不再出现“先构建 stitched_result，再替换其 backtest / performance 字段”的过程
   - 调用方最终拿到的 `stitched_result.backtest` 与 `stitched_result.performance` 必须天然属于同一套 stitched 全局口径

## 10. stitched 为什么不直接拼窗口 DataPack

因为大周期 source 在相邻 `test_active` 窗口边界处很可能共享同一根 bar。

如果直接把窗口级 `DataPack` 当真值去拼：

1. base 轴虽然通常没重叠
2. 但 source 轴很容易在 `test_active` 边界重复
3. 这时“拼接”已经变成了“去重 + 决议”

因此本方案改成：

1. stitched DataPack 直接以初始 `full_data` 切片为真值
2. 各窗口 `test_pack_result` 只负责拼出 stitched 结果字段
3. `mapping.time` 必须和 `stitched_data.mapping.time` 完全一致
4. 这样既能验证窗口结果拼接过程，又不让 `stitched_data` 真值依赖边界覆盖规则
