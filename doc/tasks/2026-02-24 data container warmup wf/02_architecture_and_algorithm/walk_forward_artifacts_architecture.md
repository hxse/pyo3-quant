# Walk-Forward 产物与算法架构（定稿）

本文档只描述新架构与算法，不讨论迁移。
破坏性更新，不保留兼容层，不保留旧 transition 写法。

---

## 1. 核心结论

1. 删除 `transition_bars` 语义。
2. 每窗四段固定：`TrainWarmup / Train / TestWarmup / Test`。
3. 回测引擎只接收 `DataContainer`。
4. 测试链固定：`Signals -> 注入 -> run_backtest -> analyze_performance`。
5. 输出统一为：
   - `window_results`: 每窗非预热测试段
   - `stitched_result`: 所有窗口非预热测试段拼接
6. WF 不在内部调用 `resolve_indicator_contracts`，只消费入口 `full_data.run_ranges`。

---

## 2. 输入输出契约

### 2.1 输入

```rust
pub struct WalkForwardConfig {
    pub train_bars: usize,
    pub test_bars: usize,
    pub test_warmup_source: TestWarmupSource,
    pub inherit_prior: bool,
    pub optimizer_config: OptimizerConfig,
}

pub enum TestWarmupSource {
    BorrowFromTrain,
    ExtendTest,
}
```

```rust
pub fn run_walk_forward(
    full_data: &DataContainer,
    param: &SingleParamSet,
    template: &TemplateContainer,
    settings: &SettingContainer,
    config: &WalkForwardConfig,
) -> Result<WalkForwardResult, QuantError>;
```

输入约束：
1. `full_data` 是入口全量容器（含预热+非预热）。
2. 不允许在 WF 内做网络请求。
3. 不允许在 WF 内重新解析指标 warmup 契约。

### 2.2 中间对象

```rust
pub struct WindowItem {
    pub train_data: DataContainer,
    pub test_data: DataContainer,
    pub train_summary: BacktestSummary,
    pub test_summary: BacktestSummary,
}
```

### 2.3 输出对象

```rust
pub struct WindowArtifact {
    pub data: DataContainer,      // 当前窗口非预热 Test 段
    pub summary: BacktestSummary, // 当前窗口非预热 Test 段
    pub window_id: usize,
    pub has_cross_window_position: bool,
}

pub struct StitchedArtifact {
    pub data: DataContainer,      // 所有窗口非预热 Test 段拼接
    pub summary: BacktestSummary, // 所有窗口非预热 Test 段拼接
    pub window_count: usize,
}

pub struct WalkForwardResult {
    pub window_results: Vec<WindowArtifact>,
    pub stitched_result: StitchedArtifact,
}
```

### 2.4 破坏性字段变更（明确清单）

旧 `WindowArtifact` 字段中，以下字段不再保留：
1. `time_range`
2. `bar_range`
3. `span_ms`
4. `span_days`
5. `span_months`
6. `bars`
7. `train_range`
8. `transition_range`
9. `test_range`
10. `best_params`
11. `optimize_metric`

新口径仅保留：
1. `data`
2. `summary`
3. `window_id`
4. `has_cross_window_position`

---

## 3. 预热来源模式

1. `BorrowFromTrain`：`TestWarmup` 与训练尾部重叠借用，窗口更紧凑。
2. `ExtendTest`：`TestWarmup` 不借用训练尾部，窗口更隔离。
3. 两种模式都要求窗口连续无间隙。
4. 两种模式都执行“预热+非预热”；返回只保留非预热测试段。

---

## 4. 窗口索引算法（模板 + 平移）

### 4.1 全局约束

1. 不区分第一窗/后续窗，统一同一套算法。
2. 步长固定：`step = test_bars`。
3. base 预热归一：`warmup_bars[base] = max(warmup_bars[base], 1)`。

### 4.2 第 0 窗模板

设：`warmup = warmup_bars[base]`。

`BorrowFromTrain`：
1. `TrainWarmup[0, warmup)`
2. `Train[warmup, warmup + train_bars)`
3. `TestWarmup[train_bars, warmup + train_bars)`
4. `Test[warmup + train_bars, warmup + train_bars + test_bars)`

补充说明：
1. `BorrowFromTrain` 下 `TestWarmup` 与 `Train` 尾部重叠 `warmup` 根，这是有意借用，不是 bug。
2. 两种模式都保证窗口连续无间隙。

`ExtendTest`：
1. `TrainWarmup[0, warmup)`
2. `Train[warmup, warmup + train_bars)`
3. `TestWarmup[warmup + train_bars, 2 * warmup + train_bars)`
4. `Test[2 * warmup + train_bars, 2 * warmup + train_bars + test_bars)`

### 4.3 第 w 窗平移

1. `delta = w * step`。
2. 任意模板区间 `[start_0, end_0)` 平移为 `[start_0 + delta, end_0 + delta)`。

### 4.4 source 范围构建

1. 先把 base 的 `Train/Test` 投影到每个 source，得到 `data_range`。
2. 不直接映射预热段。
3. 对每个 source 回补预热：
   - `train_warmup_range = [max(0, train_data_start - warmup_bars[source]), train_data_start)`
   - `test_warmup_range = [max(0, test_data_start - warmup_bars[source]), test_data_start)`
4. 组装 `train_run_ranges` 与 `test_run_ranges`。

投影规则（固定算法）：
1. 只用 base 的 `Train/Test`（非预热段）切 mapping。
2. 对每个 source 映射列取非空索引 `min/max`。
3. 回写半开区间时用 `[min, max+1)`，避免 off-by-one。
4. 伪代码：
   - `mapped = mapping.slice(base_data_range).column(source_key).drop_nulls()`
   - `src_data_start = mapped.min()`
   - `src_data_end = mapped.max() + 1`
   - `data_range[source_key] = [src_data_start, src_data_end)`
5. 约束：base 必须是最小周期；不支持 `source` 比 base 更高频的执行语义。

### 4.5 构建执行容器

每窗调用两次：
1. `build_data_container(full_data.source, full_data.base_data_key, train_run_ranges, full_data.skip_mask)`
2. `build_data_container(full_data.source, full_data.base_data_key, test_run_ranges, full_data.skip_mask)`

WF 只负责“算索引并传参”，不手工拼容器。

---

## 5. 单窗口执行链

### 5.1 训练路径

1. 用训练执行容器进入优化器。
2. 优化器内部复用回测主链，产出 `best_params` 与 `train_summary`。

### 5.2 测试路径

1. 第一次调用入口：
   - `run_single_backtest(...)`
   - `engine_settings.execution_stage = ExecutionStage::Signals`
   - 只拿信号并做跨窗判定
2. 做信号注入。
3. 第二次直接函数调用：
   - `backtester::run_backtest(...)`
   - `performance_analyzer::analyze_performance(...)`（仅 `data_range`）

硬约束：
1. 禁止“注入后不回测”。
2. 禁止“先完整回测再改信号”。
3. `run_backtest` 输入必须是测试执行全区间（预热+非预热）。
4. `analyze_performance` 仅统计非预热测试段。

---

## 6. 跨窗注入规则

### 6.1 判定条件

只看上一窗非预热测试段最后一根：
1. 多头跨窗：`entry_long_price` 非 NaN 且 `exit_long_price` 为 NaN。
2. 空头跨窗：`entry_short_price` 非 NaN 且 `exit_short_price` 为 NaN。

### 6.2 注入点

1. 强制离场：当前窗非预热测试段倒数第二根（双向）。
2. 继承开仓：当前窗 `TestWarmup` 最后一根。
3. 若不满足跨窗判定，不注入开仓。
4. 边界保护：
   - `test` 长度必须 `>= 2`，否则直接报错；
   - `test_warmup` 长度必须 `>= 1`，否则直接报错；
   - 第一窗没有上一窗状态，跳过继承开仓注入。

---

## 7. 产物生成与拼接

### 7.1 window_results

1. 从 `test_data/test_summary` 提取本地 `data_range`（非预热测试段）。
2. 构造 `WindowArtifact`。

坐标约束：
1. 使用 `test_data.run_ranges[base].data_range` 本地坐标。
2. 禁止误用 `full_data` 全局坐标。

### 7.2 stitched_result

主路径：
1. 按时间顺序拼接各窗非预热 `data`（`concat_data_containers`）。
2. 按时间顺序拼接各窗非预热 `summary`（`concat_backtest_summaries`）。
3. stitched 阶段重建资金列并重算 stitched 绩效。
4. 资金列重建规则（复用现有函数，不重写算法）：
   - 复用 `rebuild_capital_columns_for_stitched_backtest_with_boundaries`
   - stitched 首行以全局初始资金为起点
   - 后续行按拼接后时间顺序递推 `balance/equity`
   - 重算 `total_return_pct/fee_cum/current_drawdown` 后再计算 stitched 绩效

二次一致性校验：
1. 从入口 `full_data` 一次提取全局连续 OOS 区间。
2. 仅比较 `time` 列一致性。
3. 不一致直接报错。

---

## 8. 校验分责

1. `build_data_container`：覆盖校验、映射非空校验、source 完整性校验。
2. 回测引擎：预热禁开仓、执行阶段口径一致性。
3. WF：窗口合法性、注入点合法性、拼接一致性。

全部 Fail-Fast。

---

## 9. PyO3 边界

对齐 `doc/structure/pyo3_interface_design.md`：

1. 对外入口保持 `run_walk_forward(...) -> WalkForwardResult`。
2. Python 只做参数编排与结果消费，不重写窗口/注入算法。
3. 画图/展示统一调用 Rust 成对切片函数。

---

## 10. 非目标范围

1. 不讨论旧 transition 架构迁移步骤。
2. 不提供兼容写法。
3. 不定义非标准数据源的额外安全语义。
