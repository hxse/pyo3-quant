# DataContainer 预热与切片架构（定稿）

本文档只描述新架构与算法，不讨论迁移。
破坏性更新，不保留兼容层，不保留旧接口别名。

---

## 1. 架构目标

1. 只保留一种数据容器：`DataContainer`。
2. 只保留一种结果容器：`BacktestSummary`。
3. 所有范围语义统一到 `run_ranges`。
4. 所有容器构建统一走 `build_data_container`，禁止手工拼对象。
5. 预热静态真值统一走 `resolve_indicator_contracts`，禁止 Python 侧硬编码 warmup/NaN 豁免。

---

## 2. 类型契约

### 2.1 SourceRanges

```rust
pub struct SourceRanges {
    pub warmup_range: (usize, usize),
    pub data_range: (usize, usize),
}
```

约束：
1. 区间都是半开区间 `[start, end)`。
2. 索引是该 `source` 在当前对象中的相对行号。

### 2.2 DataContainer

```rust
pub struct DataContainer {
    pub source: HashMap<String, DataFrame>,
    pub mapping: DataFrame,
    pub skip_mask: Option<DataFrame>,
    pub run_ranges: HashMap<String, SourceRanges>,
    pub base_data_key: String,
}
```

约束：
1. `run_ranges` 的 key 集必须等于 `source` 的 key 集。
2. `mapping` 行数固定等于 base source 行数（全长）。
3. 对象不可变；任何切片必须返回新对象。
4. 不可变按 API 层强约束落地：对外只读，禁止 setter 就地改写。

### 2.3 BacktestSummary

```rust
pub struct BacktestSummary {
    pub run_ranges: HashMap<String, SourceRanges>,
    pub indicators: Option<HashMap<String, DataFrame>>,
    pub signals: Option<DataFrame>,
    pub backtest: Option<DataFrame>,
    pub performance: Option<HashMap<String, f64>>,
}
```

约束：
1. `run_ranges` 与对应 `DataContainer` 语义一致。
2. 任何 summary 切片必须与 container 成对切片。

---

## 3. 指标契约导出（唯一入口）

### 3.1 函数签名

```rust
pub fn resolve_indicator_contracts(
    indicators_params: &IndicatorsParams,
    base_data_key: &str,
) -> Result<IndicatorContractSnapshot, QuantError>;
```

### 3.2 返回结构（对外硬契约）

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

### 3.3 计算规则

1. 每个指标必须实现：
   - `required_warmup_bars(params) -> usize`
   - `allow_internal_nan() -> bool`
2. 取参规则固定：`optimize=true` 取 `max`，`optimize=false` 取 `value`。
3. 同一 source 多指标 warmup 取最大值，不求和。
4. 不做跨周期比例换算，不做网络补齐，不做覆盖校验。
5. `required_warmup_dict` 是聚合结果；`indicator_contracts` 是明细结果。
6. `required_warmup_bars` 必须精确匹配当前 Rust 指标实现行为（按现有实现对齐，不做理论重写）。

### 3.4 当前 registry warmup 基线（与现实现行代码对齐）

1. `sma/ema/cci/bbands/sma-close-pct`：`period - 1`
2. `rma`（standalone）：`0`
3. `rsi/atr`：`period`
4. `tr`：`1`
5. `macd`：`max(fast, slow) + signal - 2`
6. `adx`：`2 * period - 1`
7. `er`：`length`
8. `psar`：`1`
9. `opening-bar`：`0`
10. `cci-divergence/rsi-divergence/macd-divergence`：对应底层 `_value` 列的 warmup（不额外叠加 divergence window）

---

## 4. Mapping 与覆盖校验

### 4.1 结构语义

1. `mapping` 全长保留（base 行数全长）。
2. 业务硬校验只绑定非预热段（`data_range`）。
3. 预热段允许覆盖不完整，不作为覆盖正确性判定区间。

### 4.2 构建期硬校验（Fail-Fast）

在 `build_data_container` 的 mapping 构建流程内执行：

1. 非预热段首尾覆盖：
   - `source_start_time <= base_data_start_time`
   - `source_end_time + source_interval > base_data_end_time`
2. 非预热段映射结果禁止 `null`。
3. `base_data_key` 必须是最小周期；发现更高频 source 直接报错。
4. `source` 中所有 DataFrame 全区间禁止 `null/NaN`（原始输入数据完整性校验，不是指标输出校验）。
5. 任一校验失败立即报错。

### 4.3 数据源边界

1. 标准路径：`ohlcv`、`Heikin-Ashi`。
2. `renko_*` 允许接入，但风险外部承担。
3. `renko_*` 映射仍按 `join_asof(backward)`，同一时刻多行取最后一行。
4. 任何 `source_interval_ms` 的补拉估算只保证等间距序列；`renko_*` 不保证估算可靠性。

---

## 5. 统一构建函数

### 5.1 签名

```rust
pub fn build_data_container(
    source: HashMap<String, DataFrame>,
    base_data_key: String,
    run_ranges: HashMap<String, SourceRanges>,
    skip_mask: Option<DataFrame>,
) -> Result<DataContainer, QuantError>;
```

签名外隐式依赖（统一内建，不额外暴露参数）：
1. 每个 source DataFrame 必须存在 `time:Int64` 且无 `null`。
2. `base_data_key` 必须存在于 `source`。
3. source 周期解析统一复用一个通用解析函数；解析失败直接报错。
4. mapping 一律按 `join_asof(backward)` 等价逻辑重建。

### 5.2 构建语义

1. 按 `run_ranges[source]` 切片 `source`（Polars copy，浅拷贝语义）。
2. 按 base 执行区间切片 `skip_mask`（若存在）。
3. 基于切片后 `source` 重建 `mapping`。
4. 在 mapping 流程中执行覆盖与完整性校验（见第 4 节）。

### 5.3 Python 与 WF 复用

1. Python：构建全量执行容器。
2. WF：每窗调用两次，分别构建训练与测试执行容器。

---

## 6. 切片与拼接接口

### 6.1 base 区间切片（唯一切片口径）

```rust
pub fn slice_container_by_base_range(...);
pub fn slice_summary_by_base_range(...);
pub fn slice_pair_by_base_range(...);
```

规则：
1. `base_range` 使用输入容器 base source 的本地相对坐标。
2. 切片后 `run_ranges` 统一重算到新对象本地坐标。
3. `DataContainer + BacktestSummary` 必须成对切片。
4. 用途：画图/展示与窗口结果消费，不进入回测/WF 主执行链。

### 6.2 拼接

```rust
pub fn concat_data_containers(inputs: &[DataContainer]) -> Result<DataContainer, QuantError>;
pub fn concat_backtest_summaries(inputs: &[BacktestSummary]) -> Result<BacktestSummary, QuantError>;
```

规则：
1. 拼接输入必须 schema 一致、时间序列严格递增。
2. stitched 产物统一语义为非预热拼接结果（`warmup_range=(0,0)`）。

---

## 7. 回测执行口径

### 7.1 执行阶段

沿用现有 `ExecutionStage`：

```rust
pub enum ExecutionStage {
    Idle,
    Indicator,
    Signals,
    Backtest,
    Performance,
}
```

### 7.2 语义

1. 指标/信号/回测使用预热+非预热全执行区间。
2. 绩效仅统计 `run_ranges[base].data_range`。
3. 预热禁开仓在 signal 阶段执行（`signal_preprocessor`）。
4. `has_leading_nan` 仅保留调试用途，不参与业务逻辑。

### 7.3 NaN 策略

1. 默认 `allow_internal_nan=false`：非预热段出现 NaN/null 直接失败。
2. `allow_internal_nan=true`：只对该指标实例放宽非预热段 NaN/null，仍需保证非整段无效。

---

## 8. PyO3 对外接口（与 `pyo3_interface_design.md` 对齐）

必须暴露并统一使用：

1. `resolve_indicator_contracts(...)`
2. `build_data_container(...)`
3. `slice_container_by_base_range(...)`
4. `slice_summary_by_base_range(...)`
5. `slice_pair_by_base_range(...)`
6. `concat_data_containers(...)`
7. `concat_backtest_summaries(...)`

禁止：
1. Python 侧硬编码 warmup/allow_internal_nan。
2. Python 侧重复实现 mapping/覆盖校验算法。
3. Python 侧拆开 data/summary 分别切片。

---

## 9. 校验链分责

1. 构建层（`build_data_container`）：覆盖校验、映射非空校验、source 完整性校验。
2. 回测引擎层：指标/信号/回测/绩效阶段口径一致性。
3. WF 编排层：窗口索引合法性、注入点合法性、拼接一致性。

所有校验 Fail-Fast，直接报错。

---

## 10. 非目标范围

1. 不讨论旧架构迁移步骤。
2. 不提供兼容层。
3. 不定义 `ohlcv/Heikin-Ashi` 之外数据源的安全语义。
