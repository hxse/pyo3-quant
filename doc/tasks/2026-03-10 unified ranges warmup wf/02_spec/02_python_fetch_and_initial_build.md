# Python 网络请求、Rust 取数状态机与 DataPack 构建

## 0. 对象归属与边界

本篇定义：

1. `DataPackFetchPlanner`
2. `SourceFetchState`
3. planner 如何产出 `DataPack`

本篇消费：

1. `WarmupRequirements`
2. `TimeProjectionIndex`
3. `DataPack` builder contract

本篇不负责：

1. 单次回测执行
2. `ResultPack` 构建
3. WF 窗口执行与 stitched replay

本篇仍然保持流程主线，因为 `DataPackFetchPlanner` 本身就是状态机对象；这里的重点不是把状态机写成纯对象说明书，而是把状态机步骤明确绑定到 `DataPackFetchPlanner / SourceFetchState` 这两个对象上。

本卷已拆成两层：

1. 本文保留对象归属、PyO3 边界与 `SourceFetchState` contract。
2. 取数算法、初始 `ranges` 与 `finish()` 见 [02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md](./02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md)。

## 1. Rust 内部如何消费共享预热真值

这一层也继续收口到 Rust 内部，不再由 Python 先调用 `resolve_indicator_contracts(...)`。

状态机初始化时，Rust 内部先执行：

```python
resolved_contract_warmup_by_key =
    resolve_contract_warmup_by_key(indicators_params)

normalized_contract_warmup_by_key =
    normalize_contract_warmup_by_key(S_keys, resolved_contract_warmup_by_key)

applied_contract_warmup_by_key =
    apply_wf_warmup_policy(
        normalized_contract_warmup_by_key,
        false,
    )
    # planner 路径当前固定不忽略指标 warmup，但仍统一复用同一个 helper

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
3. planner 路径即使当前没有 `ignore_indicator_warmup` 分支，也必须显式复用 `apply_wf_warmup_policy(..., false)`；不允许把 `W_applied` 手写退化成另一条平行赋值分支。
4. 这份 `required_warmup_by_key` 同时服务初始取数 planner 和后续 WF 的共享基础 warmup 约束；它不覆盖 WF 专属的 `min_warmup_bars`，后者仍留在 WF 层单独校验。若后续公式需要调整，只允许回到 `01` 改 helper 契约。

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

1. Python 用户层使用 `OhlcvDataFetchConfig`
2. Rust 状态机的 PyO3 边界只暴露最小必要类型，不直接吃 Python 侧 `BaseModel / dataclass`

这样设计符合 PyO3 stub 最佳实践：

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
   - `indicators_params`：与回测引擎指标参数同型；这里直接使用指标参数容器，不要求 Python 侧先手工物化第二套 indicator concrete params；Rust 在状态机初始化时内部调用 `resolve_indicator_contracts(...)` 完成 warmup 聚合
   - `backtest_params`：与回测引擎 `BacktestParams` 同型；这里表达运行参数容器，而不是额外物化出来的一套 concrete runtime params
   - Rust 在状态机初始化时内部调用 `resolve_backtest_exec_warmup_base(backtest_params)`，由该 helper 自己统一解析会影响 exec warmup 的 `Param.value / Param.max` 真值，并把 base 执行预热并入最终 `required_warmup_by_key`
   - `min_request_bars`：每次循环补拉的最小 bar 数量
   - `max_rounds_per_source`：每个 source 最多允许补拉多少轮，防止死循环
   - Rust 在初始化阶段基于 `timeframes + base_data_key` 只生成：
     - `source_keys = unique({base_data_key} ∪ {"ohlcv_" + timeframe})`
   - 然后对每个 `source_key` 统一调用 [01_overview_and_foundation_2_types_and_mapping.md](./01_overview_and_foundation_2_types_and_mapping.md) 里定义的 `resolve_source_interval_ms(source_key)`，得到唯一合法的 `interval_ms`
   - 不允许在 planner 内部再维护第二套 timeframe -> interval 推导逻辑
   - `base_data_key` 只能通过这条唯一生成式进入 `source_keys`
   - `indicators_params` 里出现的 `source_key` 也必须全部属于 `source_keys`
   - 任一 `source_key` 解析不到合法 `interval_ms`，必须在 planner 初始化阶段直接报错
   - 这里必须把 `effective_limit >= 1` 写死：
     - 因为初始取数算法后续要直接定义 `base_effective_start_time / base_first_live_time`
     - 这要求 base 至少有 `1` 根 live bar
     - 因此 `effective_limit = 0` 属于非法输入，必须在 planner 输入阶段直接报错
   - base 首次有效段长度也必须写死：
     - 首次 `base` 请求只负责拿 `effective_limit` 根 live bar
     - 若 `base_effective_df.height() < effective_limit`，必须直接 fail-fast
     - 不为 `base` 再额外引入一套“右侧补拉到凑满 effective_limit”的分支逻辑
2. `FetchRequest`
   - `source_key`：这一轮请求要补哪一个 source
   - `since`：这一轮请求起点
   - `limit`：这一轮请求数量
   - Python 拿到后，再结合原始 `OhlcvDataFetchConfig` 里的网络字段，组装 `OhlcvRequestParams`

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

### 4.2 `SourceFetchState` 的对象归属

`SourceFetchState` 是 `DataPackFetchPlanner` 内部的 per-source 真值对象。它不直接暴露为顶层公共 PyO3 类型，但这条状态必须在摘要层写死，不能只靠流程段落拼出来。

它至少承接 4 组状态：

1. source 静态身份：
   - `source_key`
   - `interval_ms`
2. 当前请求快照：
   - 当前轮的 `since`
   - 当前轮的 `limit`
   - 当前持有的完整 `df`
3. 三段补拉进度：
   - 尾覆盖是否完成
   - 首时间覆盖是否完成
   - 首预热 bars 是否完成
4. 迭代控制状态：
   - 当前 source 已补拉多少轮
   - 是否达到 `max_rounds_per_source`
   - 是否满足最终完成条件

它的状态迁移也统一只有一条正式顺序：

1. 先拿到当前 source 的首份完整快照
2. 再补尾覆盖
3. 再补首时间覆盖
4. 最后补首预热 bars
5. 三段都完成后，当前 source 才进入 `is_complete = true`

失败语义固定为：

1. 结构非法输入：
   - 直接在 `ingest_response(...)` 报错
2. 结构合法但覆盖不足：
   - 继续推进三段补拉
3. 任一 source 的轮次超过 `max_rounds_per_source`：
   - 直接 fail-fast
4. 只有全部 `SourceFetchState` 都完成后，`DataPackFetchPlanner.is_complete()` 才能变成 `true`

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

## 5. 取数算法与 finish

取数算法、初始 `ranges` 计算与 `finish()` 的唯一落点已经拆到：

1. [02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md](./02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md)

该分卷唯一负责：

1. `ensure_tail_coverage(...)`
2. `ensure_head_time_coverage(...)`
3. `ensure_head_warmup_bars(...)`
4. 初始 `ranges` 的 Rust 侧唯一算法
5. `planner.finish() -> build_data_pack(...) -> DataPack`
