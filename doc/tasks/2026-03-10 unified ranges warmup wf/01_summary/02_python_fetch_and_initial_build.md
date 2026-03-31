# Python 网络请求、Rust 取数状态机与 DataPack 构建

## 1. Rust 内部如何消费共享预热真值

这一层也继续收口到 Rust 内部，不再由 Python 先调用 `resolve_indicator_contracts(...)`。

状态机初始化时，Rust 内部先执行：

```python
resolved_contract_warmup_by_key =
    resolve_contract_warmup_by_key(indicators_params)

normalized_contract_warmup_by_key =
    normalize_contract_warmup_by_key(S_keys, resolved_contract_warmup_by_key)

applied_contract_warmup_by_key =
    normalized_contract_warmup_by_key
    # planner 路径当前没有 ignore_indicator_warmup 分支，因此这里直接退化为恒等赋值

backtest_exec_warmup_base =
    resolve_backtest_exec_warmup_base(backtest_params)

required_warmup_by_key =
    merge_required_warmup_by_key(
        base_data_key,
        applied_contract_warmup_by_key,
        backtest_exec_warmup_base,
    )
```

这里本篇只保留三条会影响 planner 控制流的结论：

1. 上述 helper 的公式、边界与“唯一实现源”约束统一引用 [01_overview_and_foundation.md](./01_overview_and_foundation.md)，本篇不再重复展开。
2. planner 初始化阶段必须在 Rust 内部显式跑完这条链，并且后续统一消费最终的 `required_warmup_by_key`。
3. 这份 `required_warmup_by_key` 同时服务初始取数 planner 和后续 WF 的共享基础 warmup 约束；它不覆盖 WF 专属的 `min_warmup_bars`，后者仍留在 WF 层单独校验。若后续公式需要调整，只允许回到 `01` 改 helper 契约。

## 2. Python / Rust 职责划分

| 层 | 只负责 | 明确不负责 |
| --- | --- | --- |
| Python | 发网络请求、转 `pl.DataFrame`、重试空响应、把快照交给 Rust | 计算 warmup、判断 coverage、计算 `ranges`、调用 `build_data_pack(...)` |
| Rust planner | 规划请求、补尾覆盖、补首时间覆盖、补首预热、base 左裁、source 保留、算初始 `ranges`、内部调用 `build_data_pack(...)` | 把网络 IO 留在 Python |

这样收口的结果是：

1. Python 只保留 IO。
2. 所有取数算法统一收口到 Rust。
3. Python 最终不再直接调用 `build_data_pack(...)`。

这里再写死一条高内聚原则：

1. 本篇只讨论“如何把数据请求到位”。
2. 真正的 `DataPack / ResultPack` 构建校验，统一引用 [01_overview_and_foundation.md](./01_overview_and_foundation.md) 里的 builder 定义。
3. 因此本篇只保留状态机为了达成请求目标所需的完成条件与少量内部一致性断言，不再重复定义第二套 Pack 级校验。

## 3. 上游 API 约束

行情 API 只支持 `since + limit` 取数，不支持直接按 `[start, end]` 或 `until` 拉取。

因此取数算法不是“一次命中”，而是：

1. 先把 base 本身补到完整容器时间轴。
2. 再把每个 source 补到对该 base 时间轴的**全量覆盖**。
3. 若一次估算不到位，就循环重拉，直到覆盖成立或达到重试上限。
4. 由于可能存在节假日和休盘，永远不要假设“按时间间隔估出来的 bar 数量”是准确的；时间间隔预估只能作为首轮近似，后续必须结合循环请求，直到真实返回结果确认条件已经满足。

## 4. Rust 取数状态机

推荐形态：

```rust
struct DataPackFetchPlanner { ... }
```

Python 与状态机的交互模型：

```text
planner = DataPackFetchPlanner::new(...)

while !planner.is_complete():
    req = planner.next_request()
    df = py_fetch(req)        // Python 只做网络请求
    planner.ingest_response(req.key, df)

data_pack = planner.finish()
```

这里的关键点是：

1. Python 把网络响应立刻转成 `pl.DataFrame`
2. 然后直接传给 Rust 状态机
3. Rust 状态机内部维护全部算法状态
4. 最后直接返回 `DataPack`

### 4.1 PyO3 交互接口

这一层接口要完全定义清楚，避免 Python / Rust 两边各自脑补。

这里要明确分成两层：

1. Python 用户层继续复用现有 `OhlcvDataFetchConfig`
2. Rust 状态机的 PyO3 边界只暴露最小必要类型，不直接吃 Python 侧 `BaseModel / dataclass`

这样设计也符合当前项目的 PyO3 stub 最佳实践：

1. Rust 边界类型必须在 Rust 中定义，作为唯一源头
2. Python 侧只消费由 Rust 自动生成的 `.pyi` 存根，不再镜像维护一份平行类型
3. PyO3 边界类型保持最小、稳定、明确
4. Python 用户层类型继续服务业务可读性，不直接穿透到 Rust 边界

这里也要明确：

1. `OhlcvDataFetchConfig` 和 `OhlcvRequestParams` 都是当前 Python 侧已有类型
2. 它们继续服务 Python 用户层配置与网络请求，不作为 Rust 边界类型直接暴露

推荐暴露以下 PyO3 类型：

```python
class DataPackFetchPlannerInput:
    timeframes: list[str]
    base_data_key: str
    effective_since: int
    effective_limit: int
    indicators_params: Mapping[str, Mapping[str, Mapping[str, Param]]]
    backtest_params: BacktestParams
    min_request_bars: int = 10
    max_rounds_per_source: int = 20


class FetchRequest:
    source_key: str
    since: int
    limit: int


class DataPackFetchPlanner:
    def __init__(self, planner_input: DataPackFetchPlannerInput) -> None: ...
    def next_request(self) -> FetchRequest | None: ...
    def ingest_response(self, request: FetchRequest, df: pl.DataFrame) -> None: ...
    def is_complete(self) -> bool: ...
    def finish(self) -> DataPack: ...
```

| 字段 | 正式来源 | 说明 |
| --- | --- | --- |
| `timeframes / base_data_key / effective_since / effective_limit` | `OhlcvDataFetchConfig` | 来自用户层取数配置 |
| `indicators_params` | 当前运行参数 | 直接沿用现有指标参数容器，不手工物化第二套 concrete indicator params |
| `backtest_params` | 当前运行参数 | 直接沿用现有 `BacktestParams` 容器，不手工物化第二套 concrete runtime params |
| `min_request_bars / max_rounds_per_source` | planner 输入 | 只属于取数状态机 |

字段语义：

1. `DataPackFetchPlannerInput`
   - `timeframes`：从用户层 `OhlcvDataFetchConfig.timeframes` 拿到
   - `base_data_key`：从用户层 `OhlcvDataFetchConfig.base_data_key` 拿到
   - `effective_since`：从用户层 `OhlcvDataFetchConfig.since` 拿到；这里强约束要求必须是显式整数
   - `effective_limit`：从用户层 `OhlcvDataFetchConfig.limit` 拿到；这里强约束要求必须是显式整数，且必须满足 `effective_limit >= 1`
   - `indicators_params`：与回测引擎当前使用的指标参数同型；这里继续直接复用当前项目已有的指标参数容器，不要求 Python 侧先手工物化第二套 indicator concrete params；Rust 在状态机初始化时内部调用 `resolve_indicator_contracts(...)` 完成 warmup 聚合
   - `backtest_params`：与当前回测引擎使用的 `BacktestParams` 同型；这里仍然是当前项目本来就在运行参数里使用的回测参数容器，而不是额外物化出来的一套 concrete runtime params
   - Rust 在状态机初始化时内部调用 `resolve_backtest_exec_warmup_base(backtest_params)`，由该 helper 自己统一解析会影响 exec warmup 的 `Param.value / Param.max` 真值，并把 base 执行预热并入最终 `required_warmup_by_key`
   - `min_request_bars`：每次循环补拉的最小 bar 数量
   - `max_rounds_per_source`：每个 source 最多允许补拉多少轮，防止死循环
   - Rust 在初始化阶段基于 `timeframes + base_data_key` 推导：
     - `source_keys = {"ohlcv_" + timeframe}`
     - 每个 `source_key` 对应的 `interval_ms`
   - `base_data_key` 必须在 `source_keys` 中
   - `indicators_params` 里出现的 `source_key` 也必须全部属于 `source_keys`
   - 这里必须把 `effective_limit >= 1` 写死：
     - 因为初始取数算法后续要直接定义 `base_effective_start_time / base_first_live_time`
     - 这要求 base 至少有 `1` 根 live bar
     - 因此 `effective_limit = 0` 属于非法输入，必须在 planner 输入阶段直接报错
2. `FetchRequest`
   - `source_key`：这一轮请求要补哪一个 source
   - `since`：这一轮请求起点
   - `limit`：这一轮请求数量
   - Python 拿到后，再结合原始 `OhlcvDataFetchConfig` 里的网络字段，组装当前项目现有的 `OhlcvRequestParams`

两层转换关系：

1. 用户层先持有原始 `OhlcvDataFetchConfig` 与当前运行参数
2. Python 从中抽取 planner 真正需要的字段，构造 `DataPackFetchPlannerInput`
   - `timeframes / base_data_key / effective_since / effective_limit` 来自 `OhlcvDataFetchConfig`
   - `indicators_params / backtest_params` 来自当前运行参数
   - 这里的 `indicators_params` 不要求 Python 侧先把优化参数树手工物化成最终 concrete 值；唯一合法解释入口仍是 Rust `resolve_indicator_contracts(...)`
   - 这里的 `backtest_params` 不要求 Python 侧先把优化参数树手工物化成最终 concrete 值；唯一合法解释入口仍是 Rust `resolve_backtest_exec_warmup_base(...)`
3. Rust `next_request()` 只返回最小请求描述 `FetchRequest`
4. Python 再把 `FetchRequest + OhlcvDataFetchConfig` 组合成现有 `OhlcvRequestParams`
5. 然后直接调用现有 `get_ohlcv_data(...)`

方法语义：

1. `DataPackFetchPlanner(planner_input)`
   - Rust 侧创建状态机并初始化全部内部状态
2. `next_request()`
   - 返回当前下一轮要发的请求
   - 若返回 `None`，表示状态机已经满足完成条件
3. `ingest_response(request, df)`
   - Python 把这一轮网络结果转成 `pl.DataFrame` 后回传给 Rust
   - 这里的 `df` 必须是“当前这组 `since + limit` 请求对应的完整 DF 快照”，不是增量碎片
   - Rust 侧校验该响应是否对应当前挂起请求，并直接替换该 source 当前持有的 DF，不做碎片合并或去重
   - 这里再把失败语义写死：
     - 空响应重试留在 Python 层，不放进 Rust 状态机内部实现
     - Python 对“空 DF / 无数据响应”默认最多重试 `2` 次
     - 若重试后仍为空，则 Python 直接报错，不再调用 `ingest_response(...)`
     - Rust `ingest_response(...)` 只负责接收结构合法、非空的完整快照
4. `is_complete()`
   - 返回当前是否已经可以构建最终 `DataPack`
5. `finish()`
   - 只有在 `is_complete() == true` 时允许调用
   - Rust 内部完成最终 `ranges` 计算与 `build_data_pack(...)`
   - 直接返回最终 `DataPack`

Python 侧职责因此固定为：

1. 持有原始 `OhlcvDataFetchConfig`
2. 持有当前运行参数中的 `indicators_params / backtest_params`
3. 从中构造 `DataPackFetchPlannerInput`
4. 调 `next_request()`
5. 用 `FetchRequest + OhlcvDataFetchConfig` 组装现有 `OhlcvRequestParams`
6. 发网络请求
7. 把响应转成 `pl.DataFrame`
8. 若响应为空，Python 侧最多重试 `2` 次；重试后仍为空则直接报错
9. 只有拿到非空 `pl.DataFrame` 后，才调 `ingest_response(...)`
10. 循环直到 `finish()`

除此之外，Python 不再维护任何取数算法状态。

`ingest_response(...)` 的结构性输入契约也要写死：

1. 职责边界先写死：
   - 空响应重试只在 Python 层处理
   - 除“空响应”外，其余结构性校验都以 Rust `ingest_response(...)` 为唯一正式入口
2. Python 层：
   - 若网络响应转成 `pl.DataFrame` 后为空，则最多重试 `2` 次
   - 重试后仍为空，Python 直接报错，不再调用 `ingest_response(...)`
3. Rust `ingest_response(...)`：
   - 接收到的 `df` 默认应为非空快照
   - 下面这些情况都属于**结构性非法输入**，必须直接报错，不进入后续补拉规划：
   - 缺少 `time` 列
   - `time` 列类型不是 `Int64`
   - `time` 列存在 null
   - `time` 列不是严格递增
   - `time` 列存在重复时间戳
   - `request.source_key` 与当前挂起请求不匹配
4. 只有 `df` 本身结构合法时，才允许继续进入：
   - `ensure_tail_coverage(...)`
   - `ensure_head_time_coverage(...)`
   - `ensure_head_warmup_bars(...)`
5. 因此这里必须区分两类情况：
   - **结构非法**：立刻报错
   - **结构合法但覆盖不足**：允许继续补拉

## 5. 两阶段取数算法

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

### 5.1 先请求 base 有效段

1. 先请求 `base`：`since=t_start, limit=L`
2. 得到 `base_effective_df` 后，记录：
   - `base_effective_start_time = base_effective_df.time.first()`
   - `base_effective_end_time = base_effective_df.time.last()`
3. 这里不要假设 `base_effective_start_time == since`
4. 一切后续计算都以**真实返回时间列**为准，不直接拿请求参数时间戳代替

### 5.2 Rust 内部方法一：补齐尾部覆盖

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

### 5.3 Rust 内部方法二：补齐首部时间覆盖

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

每轮公式：

1. `missing_by_head_coverage = ceil(max(first_time - target_start_time, 0) / interval_ms)`
2. `prepend_bars = max(missing_by_head_coverage, min_request_bars)`
3. 重新请求时：
   - `since = old_since - prepend_bars * interval_ms`
   - `limit += prepend_bars`

这里的 `ensure_head_time_coverage(...)` 是 **Rust 状态机内部方法**，Python 不负责实现这段逻辑。
当前 source 的 `since / limit / df` 都由状态机自己持有和更新。

### 5.4 Rust 内部方法三：补齐首部预热数量

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

### 5.5 Rust 侧主流程：先 base，再 source

1. 先取到 `base_effective_df`
2. 用 `ensure_head_time_coverage(...)` 补齐 `base` 左侧时间覆盖
   - `target_start_time = base_effective_start_time`
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

## 6. Rust 侧初始 ranges 计算

这一步改到 Rust 取数状态机内部做，而且必须在**真实返回时间列**上做，不再预估。

### 6.1 base 的 ranges

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

### 6.2 非 base source 的 ranges

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
3. 必须统一复用 `map_source_row_by_time(...)`，其内部再使用 Polars 向量化 API，例如 `join_asof(..., strategy=\"backward\")` 或等价实现。
4. 不允许手写循环扫时间列，也不允许在这里再单独实现一套“看起来等价”的时间映射。
5. 因为上一步已经保证 source 对 `base_full` 全量覆盖，所以这里的 `mapped_src_idx` 必然存在，不允许为 null。
6. 这里得到的 `mapped_src_idx` 就是最终 warmup 真值，不再额外 `max(...)` 修正。

## 7. Rust 状态机 finish 后如何返回 DataPack

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

## 8. Rust builder 的职责边界

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
