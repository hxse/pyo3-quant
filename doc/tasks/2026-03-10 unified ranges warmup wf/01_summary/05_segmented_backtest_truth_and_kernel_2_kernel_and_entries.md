# 分段真值回测、可变 ATR 与对现有主循环的精准抽象（二）kernel 与入口调用链

## 8. 通用 kernel 的职责

这里的“通用 kernel”，可以直接理解成：

1. 把现有主循环函数抽成一个更通用的统一执行核。
2. 它是一次精准改造，不是再造一套新的回测引擎。
3. 对单次回测来说，它应当与现有执行逻辑保持等价；对 schedule 回测来说，只是把参数来源和 ATR 输入改成了按 stitched 轴提供。

这里还要再补一条和第 `7` 节对应的硬约束：

1. 不只是 `run_backtest(...)` 这条外层入口要和原有流程保持等价，抽出来的 kernel 内部流程本身也要和当前主循环保持等价。
2. 也就是说，不能只保证“输入输出差不多”，却把主循环内部的初始化顺序、状态推进顺序、输出写入顺序悄悄改掉。
3. 因而 kernel 的内部流程等价性，也属于本次重构的重点审阅项。

通用 kernel 只做四件事：

1. 接收已经准备好的 stitched 行轴输入。
2. 逐 bar 获取当前执行参数。
3. 复用现有状态机推进：
   - 仓位逻辑
   - 风控逻辑
   - 资金逻辑
   - 输出写入
4. 生成一张完整 backtest 表。

换句话说，kernel 不再负责：

1. 解释窗口来源。
2. 解释 warmup。
3. 解释 stitched 去重。
4. 解释 ATR 是如何生成的。
5. 解释为什么当前 row 属于哪一段。

这些都属于外层准备阶段。

### 8.1 kernel 伪签名

```rust
fn run_backtest_kernel(
    prepared_data: PreparedData,
    mut params_selector: ParamsSelector,
    output_schema: OutputSchema,
) -> Result<OutputBuffers, BacktestError>
```

这里的签名仍按摘要伪代码理解：

1. 不要求和最终 Rust 可编译签名逐字符一致。
2. 重点只在说明 kernel 真正接收的对象层级。
3. 也就是说，kernel 接收的是“已经准备好的 `PreparedData`”，而不是再自己去理解 `data / signals / atr_by_row / schedule` 这些外层对象。
4. 这里的 `ParamsSelector` 是入口层先构造好的统一参数选择器。
5. kernel 内部只允许通过 `select_params_for_row(...)` 取参：
   - 单参数路径始终返回同一份 `&BacktestParams`
   - schedule 路径只在 segment 边界推进游标，并返回当前 segment 的 `&BacktestParams`
6. 这样做的目标就是：在保持语义清楚的同时，保证参数读取层的性能最优、内存最少，避免每个 row 新建 `BacktestParams` 对象。
7. 为了和当前 `run_main_loop(...)` 保持等价，kernel 内部仍要保留三步初始化，只是输入来源写死为：
   - `BacktestState::new(...)`
     - 单参数路径：继续吃这唯一一份 `params`
     - schedule 路径：直接吃 `select_params_for_row(&mut params_selector, 0)` 返回的那一段 params
     - 这里依赖第 `9.6` 节已写死的约束：`initial_capital` 不允许跨 segment 变化
   - `OutputBuffers`
     - 单参数路径：继续等价于 `OutputBuffers::new(params, data_length)`
     - schedule 路径：由并集 `output_schema` 显式落定
   - `WriteConfig`
     - 单参数路径：继续等价于 `WriteConfig::from_params(params)`
     - schedule 路径：由同一份并集 `output_schema` 显式落定
8. 也就是说，schedule 路径不是把这三步删掉，而是把“它们各自吃什么输入”单独写死，避免实现时静默漂移。

### 8.2 kernel 伪代码

```text
run_backtest_kernel(prepared_data, mut params_selector, output_schema):
    1. let data_length = prepared_data.time.len()

    2. 校验 kernel 输入契约
       - 校验 `prepared_data` 已经由外层 `PreparedData::new(...)` 按当前语义构造完成
       - 校验 `params_selector` 覆盖完整 `[0, data_length)` 行空间
       - 校验 `output_schema` 与 `params_selector` 的列启用契约一致

    3. 确定初始化参数 `init_params`
       - 直接调用：
         `let init_params = select_params_for_row(&mut params_selector, 0)`
       - 也就是说，初始化阶段和主循环阶段共用同一条正式取参路径

    4. 初始化输出缓冲区
       - 单参数路径：
         `let mut buffers = OutputBuffers::new(init_params, data_length)`
       - schedule 路径：
         `let mut buffers = OutputBuffers::from_schema(&output_schema, data_length)`
         或其他等价 helper

    5. 初始化回测状态
       - `let mut state = BacktestState::new(init_params, &prepared_data)`

    6. 初始化写入配置
       - 单参数路径：
         `let config = WriteConfig::from_params(init_params)`
       - schedule 路径：
         `let config = WriteConfig::from_output_schema(&output_schema)`
         或其他等价 helper

    7. 初始化第 0 行和第 1 行
       - `initialize_buffer_rows_0_and_1(&mut buffers, &mut state, &prepared_data, &config)`

    8. 若 `data_length <= 2`
       - `return Ok(buffers)`

    9. 初始化主循环迭代器
       - `let mut buf_iter = OutputBuffersIter::new(&mut buffers, 2)`
       - `let mut data_iter = PreparedDataIter::new(&prepared_data, 2)`

   10. 进入主循环
       - `while let (Some(mut row), Some((index, current_bar))) = (buf_iter.next(), data_iter.next())`
         1. `let current_params = select_params_for_row(&mut params_selector, index)`
         2. `state.current_index = index`
         3. `state.prev_bar = state.current_bar`
         4. `state.current_bar = current_bar`
         5. `state.calculate_position(current_params)`
         6. `state.calculate_capital(current_params)`
         7. `row.write(&state, &config)`

   11. 返回
       - `return Ok(buffers)`
```

这段伪代码有两个刻意写死的约束：

1. 它必须和当前 `run_main_loop(...)` 的初始化顺序、循环顺序、写入顺序保持等价。
2. schedule 路径允许变化的，只有：
   - `current_params` 的来源
   - `atr_by_row` 的外层来源
   - `OutputBuffers / WriteConfig` 的 schema 落定方式
3. 其余状态推进语义不得借重构之名悄悄改写。

### 8.3 为什么主循环应该改成通用版本

因为 schedule 回测和单次回测真正不同的只有两样：

1. 当前 row 的 `params` 来自哪里。
2. 当前 row 的 `atr_by_row` 来自哪里。

其余逻辑本质完全相同：

1. 都是同一套持仓状态机。
2. 都是同一套风险阈值更新。
3. 都是同一套资金结算。
4. 都是同一套输出写入。

因此最好的写法不是：

1. 现有主循环保留一份。
2. 再给 schedule 单独复制一份。

而是：

1. 把主循环抽成更通用的版本。
2. 单次回测入口和 schedule 回测入口只负责准备不同的 selector 模式 / 输入序列。
3. 也就是说，改造点集中在“输入如何喂给主循环”，而不是改写主循环内部的仓位、风控、资金结算语义。
4. 这样做的直接好处是：改造范围小、与现有逻辑等价性更强、后续也更容易审阅和验证。

## 9. 对外入口与调用链

### 9.1 对外接口

对外保留两个入口，不合并成一个总入口：

```rust
fn run_backtest(
    data: &DataPack,
    signals: &DataFrame,
    params: &BacktestParams,
) -> Result<DataFrame, QuantError>

fn run_backtest_with_schedule(
    data: &DataPack,
    signals: &DataFrame,
    atr_by_row: Option<&Series>,
    schedule: &[BacktestParamSegment],
) -> Result<DataFrame, QuantError>
```

这里的签名仍按摘要伪代码理解：

1. 不要求和最终 Rust 真实签名逐字符一致。
2. 重点只在说明对象来源、阶段顺序和契约。
3. 本篇明确不把这两个入口再合并成一个：
   - `run_backtest(...)` 表达“单参数标准回测”
   - `run_backtest_with_schedule(...)` 表达“分段参数 stitched replay”
4. 两者的外部输入契约并不相同，强行合并只会把公开 API 搞得更混乱。
5. 本篇真正追求统一的，是内部执行核和参数选择方式，而不是把外部入口也揉成一个。

### 9.2 两个入口如何共同调用同一个 kernel

这里必须再写死一层：

1. `run_backtest(...)` 对外接口保留不变，但内部也要改。
2. 本篇现在明确选择最直接的收敛方式：
   - `run_backtest(...)` 在内部构造单段 `schedule`
   - 然后直接调用 `run_backtest_with_schedule(...)`
3. 也就是说，这次不是“新增 schedule 入口 + 旧入口完全不动”，而是“保留两个外部入口，但把 schedule 路径明确收敛成内部 canonical path”。

两条入口的内部流程应直接写成下面这种伪代码调用流：

```text
run_backtest(data, signals, params):
    1. `params.validate()`
    2. `let ohlcv = get_ohlcv_dataframe(data)`
    3. `let atr_by_row = calculate_atr_if_needed(ohlcv, params)`
       - 这里继续沿用当前实现：ATR 一致性校验内聚在 `calculate_atr_if_needed(...)` 内部
    4. `let data_length = data.mapping.height()`
    5. `let single_segment_schedule = [BacktestParamSegment { start_row: 0, end_row: data_length, params }]`
       - 摘要里这里按逻辑伪代码理解
       - 不要求展开最终 Rust 借用 / clone 细节
    6. `return run_backtest_with_schedule(data, signals, atr_by_row.as_ref(), &single_segment_schedule)`

run_backtest_with_schedule(data, signals, atr_by_row, schedule):
    1. `validate_schedule_contiguity(schedule, data.mapping.height())`
    2. `for segment in schedule { segment.params.validate()? }`
    3. `validate_backtest_param_schedule_policy(schedule)`
    4. `let has_any_schedule_atr_param = validate_schedule_atr_contract(schedule, atr_by_row, data.mapping.height())`
       - 对每个 `segment.params` 复用 `validate_atr_consistency()`
       - 把每段返回的 bool 聚合成整体 `has_any_schedule_atr_param`
       - 若整体需要 ATR，则 `atr_by_row` 必须是 `Some(...)`
       - 若整体不需要 ATR，则 `atr_by_row` 必须是 `None`
       - 若 `atr_by_row.is_some()`，则其长度必须严格等于 `data.mapping.height()`
    5. `let prepared_data = PreparedData::new(data, signals.clone(), &atr_by_row)`
    6. `let params_selector = build_schedule_params_selector(schedule)`
    7. `let output_schema = build_schedule_output_schema(schedule)`
    8. `let output_buffers = run_backtest_kernel(prepared_data, params_selector, output_schema)`
    9. `output_buffers.validate_array_lengths()`
   10. `let mut result_df = output_buffers.to_dataframe()`
   11. `if let Ok(col) = signals.column("has_leading_nan") { result_df.with_column(col.clone())? }`
   12. `return Ok(result_df)`
```

这里的结论要非常明确：

1. `run_backtest(...)` 也属于这次改造范围。
2. 但它不再独占一套入口内部流程，而是把“固定参数 + 单条 ATR 输入”先降成“单段 schedule + 单条 ATR 输入”，再直接调用 `run_backtest_with_schedule(...)`。
3. 因此 schedule 路径是内部 canonical path；单次回测只是它的一个特例。
4. `BacktestParams` 在回测模块执行过程中，按当前 Rust 签名设计始终以 `&BacktestParams` 形式传递，属于语法层面的只读输入，不是仅靠语义约定“不修改”。
5. 两条入口在“构造 PreparedData”这一步，都必须保留当前 `PreparedData::new(...)` 已有的信号预处理语义：
   - 冲突信号消解
   - `skip_mask` 屏蔽
   - ATR 为 `NaN` 时的进场屏蔽
   - `has_leading_nan` 屏蔽进场
6. 两条入口虽然保留，但内部参数读取路径要统一：
   - `run_backtest_with_schedule(...)` 继续负责构造统一的 `ParamsSelector`
   - kernel 只通过 `select_params_for_row(...)` 读取 `current_params`
   - 不允许单参数路径和 schedule 路径在 kernel 内再保留两套不同取参写法
7. 按本篇约束实现后，`run_backtest(...)` 理应与原有的 `run_backtest(...)` 逻辑等价；真正新增的差异只应出现在多段 schedule 场景。

### 9.2.1 等价性审阅重点

这里再把审阅重点写死：

1. 本篇最需要重点审阅的，不是 schedule 路径“能不能跑通”，而是单次回测路径在重构后是否仍与原有流程语义等价。
2. 也就是说，`run_backtest(...)` 这条老路径不能因为抽出通用 kernel，就悄悄改变现有行为。
3. 若实现阶段必须在“kernel 抽象更漂亮”和“单次回测保持等价”之间取舍，应优先保证后者。
4. 人工审阅时，至少要重点核对这几项：
   - 参数校验顺序是否仍与当前单次回测一致
   - ATR 相关 helper 的调用顺序与内聚边界是否仍一致
   - `PreparedData::new(...)` 的信号预处理语义是否完整保留
   - 是否仍先初始化第 `0 / 1` 行，再从第 `2` 行开始主循环
   - 单参数路径的输出 schema、列顺序、dtype 与 `has_leading_nan` 透传是否仍一致
5. 实现阶段还要再加一条方法论约束：
   - 必须同时对照本篇摘要文档和当前回测源码一起实现
   - 不能只看摘要文档写代码
   - 也不能只看当前源码重构
6. 原因很直接：
   - 若只看摘要文档写，很容易在局部调用顺序、初始化细节、输出 schema 上和当前源码不等价
   - 若只看当前源码写，又很容易在 selector / kernel / schedule 这层分工上偏离本篇方案
7. 因而这次重构的正确姿势是：
   - 用摘要文档约束目标结构与责任边界
   - 用当前源码校对调用顺序、初始化细节与等价行为

### 9.3 为什么 `run_backtest_with_schedule(...)` 直接吃 `atr_by_row`

本篇明确认为，这是自然且正确的。

原因有三条：

1. 这样可以直接支持 `atr_period` 可变。
2. 这样可以把“ATR 如何物化”的复杂度放在外层，而不是污染回测状态机。
3. 这样单次回测和 schedule 回测都能复用同一个 kernel。
4. 若当前 stitched backtest 全程不启用 ATR 相关逻辑，则直接传 `None` 即可。

这里还要把一个容易混淆的点先说清楚：

1. 单次路径里，ATR 是在入口内部现算的：
   - 先做 `params.validate_atr_consistency()`
   - 得到 `has_atr_params: bool`
   - 再由 `calculate_atr_if_needed(...)` 根据这个 bool 分支决定返回 `Some(atr_series)` 还是 `None`
2. schedule 路径里，ATR 已经是外层传进来的正式输入：
   - 因此这里不再内部计算 ATR
   - 只需要聚合“整个 schedule 是否需要 ATR”的 bool，并校验 `atr_by_row` 的 `Some / None` 形态是否匹配
3. 也就是说，schedule 路径对应的是：
   - “复用 `validate_atr_consistency()` 的 bool 语义”
   - 但不复用“在入口内部现算 ATR”这一步

因此，本篇把 schedule 路径的 helper 明确写成：

```rust
fn validate_schedule_atr_contract(
    schedule: &[BacktestParamSegment],
    atr_by_row: Option<&Series>,
    data_length: usize,
) -> Result<bool, QuantError>
```

它的职责是：

1. 对每个 `segment.params` 调用 `validate_atr_consistency()`
2. 把每段返回的 bool 做 OR 聚合，得到：
   - `has_any_schedule_atr_param`
3. 若 `has_any_schedule_atr_param == true`
   - 则 `atr_by_row` 必须是 `Some(...)`
4. 若 `has_any_schedule_atr_param == false`
   - 则 `atr_by_row` 必须是 `None`
5. 若 `atr_by_row.is_some()`
   - 则其长度必须严格等于 `data_length`
6. 全部通过后，返回 `has_any_schedule_atr_param`

这里还要补一条硬约束：

1. `stitched_atr_by_row` 不能只在外层“拼出来就算完”，也不能只靠 kernel 被动相信输入。
2. 它必须做**双层校验**：
   - 外层做语义校验
   - kernel 做输入契约校验
3. 但两边不能重复做同一件事，更不能让 kernel 反向重算 ATR 去验证外层是否拼对。

更具体地说：

1. 外层必须校验：
   - 若全程不启用 ATR 相关逻辑，则 `stitched_atr_by_row = None`
   - 若任一 segment 启用 ATR 相关逻辑，则必须显式产出 `stitched_atr_by_row`
   - `stitched_atr_by_row` 必须和 `stitched_data_pack.base`、`backtest_schedule` 属于同一 stitched 行轴
   - 每一行的 ATR 值都必须已经按该行所属 segment 的参数语义物化完成
2. kernel 必须校验：
   - 若 schedule 任一段启用 ATR 相关逻辑，但 `atr_by_row = None`，直接报错
   - 若 schedule 全程不启用 ATR 相关逻辑，但传入了 `atr_by_row`，也直接报错
   - 若传入了 `atr_by_row`，则其长度必须严格等于 `data.mapping.height()`
3. `validate_schedule_atr_contract(...)` 只负责校验 ATR 输入契约，不负责在入口内部现算 ATR。
4. kernel 不负责校验“这条 ATR 是怎么拼出来的”，只负责 fail-fast 校验输入契约。

### 9.4 `BacktestParamSegment` 的行轴语义

`BacktestParamSegment` 的签名已在第 `7` 节先定义，这里只补它的行轴语义：

1. `start_row / end_row` 一律指向 **stitched 绝对行轴**。
2. 它不是原始 WF 输入数据的全局行号。

原因很简单：

1. `run_backtest_with_schedule(...)` 只关心它真正拿到的那份 `stitched_data_pack`。
2. 因此 `schedule` 的行号空间也必须和这份 `stitched_data_pack` 的 base 轴一致。
3. 不能让它再去理解原始 WF 输入中的窗口偏移。

### 9.5 工具函数：`validate_schedule_contiguity(...)`

```rust
fn validate_schedule_contiguity(
    schedule: &[BacktestParamSegment],
    data_length: usize,
) -> Result<(), QuantError>
```

这个 helper 的职责必须收得很窄：

1. 它只检查 `schedule` 在 stitched 行轴上的连续覆盖关系。
2. 它不负责：
   - `segment.params.validate()`
   - `validate_backtest_param_schedule_policy(schedule)`
   - ATR 契约校验

工具函数步骤：

1. 若 `schedule.is_empty()`，直接报错。
2. 检查第一个 segment 是否满足 `start_row == 0`。
3. 从前到后检查每个相邻 segment：
   - 必须按 `start_row` 升序排列
   - 必须满足 `next.start_row == current.end_row`
   - 因而既不允许 gap，也不允许 overlap
4. 检查最后一个 segment 是否满足 `end_row == data_length`。
5. 若以上任一条件不满足，直接报错；全部满足才返回 `Ok(())`。

本 helper 的正式判定条件可以直接写成：

1. 第一个 segment 满足 `schedule[0].start_row == 0`
2. 对任意相邻的 `schedule[i]` 和 `schedule[i + 1]`：
   - `schedule[i].start_row < schedule[i].end_row`
   - `schedule[i + 1].start_row == schedule[i].end_row`
3. 最后一个 segment 满足 `schedule[last].end_row == data_length`

在当前 [04_walk_forward_and_stitched.md](./04_walk_forward_and_stitched.md) 已写死的“`test_active` 相邻首尾相接、无 overlap”前提下：

1. `backtest_schedule` 通常天然就是“一窗一段”。
2. 因此这里的连续覆盖要求不是额外补丁，而是当前 WF 窗口制度的直接产物。

### 9.6 参数允许变化的范围

在 `validate_schedule_contiguity(...)` 之后，`run_backtest_with_schedule(...)` 仍必须继续做两层校验：

1. 对每个 `segment.params` 调用单参数的 `BacktestParams::validate()`
2. 调用字段级 policy：
   `validate_backtest_param_schedule_policy(schedule)`

本篇不再只写“哪些能改、哪些不能改”的口头规则，而是把第二层收敛成一个唯一的字段级 policy：

`validate_backtest_param_schedule_policy(schedule)`

它必须显式检查 `BacktestParams` 的每个字段。本文先把 policy 写死如下：

| field | segment_vary | 说明 |
| --- | --- | --- |
| `sl_pct` | `true` | 可按 segment 切换 |
| `tp_pct` | `true` | 可按 segment 切换 |
| `tsl_pct` | `true` | 可按 segment 切换 |
| `sl_atr` | `true` | 可按 segment 切换 |
| `tp_atr` | `true` | 可按 segment 切换 |
| `tsl_atr` | `true` | 可按 segment 切换 |
| `atr_period` | `true` | 可按 segment 切换 |
| `tsl_psar_af0` | `true` | 可按 segment 切换 |
| `tsl_psar_af_step` | `true` | 可按 segment 切换 |
| `tsl_psar_max_af` | `true` | 可按 segment 切换 |
| `tsl_atr_tight` | `true` | 可按 segment 切换 |
| `sl_exit_in_bar` | `true` | 可按 segment 切换 |
| `tp_exit_in_bar` | `true` | 可按 segment 切换 |
| `sl_trigger_mode` | `true` | 可按 segment 切换 |
| `tp_trigger_mode` | `true` | 可按 segment 切换 |
| `tsl_trigger_mode` | `true` | 可按 segment 切换 |
| `sl_anchor_mode` | `true` | 可按 segment 切换 |
| `tp_anchor_mode` | `true` | 可按 segment 切换 |
| `tsl_anchor_mode` | `true` | 可按 segment 切换 |
| `initial_capital` | `false` | 只在整次连续回测初始化时写入一次账户状态 |
| `fee_fixed` | `false` | 平仓时按当前参数读取，不能被边界切段污染 |
| `fee_pct` | `false` | 平仓时按当前参数读取，不能被边界切段污染 |

这里的设计原则也写死成三条：

1. `segment_vary = false` 的字段，必须在所有 segment 中完全一致，否则直接报错。
2. `segment_vary = true` 的字段，也必须经过显式校验，只不过校验结论是“允许变化”，而不是“强制一致”。
3. 文档、执行文档和最终实现都只能复用这一份字段级 policy，不能在别处再写第二套口头规则。

为了避免后续漂移，再补一条硬约束：

1. 若未来 `BacktestParams` 新增字段，必须在同一任务里同步更新这张 policy 表与 `validate_backtest_param_schedule_policy(...)`。
2. 在 policy 未更新前，不得把新增字段静默视作“默认可变”或“默认不可变”。
