# 临时 TODO：fetched planner 接线缺口

> 说明：
> 1. 本文件是临时执行备忘，不是 `03-10` 的正式 Spec 正文。
> 2. `03-10` 的正式真值仍以 `02_spec/` 为准。
> 3. 本文件只记录当前排查到的实现缺口、证据链与后续修复计划。

## 1. 当前问题

`03-10` 的正式设计要求：

1. fetched / planner 路径先把 full `DataPack` 补到满足 `required_warmup_by_key`
2. `planner.finish()` 再产出正式 `ranges`
3. WF 只在这个前提上继续做窗口规划与 source 投影

当前仓库的 live / fetched 正式入口没有真正接到这条链上。

## 2. 当前实现缺口

### 2.1 当前 fetched 路径

当前 `py_entry/data_generator/data_generator.py` 的 fetched 分支仍是：

1. Python 先请求 base 数据
2. Python 对非 base source 只做 coverage backfill
3. 最后直接调用 `pyo3_quant.backtest_engine.data_ops.build_time_mapping(...)`

对应代码位置：

1. [py_entry/data_generator/data_generator.py](/home/hxse/pyo3-quant/py_entry/data_generator/data_generator.py:195)
2. [py_entry/data_generator/data_generator.py](/home/hxse/pyo3-quant/py_entry/data_generator/data_generator.py:266)

### 2.2 当前 Rust builder 路径

`build_time_mapping(...)` 最终走 `build_full_data_pack(...)`，而当前 `build_full_data_pack(...)` 仍把所有 source 的 `ranges` 直接写成：

1. `warmup_bars = 0`
2. `active_bars = pack_bars`
3. `pack_bars = source.height()`

对应代码位置：

1. [src/backtest_engine/data_ops/source_contract.rs](/home/hxse/pyo3-quant/src/backtest_engine/data_ops/source_contract.rs:138)

这说明当前正式 fetched 入口还没有落实 `03-10` 里 planner / finish / initial_ranges 的 frozen contract。

## 3. 与 `03-10` 正式 Spec 的不一致点

`03-10` 正式 Spec 要求：

1. Rust planner 初始化先算出 `required_warmup_by_key`
2. 非 base source 需要围绕 `base_first_live_time` 做 head warmup 补拉
3. `build_initial_ranges(...)` 必须断言 `mapped_src_idx >= W_required[k]`

对应正式文档与实现：

1. [02_spec/02_python_fetch_and_initial_build.md](/home/hxse/pyo3-quant/doc/tasks/2026-03-10%20unified%20ranges%20warmup%20wf/02_spec/02_python_fetch_and_initial_build.md:30)
2. [02_spec/02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md](/home/hxse/pyo3-quant/doc/tasks/2026-03-10%20unified%20ranges%20warmup%20wf/02_spec/02_python_fetch_and_initial_build_1_fetch_algorithm_and_finish.md:141)
3. [src/backtest_engine/data_ops/fetch_planner/planner.rs](/home/hxse/pyo3-quant/src/backtest_engine/data_ops/fetch_planner/planner.rs:334)
4. [src/backtest_engine/data_ops/fetch_planner/initial_ranges.rs](/home/hxse/pyo3-quant/src/backtest_engine/data_ops/fetch_planner/initial_ranges.rs:37)

因此当前问题的准确归因是：

1. `03-10` 的窗口投影公式本身不是这次问题的根因
2. 真正缺口是 fetched 正式入口没有按 `03-10` frozen planner contract 产出 full pack

## 4. 当前证据链

以 `search:adx_macd_mtf.adx_macd_mtf` + `DOGE/USDT` 为例：

1. `warmup_bars_by_source = {'ohlcv_30m': 72, 'ohlcv_4h': 76, 'ohlcv_1d': 76}`
2. 当前 full pack 的 `ranges` 仍是所有 source 都从 `0` 开始
3. `mapping['ohlcv_1d'][72] = 1`
4. `mapping['ohlcv_1d'][500] = 10`

这说明：

1. full pack 里 base 首个 live 区域附近，`1d` source 根本没有被补到 `76` 根 warmup
2. WF 入口后续报错只是把这个 upstream gap 暴露出来

## 5. 与 `04-05` 的边界

`04-05` 当前只负责：

1. 把这类问题在 Rust 正式 mode 入口更早、更清晰地 fail-fast 暴露出来
2. 不恢复 Python precheck

`04-05` 不负责：

1. 修复 fetched planner 主体
2. 把 live/fetched 正式入口真正接回 `DataPackFetchPlanner`

因此真正的实现修复仍应回到 `03-10` 这一条线上处理。

## 6. 临时收口方案：WF 入口 full-pack readiness 校验

### 6.1 这条校验的性质

这条校验不是：

1. 通用 `DataPack` 结构合法性校验
2. 所有 mode 共享的全局入口校验
3. 对 `03-10` planner / finish 正式修复的替代品

这条校验是：

1. `walk_forward` consumer 侧的窄断言
2. 用来判断“当前输入 full `DataPack` 是否已经满足本次 `WF` 的基础 warmup contract”
3. 用来把错误从“窗口切片阶段”前移到“WF 正式入口”

一句话概括：

**它校验的是 `WF-ready full DataPack`，不是泛化的 `DataPack valid`。**

### 6.2 放置位置

建议把这条校验放在：

1. [src/backtest_engine/walk_forward/runner.rs](/home/hxse/pyo3-quant/src/backtest_engine/walk_forward/runner.rs:17) 的 `run_walk_forward(...)`
2. 具体顺序：
   - `validate_mode_settings(...)`
   - `build_warmup_requirements(...)`
   - `validate_wf_input_datapack_readiness(...)`
   - `build_window_indices(...)`

原因：

1. 到这一步已经拿到：
   - `data_pack`
   - `required_warmup_by_key`
2. 但还没进入窗口几何与 source 投影
3. 最适合把“producer 没有产出合格 full pack”的问题，在 consumer 正式入口直接报出来

这里建议显式封装成一个私有工具函数，而不是把校验逻辑直接铺在 `run_walk_forward(...)` 里。

建议函数形态：

```rust
fn validate_wf_input_datapack_readiness(
    data_pack: &DataPack,
    required_warmup_by_key: &HashMap<String, usize>,
) -> Result<(), QuantError>
```

函数职责写死为：

1. 只服务 `walk_forward`
2. 只校验 `WF-ready full DataPack` 的基础 warmup contract
3. 不承担窗口几何、不承担 source 切片、不承担 `min_warmup_bars`
4. 不抽象成通用 mode validator

### 6.3 校验锚点

这条 guard 的锚点不应再重新发明第二套 planner 真值，而是直接基于**当前输入 `DataPack` 自己声明的 live 起点**来判断它是否满足 `WF` 消费前提。

具体锚点：

1. `base_data_key = data_pack.base_data_key`
2. `base_declared_warmup = data_pack.ranges[base].warmup_bars`
3. `base_first_live_row = base_declared_warmup`
4. `base_first_live_time = data_pack.source[base].time[base_first_live_row]`

这里的关键点是：

1. `WF` 入口 guard 校验的是“输入 pack 自己宣称从哪一行开始 live”
2. 然后检查这个 live 起点，是否真的已经给所有 source 留够了 `required_warmup_by_key`
3. 若当前输入 `DataPack` 是按 `03-10` 的 planner / finish 正式构造出来的，那么这里的：
   - `base_declared_warmup`
   - `W_required[base]`
   本来就应当一致
4. 若当前输入 `DataPack` 不是 formal full pack，这条 guard 就会提前暴露出 producer gap

### 6.4 工具函数内部步骤

建议把 `validate_wf_input_datapack_readiness(...)` 的步骤写死为：

1. 先做输入真值存在性校验
   - 若缺少 `base_data_key`，直接报错
   - 若缺少 `data_pack.ranges[base]`，直接报错
   - 若缺少 `data_pack.source[base]`，直接报错
   - 这是 `WF` 自己后续窗口规划也要消费的共享真值
2. 读取并冻结 `base` 锚点
   - `base_declared_warmup = data_pack.ranges[base].warmup_bars`
   - `base_required = required_warmup_by_key[base]`
   - 若 `base_declared_warmup < base_required`，直接报错
   - 若 `data_pack.source[base].height() < base_declared_warmup + 1`，直接报错
   - `base_first_live_row = base_declared_warmup`
   - `base_first_live_time = source[base].time[base_first_live_row]`
   - 这里不重新根据 `W_required[base]` 反推出另一套 live 行号
   - 直接以输入 `DataPack` 自己声明的 `ranges[base].warmup_bars` 为准
3. 对每个 source `k` 做 source-level readiness 校验
   - 必须存在 `data_pack.source[k]`
   - 必须存在 `data_pack.mapping[k]`
   - 读取 `mapped_src_idx = data_pack.mapping[k][base_first_live_row]`
   - 若该位置缺失映射或为 null，直接报错
   - 读取 `required = required_warmup_by_key[k]`
   - 若 `mapped_src_idx < required`，直接报错
4. 对 `base` 自己也走同一口径
   - `base` 列在 mapping 上的 `mapped_src_idx` 应等于 `base_first_live_row`
   - 因而 `base` 的检查天然退化为：
     - `base_first_live_row >= W_required[base]`
   - 为避免实现层额外分支，也可以直接统一走 source 循环
5. 只有在全部 source 都通过时，函数返回 `Ok(())`
6. `run_walk_forward(...)` 收到 `Ok(())` 后，才允许进入 `build_window_indices(...)`
   - 后续窗口几何、`min_warmup_bars`、`BorrowFromTrain / ExtendTest` 仍由 WF 自己继续处理
   - 这条 guard 只负责“full pack 已经具备基础 warmup contract”

额外约束：

1. 这个 helper 只读 `data_pack`，不修改 `ranges`、不修补 mapping、也不尝试自动回退
2. 一旦发现不满足 contract，直接返回明确错误，不做静默兜底
3. 后续若别的 mode 也需要类似断言，应由它们各自入口显式调用自己的 helper，而不是把这里抽成全局共享 validator

### 6.5 报错语义

这条校验的报错语义不应再写成“窗口左侧 warmup 不足”，而应明确指向输入契约问题。

建议错误口径：

1. `WF 输入 full DataPack 不满足 required_warmup_by_key`
2. 至少带出：
   - `source_key`
   - `base_first_live_row`
   - `mapped_src_idx`
   - `required_warmup`
3. 明确指出：
   - 当前问题发生在 `run_walk_forward(...)` 入口
   - 当前 full pack 不具备 `WF-ready` 基础预热条件
   - 上游 fetched / planner 路径很可能没有正确 materialize `03-10` frozen contract

### 6.6 与正式修复的关系

这条 guard 只是临时收口，不是最终修复。

它解决的是：

1. 当前报错层级太晚
2. 当前错误文案太像窗口算法 bug
3. 当前缺少一个能把问题直接指向 upstream producer gap 的入口断言

它不解决的是：

1. fetched 正式入口为什么没有走 `DataPackFetchPlanner`
2. `planner.finish()` 为什么没有成为 live / fetched 主路径
3. formal full pack 的 `ranges` 为什么仍然没有被 producer 正确 materialize

因此后续真正修复时：

1. producer 侧仍要接回 `03-10` 的 planner / finish / initial_ranges 链
2. 这条 `WF` 入口 guard 仍然应当保留，作为 consumer-side invariant assertion

## 7. 建议修复计划

### 7.1 阶段 1：把 fetched 正式入口接回 planner

目标：

1. `OhlcvDataFetchConfig` 正式路径不再自己拼 coverage-only full pack
2. Python 只负责网络请求与响应转换
3. Rust `DataPackFetchPlanner` 负责：
   - 请求规划
   - tail coverage
   - head time coverage
   - head warmup
   - `finish()` + `build_initial_ranges(...)`

预期修改面：

1. [py_entry/data_generator/data_generator.py](/home/hxse/pyo3-quant/py_entry/data_generator/data_generator.py:195)
2. `src/backtest_engine/data_ops/fetch_planner/*.rs`

### 7.2 阶段 2：收口 legacy coverage-only 路径

目标：

1. 当前 `_fetch_with_coverage_backfill(...)` 不再承担正式 full pack 语义
2. 若暂时保留，也只能作为过渡调试实现，不再作为正式入口主路径

### 7.3 阶段 3：补测试

至少补三类测试：

1. fetched full pack integration：
   - full pack 的 `ranges` 不再是全 `0/full/full`
   - 非 base source 在 `base_first_live_time` 上满足 `mapped_src_idx >= W_required[k]`
2. MTF WF regression：
   - `30m + 4h + 1d` 组合不再在第 0 窗因 full pack readiness 缺口报错
3. formal guard 协同：
   - 当 legacy 路径仍未修完时，`04-05` 的入口 fail-fast 能稳定把错误指向 full pack readiness gap

## 8. 收口目标

最终目标只有一句话：

**让 fetched 正式入口产出的 full `DataPack` 真正满足 `03-10` 已冻结的 planner / initial_ranges 前提，再让 WF 只消费这份已经成立的 formal input。**
