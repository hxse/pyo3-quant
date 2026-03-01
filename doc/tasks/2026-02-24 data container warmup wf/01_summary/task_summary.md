# DataContainer 与 WF 重构讨论摘要（逻辑链条闭环版）

> 【已废弃】该摘要对应“大一统容器重构”方案。当前已切换到新任务中的“WF 最小改动预热方案”，本文件仅保留历史讨论快照。

这份文档是本次方案讨论摘要，不是迁移文档。目标是把当前口径讲清楚、讲完整，保证理论自洽与实现边界明确。

阅读标记：
- `【目标口径】`：本次收敛后的目标设计。
- `【现状复述】`：用于理论闭环的现状描述，不等于本次必须改代码。
- 全文校验策略：所有校验一律 Fail-Fast，直接报错，不做静默回退。

---

## 1. 类型与术语（统一定义）

### 1.1 容器类型

- `DataContainer`：唯一数据容器类型（执行态/切片态/消费态统一）。
- `BacktestSummary`：唯一结果容器类型。
- 两类容器都带 `run_ranges: HashMap<String, SourceRanges>`。
- 两类容器都不可变；任何切片都必须通过工具函数返回新对象。
- 不可变口径是 API 级强约束：对外只读，禁止外部就地改写（通过删除/禁用 setter 落地）。

### 1.2 范围字段

- `run_ranges: HashMap<String, SourceRanges>`，在 `DataContainer` 和 `BacktestSummary` 中同结构存在；key 集合必须与 `DataContainer.source` 的 key 一致。
- `SourceRanges`：
  - `warmup_range: (usize, usize)`
  - `data_range: (usize, usize)`
- 区间语义：半开区间 `[start, end)`。
- 索引语义：相对于当前容器中该 `source` 自身 DataFrame 的行号，不是全局绝对索引，不是 base 行号。
- 约束：`run_ranges` 只描述“当前容器自身”的范围，支持连续切片。

---

## 2. 设计初衷与固定约束

### 2.1 为什么要做

多周期策略在训练与测试中都依赖预热上下文。没有预热会直接降低训练质量，测试窗口也会被预热占用，导致有效样本变少、窗口评估噪声变大。

### 2.2 固定约束

1. 接受破坏性更新，不做兼容层。
2. 网络请求在 Python 侧，核心计算在 Rust 侧。
3. 先统一唯一口径，再谈扩展；当前阶段优先简单、统一、唯一。

---

## 3. 场景视角：结构是否成立

路径说明：这里只描述容器流转；函数其他参数与返回保持现状，不在本节展开。

### 3.1 Python 请求数据

- 先调用 Rust 静态工具函数 `resolve_indicator_contracts`，得到指标契约快照：
  - `required_warmup_dict`（每个 source 的聚合预热需求）
  - `indicator_contracts`（每个指标实例的 `required_warmup_bars` 与 `allow_internal_nan` 明细）
- 再按固定网络流程完成“非预热覆盖 + 预热补齐”（详见第 4.3 节）。
- 最后调用统一构建函数生成成型 `DataContainer`（全量，含预热+非预热）。

### 3.2 单次回测

路径：`DataContainer -> BacktestSummary`。

- 输入 `DataContainer`：全量对象（含预热+非预热）。
- 输出 `BacktestSummary`：全量对象（含预热+非预热）。
- 指标、信号、回测都使用全量执行区间。
- 绩效只统计非预热段。
- `mapping` 全长保留，但业务严格性只绑定非预热段。

### 3.3 优化与参数抖动

路径同单次回测：`DataContainer -> BacktestSummary`。

- 输入/输出都保持全量对象（含预热+非预热）。
- 两者复用主回测链，不引入第二套数据语义。

### 3.4 向前测试

- 引擎输入 `full_data`：全量 `DataContainer`（含预热+非预热）。
- 窗口中间态 `Vec<WindowItem>`：训练/测试的 `DataContainer + BacktestSummary` 都是全量对象（各自窗口内的预热+非预热）。
- 窗口返回 `Vec<WindowArtifact>`：每窗只保留非预热测试段（`DataContainer/BacktestSummary` 仍是同类型对象，但 `warmup_range=(0,0)`）。
- 拼接返回 `stitched DataContainer + stitched BacktestSummary`：只包含非预热测试段拼接结果（`warmup_range=(0,0)`）。
- 拼接一致性：stitched 时间序列必须与“从全量容器一次提取全局连续非预热测试区间”的时间序列一致。

### 3.5 画图

路径：`DataContainer + BacktestSummary -> DataContainer + BacktestSummary`（成对切到 `warmup_range=(0,0)` 的非预热视图）。

- 输入：全量 `DataContainer + BacktestSummary`（含预热+非预热）。
- 输出：非预热视图 `DataContainer + BacktestSummary`（`warmup_range=(0,0)`）。
- 画图切片必须成对执行，避免输入/输出错位。
- 工具函数在 Rust 定义，通过 PyO3 暴露给 Python。

---

## 4. 映射、覆盖、切片：统一口径

### 4.0 职责归属表（唯一口径）

| 层级 | 负责 | 不负责 |
|---|---|---|
| Python 网络层 | 调用 `resolve_indicator_contracts`；按 `since+limit` 补拉非预热与预热数据 | 不做 mapping 构建与运行时校验 |
| `build_data_container` / mapping 流程 | 按 `run_ranges` 切片；重建 mapping；执行覆盖/映射/数据完整性校验 | 不做网络请求；不做 WF 注入编排 |
| 回测引擎 | 指标/信号/回测/绩效阶段执行；预热禁开仓；按 `data_range` 统计绩效 | 不负责拉数据；不负责窗口切分 |
| WF 编排层 | 生成窗口索引；注入跨窗信号；组织拼接与一致性校验 | 不手工拼容器；不绕过构建函数校验 |

### 4.1 Mapping 结构契约

- `mapping` 始终按 base 全长构建，行数等于 base 全量行数。
- 这是结构契约（切片/重基/窗口编排依赖），不等于“全段业务都参与”。

### 4.2 非预热段硬校验（唯一硬区间）

`mapping` 构建阶段只对 `run_ranges[base].data_range` 做硬校验：

1. 非预热段需满足首尾覆盖：
   - `source_start_time <= base_data_start_time`
   - `source_end_time + source_interval > base_data_end_time`
2. 非预热段映射结果不得出现 `null`。
3. 预热段允许不完整，不做覆盖硬校验。
4. `source` 中所有 DataFrame 必须全区间通过 `null/NaN` 校验：不允许在任意行出现 `null/NaN`。
5. `base_data_key` 必须是最小周期；若存在比 base 更高频的 source，mapping 构建直接报错。

口径说明：
- 规则 1/2 是“映射正确性”校验，只看非预热段。
- 规则 4 是“原始 source 完整性”校验（通常是 OHLCV/Heikin-Ashi 输入），不是指标输出 NaN 校验。
- 预热段只用于指标预热；信号/回测/绩效业务正确性由非预热段保证。

### 4.3 Python 网络流程（先非预热，后预热）

这是 Python 网络层职责，不属于 Rust 静态预热工具函数。
现有默认行情 API 入参只有 `since + limit`，没有“按结束时间直接请求”的模式。
因此补拉策略必须以“时间锚点（since）”为主，`limit` 只作为每轮容量参数。

向前补拉与向后补拉必须严格区分：

1. 向前补拉（解决 `start` 不覆盖、预热不足）：
   - 目标是让“首根更早”。
   - 在 `since + limit` 模式下，想拿到更早数据只能前移 `since`。
   - 仅增大 `limit` 不会让首根更早，只会让尾部更长。
2. 向后补拉（解决 `end` 不覆盖）：
   - 目标是让“末根更晚”。
   - 在 `since` 固定时，直接增大 `limit` 就能向后扩展可返回区间。
   - 因此 `end` 侧可以按剩余缺口数量连续补拉。

1. 调用 `resolve_indicator_contracts`（返回 `required_warmup_dict + indicator_contracts`；仅给静态契约，不参与覆盖计算）。
2. 补拉性能参数（Python 层）：
   - `start_backfill_step_bars`：`start` 侧每轮补拉数量（直接使用该值）。
   - `end_backfill_min_step_bars`：`end` 侧每轮最小补拉数量（下限值）。
   - `warmup_backfill_min_step_bars`：预热段每轮最小补拉数量（下限值）。
3. 先拉非预热段：
   - 先请求 base 非预热目标区间，得到 `base_data_start_time/base_data_end_time`。
   - 再请求各 source 非预热区间；首轮可与 base 共用 `since/limit`。
   - `start` 侧：若 `source_start_time > base_data_start_time`，每轮按 `start_backfill_step_bars` 前移 `since`，直到覆盖。
   - `end` 侧：先预估数量再补拉：
     - `required_source_bars_for_end = ceil((base_data_end_time - source_data_start_time) / source_interval_ms) + 1`
     - 若 `source_end_time + source_interval_ms <= base_data_end_time`，按“剩余缺口数量 + 最小步长”连续增大 `limit`：
       `missing = required_source_bars_for_end - actual_returned_bars`，每轮请求 `max(missing, end_backfill_min_step_bars)`，再用新返回量重算 `missing`，直到覆盖。
4. 再拉预热段：
   - 对每个 source 先读取 `warmup_need = required_warmup_dict[source]`，再先估算“预热目标起始时间”：
     `warmup_target_start_time = base_data_start_time - warmup_need * source_interval_ms`，首轮以该时间作为 `since` 请求。
   - 若首轮返回后仍不足，按“剩余缺口对应的时间跨度”连续前移 `since`：
     `warmup_missing = warmup_need - actual_warmup_bars`，每轮前移 `max(warmup_missing, warmup_backfill_min_step_bars) * source_interval_ms`，再重算 `warmup_missing`，直到满足。
   - `source_interval_ms` 估算只适用于等间距时间序列（`ohlcv`、`Heikin-Ashi`）；`renko_*` 不保证该估算有效，风险外部承担。
5. 两段都满足后，进入 Rust 构建函数。
6. 超过重试上限直接报错（Fail-Fast）。

### 4.4 Mapping 使用场景白名单

1. 指标阶段：读取全量映射；预热段仅用于指标预热样本。
2. 信号阶段：读取全量映射；预热段禁开仓；`null/NaN` 按现有口径压为 `false`。
3. 回测阶段：全量执行；无外部注入时，预热段不会开仓。
4. 绩效阶段：只统计非预热段。
5. 向前测试：只映射非预热段；预热段禁止走 mapping 反查，统一按全局预热数量回补。

### 4.5 数据源边界

- 标准连续时间序列路径：`ohlcv`、`Heikin-Ashi`。
- `renko_*` 允许接入，但为外部自担风险路径。
- `renko_*` 的 mapping 仍按 `join_asof(backward)`：同一时刻多行候选时取最后一行。
- 若策略语义不接受该行为，需外部先整理数据或禁用该源。

---

## 5. 静态预热工具函数（唯一真值）

函数：`resolve_indicator_contracts`。

输入：指标参数集合 + `base_data_key`。
输出：`IndicatorContractSnapshot`，包含两部分：
- `required_warmup_dict: {source -> warmup_bars}`（按 source 聚合后的预热需求）
- `indicator_contracts: [{source, indicator_key, required_warmup_bars, allow_internal_nan}]`（指标实例明细契约）

Rust 硬结构（对外契约）：

```rust
pub struct IndicatorContractSnapshot {
    pub required_warmup_dict: HashMap<String, usize>,
    pub indicator_contracts: Vec<IndicatorContractItem>,
}

pub struct IndicatorContractItem {
    pub source: String,
    pub indicator_key: String,
    pub required_warmup_bars: usize,
    pub allow_internal_nan: bool,
}
```

职责：只做静态指标契约解析（预热 + NaN 豁免）；无网络副作用；可复用。

规则：
1. 每个指标都必须实现 `required_warmup_bars(params) -> usize`。
2. 取参规则：`optimize=true` 取 `max`，`optimize=false` 取 `value`。
3. 同一 source 多指标取最大值，不求和。
4. 所有 source 都只保留“自身指标需求聚合结果”，不做跨周期估算或比例换算。
5. 返回值同时包含“明细契约 + 聚合预热”，不再拆成两个对外函数。
6. 不负责覆盖补齐，不负责网络请求，不负责运行时覆盖校验。

`IndicatorContractSnapshot` 与 `run_ranges` 的关系：
- `required_warmup_dict` 是静态需求真值（来自快照聚合层）。
- `indicator_contracts` 是静态明细真值（用于测试与调试）。
- `run_ranges` 是当前容器实际范围。
- 两者不要求数值恒等；进入执行链时只要求 `run_ranges` 合法且非预热覆盖校验通过。

### 5.1 指标清单（当前 registry，按现有 Rust 实现精确对齐）

硬约束：本表用于“对齐当前 Rust 指标实现行为”，不是理论估计值；Rust 指标实现本次不改，`required_warmup_bars` 必须与当前实现严格一致。

1. `sma`：`period - 1`
2. `ema`：`period - 1`
3. `rma`（standalone）：`0`
4. `rsi`：`period`
5. `tr`：`1`
6. `atr`：`period`
7. `macd`：`max(fast, slow) + signal - 2`
8. `adx`：`2 * period - 1`
9. `cci`：`period - 1`
10. `bbands`：`period - 1`
11. `er`：`length`
12. `psar`：`1`
13. `opening-bar`：`0`
14. `sma-close-pct`：`period - 1`
15. `cci-divergence`：`CCI.required_warmup_bars(params)`（`_value` 列口径）
16. `rsi-divergence`：`RSI.required_warmup_bars(params)`（`_value` 列口径）
17. `macd-divergence`：`MACD.required_warmup_bars(params)`（`_value` 列口径）

### 5.2 `allow_internal_nan` 口径

- `psar`：`true`（仅 PSAR 输出列豁免中间结构性 NaN）。
- 其余已注册指标：`false`。
- `supertrend` 当前未注册；后续引入时必须显式逐列声明。

补充：
- `has_leading_nan` 不再参与业务判断，只保留调试用途。
- 用户手填 warmup 被放弃：统一以静态函数结果为准。

### 5.3 指标 pytest 联合校验计划（warmup + NaN 豁免）

目标：在现有指标精度测试中，顺带验证“预热需求是否正确”和“`allow_internal_nan` 是否按口径生效”。

执行方式（pytest 为主）：
0. 硬约束：测试以 Rust 契约为唯一真值；Python 测试代码禁止硬编码任何预热需求常量。
1. 复用现有 `py_entry/Test/indicators/indicator_test_template.py` 与 `run_indicator_backtest(...)`，不新增第二套测试框架。
2. 在每个指标测试中，通过 PyO3 调用 `resolve_indicator_contracts`（待落地）断言：
   - 返回的 `required_warmup_dict[source]` 与 `indicator_contracts` 聚合结果一致；
   - 同一 source 多指标场景取最大值，不求和。
3. 在单指标测试中，按“该指标主校验列”做分段断言（不是指标集合口径）：
   - 先用容器 `run_ranges[source].warmup_range` 确定预热段长度 `warmup`（执行态真值）。
   - 再断言：`required_warmup_bars == warmup`（单指标场景）。
   - `allow_internal_nan=false`：预热段 `[0, warmup)` 全 `null/NaN`，非预热段 `[warmup, end)` 无 `null/NaN`。
   - `allow_internal_nan=true`：预热段 `[0, warmup)` 全 `null/NaN`，非预热段 `[warmup, end)` 跳过 NaN/null 校验。
   - “主校验列”由 Rust 契约导出（测试侧不硬编码列名）；例如 divergence 仅对 `_value` 列做上述断言。
4. `allow_internal_nan` 白名单不在测试侧硬编码：
   - 统一从 Rust 指标注册表导出；
   - Python 测试只消费导出结果并做断言；
   - 新增指标后，测试无需手工改白名单，只需复用导出契约。
5. 推荐新增一个汇总用例文件：`py_entry/Test/indicators/test_indicator_warmup_contract.py`，用于集中校验 warmup 与 NaN 豁免契约；各指标精度用例保持原状并复用该断言工具。

失败策略（Fail-Fast）：
- warmup 计算不一致直接失败；
- `allow_internal_nan=false` 却出现非预热段 NaN 直接失败；
- 未声明豁免却走豁免路径直接失败。

---

## 6. 统一构建函数（Py 与 WF 共用）

【目标口径】容器构建只走一个工具函数，禁止手工拼容器。

推荐契约：

`build_data_container(source, base_data_key, run_ranges, skip_mask?) -> DataContainer`

输入约束：
- `source/skip_mask` 只接受 Polars DataFrame。
- 构建阶段切片统一使用 Polars copy（浅拷贝）语义。
- `source` 每个 DataFrame 必须包含 `time:Int64` 列且无 `null`。
- `base_data_key` 必须存在于 `source` 且可被通用解析函数识别周期信息；解析失败直接报错。

构建语义：
1. `source` 按 `run_ranges[source]` 切片（Polars copy）。
2. `skip_mask`（若存在）按 base 执行区间切片。
3. `mapping` 不外传，基于切片后 source 重新计算。
4. 构建函数只触发 mapping 构建流程；所有 mapping 相关校验都在 mapping 内部执行（第 4 节）。

WF 与 Python 的复用方式：
- Python：用于构建全量容器。
- WF：每个窗口调用两次（训练一次、测试一次）。

---

## 7. 向前测试执行闭环

### 7.1 前提

1. WF 入口只接收已成型 `full_data: DataContainer`。
2. 不在 WF 内调用 `resolve_indicator_contracts`，不在 WF 内做网络请求。
3. WF 只使用“每个 source 的预热数量值”，不使用 `full_data` 的范围区间本身：
   `warmup_bars[source] = full_data.run_ranges[source].warmup_range[1] - full_data.run_ranges[source].warmup_range[0]`。
4. base 侧先归一：
   `warmup_bars[base] = max(warmup_bars[base], 1)`。后续窗口计算统一使用 `warmup_bars[source]`，不再使用“继承区间”口径。

### 7.2 预热来源模式（先定模式，再算窗口）

1. `ExtendTest`：测试预热不借用训练尾部；训练段与测试段各自携带预热，窗口连续无间隙。
2. `BorrowFromTrain`：测试预热借用训练尾部；非首窗更紧凑，同样保持窗口连续无间隙。
3. `BorrowFromTrain` 下 `TestWarmup` 与 `Train` 尾部存在重叠，这是有意设计，不是 bug。
4. 两种模式共同口径：
   - 都是“预热+非预热”执行；
   - 对外窗口返回与 stitched 拼接只保留非预热测试段；
   - base 的测试预热长度统一使用 `warmup_bars[base]`（进入窗口计算前已完成 `warmup_bars[base] = max(warmup_bars[base], 1)`）。

### 7.3 窗口构建（第 0 窗模板 + 步长平移）

硬约束：窗口计算不区分“第一窗/后续窗”。先算第 0 窗模板，再按步长平移。

1. 固定参数：`train_bars`、`test_bars`、`step = test_bars`、`warmup = warmup_bars[base]`。
2. 先定义第 0 窗模板（半开区间）：
   - `BorrowFromTrain`：
     `TrainWarmup[0, warmup)`，`Train[warmup, warmup + train_bars)`，`TestWarmup[train_bars, warmup + train_bars)`，`Test[warmup + train_bars, warmup + train_bars + test_bars)`。
   - `ExtendTest`：
     `TrainWarmup[0, warmup)`，`Train[warmup, warmup + train_bars)`，`TestWarmup[warmup + train_bars, 2 * warmup + train_bars)`，`Test[2 * warmup + train_bars, 2 * warmup + train_bars + test_bars)`。
3. 第 `w` 窗统一平移：`delta = w * step`。
   对第 0 窗四段的每个区间 `[start_0, end_0)`，得到 `[start_0 + delta, end_0 + delta)`。
4. 把 base 的 `Train/Test` 投影到每个 source，得到每个 source 的 `data_range`。
   硬约束：base 必须是最小周期；若存在比 base 更高频的 source，mapping 构建直接报错。
5. 对每个 source 计算 `warmup_range`：
   - `source_warmup_bars = warmup_bars[source]`。
   - `train_run_ranges[source].warmup_range = [max(0, train_run_ranges[source].data_range.start - source_warmup_bars), train_run_ranges[source].data_range.start)`。
   - `test_run_ranges[source].warmup_range = [max(0, test_run_ranges[source].data_range.start - source_warmup_bars), test_run_ranges[source].data_range.start)`。
6. 向前测试按窗口调用两次 `build_data_container(...)`：
   - 训练：`source=full_data.source, base_data_key=full_data.base_data_key, run_ranges=train_run_ranges, skip_mask=full_data.skip_mask`
   - 测试：`source=full_data.source, base_data_key=full_data.base_data_key, run_ranges=test_run_ranges, skip_mask=full_data.skip_mask`
7. WF 只负责“算索引并传参”；容器切片、mapping 重建、构建期校验都在 `build_data_container` 内完成，不允许 WF 手工拼对象。

### 7.4 窗口坐标示例

参数：`full_data_base_len=2000, train=500, test=200, warmup_bars[base]=50`。

按 `step=test_bars=200` 平移：
- `BorrowFromTrain` 第 0 窗：`TrainWarmup[0,50) Train[50,550) TestWarmup[500,550) Test[550,750)`
- `BorrowFromTrain` 第 1 窗：`TrainWarmup[200,250) Train[250,750) TestWarmup[700,750) Test[750,950)`
- `ExtendTest` 第 0 窗：`TrainWarmup[0,50) Train[50,550) TestWarmup[550,600) Test[600,800)`
- `ExtendTest` 第 1 窗：`TrainWarmup[200,250) Train[250,750) TestWarmup[750,800) Test[800,1000)`

### 7.5 信号注入与执行顺序

1. 预热禁开仓由回测引擎 signal 阶段执行（`signal_preprocessor`）。
2. WF 不重复实现第二套禁开仓逻辑。
3. 测试段执行顺序：
   - 第一次：调用回测引擎入口 `run_single_backtest(...)`，并设置 `engine_settings.execution_stage = ExecutionStage::Signals`（拿信号 + 判定跨窗）。
   - 注入
   - 第二次：注入后直接调用 `backtester::run_backtest(...)` 完成回测，再调用 `performance_analyzer::analyze_performance(...)` 仅对 `data_range` 计算绩效。
4. 注入点固定：
   - 非预热测试段倒数第二根：强制离场（双向）
   - 测试预热段最后一根：跨窗继承开仓
   - 若不满足跨窗判定，则不注入开仓信号。
5. 跨窗判定看上一窗口非预热测试段最后一根：
   - 多头：`entry_long_price` 非 NaN 且 `exit_long_price` 为 NaN
   - 空头：`entry_short_price` 非 NaN 且 `exit_short_price` 为 NaN

### 7.6 绩效字段迁移

1. 【现状复述】存在 `PerformanceMetric::HasLeadingNanCount`（`has_leading_nan_count`）。
2. 【目标口径】删除该指标。
3. 【目标口径】替换为 `warmup_bars_count`，公式：
   `warmup_bars_count = run_ranges[base_data_key].warmup_range.end - run_ranges[base_data_key].warmup_range.start`。
4. 与总口径一致：`has_leading_nan` 仅用于调试。

### 7.7 工程落地顺序（保留）

1. E1：先改窗口索引与四段生成，不动注入链路。
2. E2：再改测试执行链：`Signals(exec_range) -> 注入 -> Backtest(exec_range) -> Performance(data_range)`，并补 stitched 一致性校验。
3. E0（前置）：先完成“指标契约函数 + 指标契约测试”，再进入 E1/E2。

---

## 8. 拼接与资金列

### 8.1 拼接主路径

- 主路径：从每窗 `test_data/test_summary` 提取非预热测试段后拼接。
- 二次校验：与“从全量 `full_data` 一次提取全局连续非预热测试区间”的时间序列一致。

### 8.2 资金列口径

- 窗口内测试段不重建资金列（沿用引擎结果）。
- stitched 必须重建资金列（消除窗口边界伪跳变）。

现有 stitched 资金列重建（保持现状）：
1. 先拼接窗口回测表。
2. 按统一初始资金递推 `balance/equity`。
3. 重算 `total_return_pct/fee_cum/current_drawdown`。
4. 用重建后结果重算 stitched 绩效。

---

## 9. 三层校验链（Fail-Fast）

### 9.1 向前测试层（窗口构建与切片合法性）

- WF 层负责：窗口区间半开合法、索引不越界。
- WF 层负责：非预热测试段固定步长滚动，窗口间不重叠。
- WF 层负责：执行容器必须是“预热+非预热”完整区间。
- WF 层负责：预热段不做覆盖硬校验，按全局 warmup 数量回补。
- WF 层负责：容器与结果切片后必须对齐。
- 构建函数自动负责（`build_data_container` 内部 mapping 流程）：非 base source 只对 `data_range` 做首尾覆盖校验。
- 构建函数自动负责（`build_data_container` 内部 mapping 流程）：`data_range` 映射结果禁止 `null`。
- 构建函数自动负责（构建阶段校验）：`source` 中所有 DataFrame 必须全区间通过 `null/NaN` 校验（任意行不允许 `null/NaN`）。

### 9.2 回测引擎层（指标/信号/回测一致性）

- 指标预热需求只认 `required_warmup_bars(params)`。
- 默认 `allow_internal_nan=false`；非预热段 NaN/null 直接报错。
- `allow_internal_nan=true` 只豁免指定列。
- 信号/回测用预热+非预热，绩效只看非预热。
- 预热段映射不作为业务正确性判定区间。

### 9.3 向前测试层（注入合法性与拼接一致性）

- 注入点唯一。
- 跨窗判定只看上一窗非预热测试段最后一根。
- stitched 时间序列必须通过一致性校验。
- `stitched DataContainer` 与 `stitched BacktestSummary` 长度/时间轴一致。

时间约束：
- 标准路径（`ohlcv`、`Heikin-Ashi`）要求时间严格递增且无重复。
- `renko_*` 允许重复时间戳，映射按“同刻取最后一行”，风险外部承担。

---

## 10. 保持现状说明

本文档同时包含“已落地口径”和“待落地口径”。落地状态以源码和执行文档为准，本文不逐条展开。
