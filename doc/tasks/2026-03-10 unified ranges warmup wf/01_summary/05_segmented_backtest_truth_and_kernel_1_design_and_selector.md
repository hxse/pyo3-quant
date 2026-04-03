# 分段真值回测、可变 ATR 与对现有主循环的精准抽象

## 0. 本篇归属与边界

| 本篇新增 | 本篇不新增 |
| --- | --- |
| 分段真值 stitched backtest 的目标口径 | planner 新规则 |
| `run_backtest_with_schedule(...)` 与通用 kernel | `01` 已定义的 warmup 三层口径 |
| 在复用 `04` 注入后信号前提下的 replay 边界 | `04` 已有的窗口规划、跨窗注入与窗口结果阶段契约 |
| `BacktestParamSegment` 与 `ParamsSelector` | 指标层或信号层的“全局按段运行”改造 |

因此本篇是一次很窄的增量改造：

1. 指标按窗口算。
2. 信号按窗口算。
3. `04` stitched 阶段把窗口级指标和窗口级 active 信号序列收成 `StitchedReplayInput`。
4. backtest 真值由 `StitchedReplayInput` 驱动的一次性连续执行得到。

本篇把一份已经通过 schedule 验证、并已经绑定 selector / schema contract 的 replay 计划，统一按对象视角称为 `ResolvedRegimePlan`。

`ResolvedRegimePlan` 只承接：

1. `BacktestParamSegment`
2. contiguity
3. schedule policy
4. output schema
5. `ParamsSelector` 的构造前提

`ResolvedRegimePlan` 不承接：

1. stitched 指标拼接
2. `stitched_atr_by_row` 的物化算法
3. kernel 内部执行细节

这里的 `ResolvedRegimePlan` 是本篇的概念对象，不要求等于单一 Rust 公共结构体；它只负责把 `05` 已经拥有的 schedule 真值与 contract 收在同一层解释。

## 1. 要解决的核心问题

当前 stitched backtest 的正式目标是：**让最终 backtest 真值沿 stitched 连续时间轴一次性生成**。

因此本篇直接采用下面这条正式路径：

1. 先准备 stitched 阶段真正需要的输入真值。
2. 再把这些输入真值喂给回测引擎。
3. 让回测引擎沿连续时间轴直接执行出最终 backtest。

正式 stitched backtest 真值只走 segmented replay 这条链，不走重建资金列路径。

本篇口径在这里一并写死：

1. stitched 正式信号语义与 `04` 的窗口正式 WF 语义保持一致。
2. 本篇目标是：**得到与 `04` 当前正式 WF 语义一致的一次性连续重放结果**。
3. 正式 stitched replay 输入统一由 `StitchedReplayInput` 承接。
4. 其中正式 stitched 输入信号直接使用各窗口 `test_active_result.signals`，也就是窗口 `final_signals` 的 active-only 可见部分。
5. 当前正式语义接受一条保守约束：
   - 跨窗 carry 开仓写在 active 第一根
   - 因而真正的继承开仓会延后一根 active bar 执行

## 2. 整体方案总览

新方案的总流程如下：

```text
1. 每个窗口独立完成：
   - 指标计算
   - 信号生成
   - 优化/选参与窗口级结果构建

2. stitched 阶段直接构造 `StitchedReplayInput`。

3. `StitchedReplayInput` 统一包含：
   - stitched_data
   - stitched_signals
   - backtest_schedule: Vec<BacktestParamSegment>
   - stitched_atr_by_row
   - stitched_indicators_with_time

4. 若 schedule 中存在 ATR 相关参数：
   - `StitchedReplayInput.stitched_atr_by_row` 必须存在
   - 它的唯一正式物化算法统一引用 `04`：
     - 先按 unique `resolved_atr_period` 计算全量 ATR cache
     - 再按 `backtest_schedule` 做 segment 级 slice + concat
   - 若当前 stitched backtest 全程不启用 ATR 相关逻辑，则该输入为 `None`

5. 调用：
   run_backtest_with_schedule(
       data = stitched_replay_input.stitched_data,
       signals = stitched_replay_input.stitched_signals,
       atr_by_row = stitched_replay_input.stitched_atr_by_row,
       schedule = stitched_replay_input.backtest_schedule,
   )

6. 得到一份一次性连续执行出来的 stitched_backtest_truth

7. `stitched_raw_indicators =
      strip_indicator_time_columns(stitched_replay_input.stitched_indicators_with_time)`

8. 再基于：
   - `stitched_replay_input.stitched_data`
   - `stitched_raw_indicators`
   - `stitched_replay_input.stitched_signals`
   - `stitched_backtest_truth`
   - `stitched_performance`
统一调用 `build_result_pack(...)`，生成最终 stitched `ResultPack`
```

这里的 `StitchedReplayInput` 是 `04 -> 05` 的正式边界对象：

1. 它只收纳 `04` stitched 阶段已经产出的正式输入真值。
2. replay 直接消费：
   - `stitched_data`
   - `stitched_signals`
   - `backtest_schedule`
   - `stitched_atr_by_row`
3. 最终 `StitchedArtifact.result` 构建阶段再消费：
   - `stitched_indicators_with_time`
4. 它不是阶段名，也不是第二套 stitched 解释层。

这里的关键转变只有一条：

1. stitched 正式 backtest 真值来源是 segmented replay。
2. stitched replay 的正式输入信号是窗口级 `test_active_result.signals`。

## 3. 什么变，什么不变

### 3.1 不变的部分

这些内容不需要动：

1. fetch planner 的初始取数逻辑。
2. `W_resolved / W_normalized / W_applied` 及其 shared helper。
3. `build_window_indices(...)` 的窗口规划逻辑。
4. 每个窗口内部的指标计算。
5. 每个窗口内部的信号生成。
6. 每个窗口内部的优化与窗口级 `ResultPack`。
7. `build_result_pack(...)` 的容器构建语义。

### 3.2 真正变化的部分

本篇涉及 stitched 输入边界时，统一引用 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 里的“stitched 单一事实块”；这里只写 `05` 对这些正式输入的消费结论。

真正变化的只在 stitched 末段：

1. stitched 阶段产出：
   - 全局 `signals`（直接拼接各窗口 `test_active_result.signals`）
   - 全局 `atr_by_row`
   - 全局 `BacktestParams schedule`
   - 全局 `stitched_indicators_with_time`
2. 调用一次连续回测入口，得到 `stitched_backtest_truth`。
3. 先把 `stitched_indicators_with_time` 统一降级成 `stitched_raw_indicators`。
4. 再基于 `stitched_data + stitched_backtest_truth` 计算 stitched `performance`。
5. 最后统一通过 `build_result_pack(...)` 构建最终 stitched `ResultPack`。

### 3.3 stitched indicators 的地位

`run_backtest_with_schedule(...)` 真正必须消费的是：

1. `stitched_signals`
2. `stitched_atr_by_row`
3. `backtest_schedule`

因此，`stitched_indicators_with_time` 不是 replay 的硬前置条件，但属于最终 `StitchedArtifact.result` 指标字段的正式中间产物，不能省略。

它按 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 的 stitched 规则生成；正式 stitched backtest 的计算不依赖它本身。

同时总契约必须保持和 [03_backtest_and_result_pack.md](./03_backtest_and_result_pack.md) 一致：

1. `stitched_indicators_with_time` 是结果态 indicators，带 `time` 列。
2. 最终 stitched `ResultPack` 统一走 `build_result_pack(...)`。
3. 因此在最终构建 stitched `ResultPack` 前，必须先：
   - `strip_indicator_time_columns(stitched_indicators_with_time)`
   - 得到 `stitched_raw_indicators`
4. 再把 `stitched_raw_indicators` 喂给 `build_result_pack(...)`。

## 4. 核心设计：不是“另起引擎”，而是“把现有主循环抽成通用 kernel”

本篇最核心的设计判断是：重点不是多一个 `run_backtest_with_schedule(...)` 接口，而是**把 backtest 内部执行核改造成一套通用 kernel**。这一步的目标不是重写引擎，而是把现有主循环里已经稳定的执行逻辑抽成统一执行核。

也就是说，设计应该是：

1. 对外保留两个入口：
   - `run_backtest(...)`
   - `run_backtest_with_schedule(...)`
2. 对内统一成一个 kernel：
   - 单次回测入口把“单一参数 + 单一 ATR 序列”喂进去。
   - 分段回测入口把“schedule 参数 + stitched ATR 序列”喂进去。
3. 主循环、状态推进、风控检查、资金结算、输出写入，都尽量只保留一套实现。
4. 在单次回测路径下，这个 kernel 的行为应与现有 `run_backtest(...)` 主循环保持语义等价，而不是借重构之名顺手改掉原有回测规则。

否则最容易退化成“单次一套循环、分段一套循环”，后续每次修 bug、补列、改风控都要改两份，很容易漂。

因此本篇明确把设计重心定成：

1. **两套外部入口**
2. **一套内部 kernel**

## 5. 边界语义的正式口径

本篇只采用一条边界语义：

1. `04` 在窗口边界显式写入跨窗注入与窗口尾部强平信号。
2. `05` stitched replay 直接消费各窗口 `test_active_result.signals`。
3. 因此窗口边界上的“平仓再开仓”在信号层已经写死，不再依赖回测 kernel 内部补状态或额外推断。

这条正式口径带来的结果也一并写死：

1. `05` 只对已经注入完成的 stitched 信号流做一次性连续回放。
2. `exit_in_bar / next-bar`、`TSL_PCT / TSL_ATR / PSAR` 等边界行为都统一建立在这条 stitched 信号语义上。
3. `04` 的窗口正式返回与 `05` 的 stitched 回放使用同一份信号语义。
4. 这条边界语义也直接对应实盘换参时“先平再开”的可执行流程。

## 6. 为什么 `atr_period` 可以允许变化

在只看当前代码结构时，最容易产生一个误解：

1. 现在引擎里 `CurrentBarData` 只有一个 `atr`。
2. `PreparedData` 里也只有一条 `atr` 序列。
3. 所以似乎只要允许 `atr_period` 变化，整个回测引擎就必须大改。

本篇认为这个结论不成立。

真正需要改的不是“主循环突然懂多种 ATR”，而是：

1. 主循环只消费一条已经对齐到 stitched 行轴的 `atr_by_row`。

### 6.1 本方案里 ATR 的正式定位

本方案把 ATR 的地位定义成：

1. ATR 不是 schedule 回测 kernel 内部现算的隐藏衍生物。
2. ATR 是 schedule 回测 kernel 的正式输入之一。
3. 它和 `signals` 一样，都是一条已经按 stitched 行轴对齐好的外部输入序列。

因此：

1. 单次回测入口：
   - 先根据一套固定 `BacktestParams` 生成 ATR 序列
   - 再把这条 ATR 序列交给通用 kernel
2. 分段回测入口：
   - 先根据 stitched 行轴和 `schedule` 生成 `atr_by_row`
   - 再把这条 `atr_by_row` 交给同一个 kernel

### 6.2 为什么这能支持 `atr_period` 可变

因为 kernel 的职责已经被收紧成：

1. 我只消费 `atr_by_row[i]`
2. 我不关心它是怎么来的

只要调用方能保证：

1. `atr_by_row` 长度和 stitched base 轴完全一致
2. `atr_by_row[i]` 的值已经按本任务定义的 schedule 语义物化完成

那么 kernel 就不需要再知道：

1. `atr_period` 是不是全局固定
2. 外层是如何组织 ATR cache 的具体实现细节

本篇因此明确支持：

1. `atr_period` 可以随 segment 变化。
2. 变化后的 ATR 解释直接建立在 stitched_signals 这条正式输入上。

### 6.3 为什么不要求对 `prev_bar.atr` 做特殊边界修补

因为在这版方案里，跨窗语义已经由注入后的 `stitched_signals` 先写死了，首段执行预热也已经前移到 `04` 的 `stitched_atr_by_row` 物化阶段，`prev_bar.atr` 只剩下“上一行历史输入”这一个角色：

1. 它都是“上一行已经物化好的历史输入”。
2. 当前 bar 只负责读取它，不负责改写它。
3. `05` 的职责中不包含窗口边界专属的 ATR 状态延续规则。
4. 也就是说，`05` 不做首段 ATR 修补的前提是：
   - `04` 不能在 active-only `stitched_data.base` 上直接现算 ATR
   - 而必须先基于 `full_data.base` 左侧已有上下文物化 `stitched_atr_by_row`

当前再补一条边界：

1. `W_backtest_exec_base` 在窗口公式里同时覆盖 ATR 与 PSAR。
2. stitched replay 里，外层需要显式物化的执行预热输入只有 ATR。
3. 当前 `TSL_PSAR` 不额外引入 stitched 首段专属补丁：
   - 现有主循环固定先初始化第 `0/1` 行，再从第 `2` 行开始真正执行
   - 本任务已经把 `test_active >= 3` 写成最小合法长度
   - 当前 `psar_required_warmup_bars() = 2`
4. 因而在当前主循环约束下，PSAR 初始化所需的局部历史已经由 stitched active 轴自身满足。

所以本篇的正式结论是：

1. `atr_period` 可变没有原则性障碍。
2. 不需要为 `prev_bar.atr` 单独发明例外规则。
3. stitched replay 只需要消费已经物化好的 `atr_by_row` 即可。

## 7. 统一参数选择器

```rust
struct BacktestParamSegment {
    start_row: usize, // inclusive
    end_row: usize,   // exclusive
    params: BacktestParams,
}

struct ParamsSelector {
    schedule: &[BacktestParamSegment],
    segment_idx: usize,
}

fn build_schedule_params_selector(
    schedule: &[BacktestParamSegment],
) -> ParamsSelector

fn select_params_for_row(
    selector: &mut ParamsSelector,
    row_idx: usize,
) -> &BacktestParams
```

这里先把内部参数读取层定义清楚，再往下谈 kernel 和入口。

`BacktestParamSegment` 放在这里，而不是后面入口章节，原因很简单：

1. `ParamsSelector` 直接依赖它。
2. `build_schedule_params_selector(...)` 也直接消费它。
3. 所以在阅读顺序上，应先把 selector 所依赖的输入对象交代清楚，再往下谈 kernel 和入口。

这里还要把边界写死：

1. `BacktestParamSegment.start_row / end_row` 的正式构造算法归 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md)。
2. 本篇直接消费 `04` 已写死的重基结果：
   - 先读取各窗口 `test_active_base_row_range`
   - 再以第一窗 `test_active_base_row_range.start` 为基准做减法重基
   - 得到 stitched 绝对行轴上的半开区间 `[start_row, end_row)`
3. 因而 `05` 只负责：
   - 消费 `BacktestParamSegment`
   - 校验 contiguity
   - 在 kernel 内按 row 选择当前参数

语义：

1. 正式设计如下：
   - kernel 只认一个统一的 `ParamsSelector`
   - 它永远按 `schedule + segment_idx` 工作
3. 入口层负责先把单参数或多参数都收敛成 `schedule`，再构造交给 kernel 消费的只读参数选择器。
4. 它的目标只有一个：
   - 对任意 `row_idx`
   - 返回当前这一行应当使用的 `&BacktestParams`
5. `build_schedule_params_selector(...)`
   - 用于 schedule 路径
   - 返回的选择器按 `row_idx` 落到对应 segment，再返回该 segment 的 `&BacktestParams`
   - 这里的 “schedule 路径” 同时覆盖：
     - 单参数入口内部构造出的单段 schedule
     - 多段 stitched replay schedule
6. `select_params_for_row(...)`
   - 是 kernel 唯一允许调用的取参入口
   - 单参数与多段 schedule 最终都必须走它
7. 本篇明确不采用“单参数路径完全绕开选择器”的写法。
   - 因为那样 kernel 内部就会重新出现两套参数读取路径
   - 等价性审阅也会变得更难
8. 本篇同样不采用“把两个公开入口合并成一个”的写法。
   - 因为单参数与 schedule 的外层输入契约本来就不同
   - 强行合并只会把 API 边界变脏
   - 因此最佳结构是：两个外部入口保留，一个内部 `ParamsSelector` 统一收口

工具函数步骤：

1. `build_schedule_params_selector(schedule)`
   - 第一步：接收外层已经完成连续覆盖校验、policy 校验、单参数校验的 `schedule`
   - 第二步：把 `segment_idx` 初始化为 `0`
   - 第三步：构造 `ParamsSelector { schedule, segment_idx: 0 }`
   - 第四步：返回该 selector
   - 这一步同样不展开成按 row 的参数数组，只保留对 segment 列表的借用
2. `select_params_for_row(selector, row_idx)`
   - 从当前 `segment_idx` 开始检查当前 row 是否已经越过当前 segment 的 `end_row`
   - 若已越过，则把 `segment_idx` 向后推进
   - 推进结束后，检查当前 `segment_idx` 是否满足：
     `schedule[segment_idx].start_row <= row_idx < schedule[segment_idx].end_row`
   - 若满足，则返回当前 `segment_idx` 对应 segment 的 `&BacktestParams`
   - 若不满足，则直接报错，不允许静默沿用上一段或最后一段
   - 在当前 kernel 约束下，`row_idx` 是单调递增的，因此 `segment_idx` 也应当只增不减

上面的步骤已经是本节唯一的正式算法描述。下面只补一个实现结论：

1. selector 不会回头查更早的 segment。
2. `segment_idx` 只会向前推进。
3. 因而每 row 的取参成本是轻量的，不需要每次从头扫描整张 schedule。

边界：

1. `ParamsSelector` 本身不持有按 row 展开的参数副本，只允许借用既有 `BacktestParams`。
2. `select_params_for_row(...)` 只返回参数引用，不允许在执行期间按 row 新建 `BacktestParams` 对象。
3. `BacktestParams` 在回测模块执行过程中按当前 Rust 签名始终以 `&BacktestParams` 形式传递，因此这里是语法层面的只读选择，不是语义层面的“约定不改”。
4. `build_schedule_params_selector(...)` 最合理的实现不是“每个 row 重查整张 schedule”，而是：
   - 预先持有最少量的 segment 参数对象
   - 用一个 `segment_idx` 只在跨 segment 边界时推进一次
5. `ParamsSelector` 只负责回答“当前 row 用哪套参数”，不负责：
   - 参数合法性校验
   - ATR 生成
   - output schema 决策
6. 入口层负责构造 selector 并保证它覆盖完整行空间。
7. kernel 只消费 `select_params_for_row(...)` 的结果，不反向关心当前是单段 schedule 还是多段 schedule。
8. `build_schedule_params_selector(...)` 不负责补救脏 schedule。
   - 如果 `schedule` 为空、未覆盖完整行空间、存在 gap 或 overlap，这些都应在外层校验阶段直接报错
   - 这里不做任何自动修正或隐式兜底
9. `select_params_for_row(...)` 也不允许“越界后凑合返回最后一段”或“遇到空洞就沿用上一段”。
   - 若实际实现里发现 `row_idx` 找不到合法 segment，应直接 fail-fast
   - 摘要伪签名没有展开 `Result`，只是为了保持主干简洁；真正实现不能静默兜底
