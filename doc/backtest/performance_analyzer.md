# 绩效分析模块文档

本文档描述绩效分析模块的设计与实现。

---

## 1. 模块概览

绩效分析模块负责根据回测结果计算一系列量化评估指标。

**位置**: `src/backtest_engine/performance_analyzer/`

**结构**:
```
performance_analyzer/
├── mod.rs       # 主入口，协调数据流和指标汇总
├── metrics.rs   # 风险调整指标计算（年化收益、夏普等）
└── stats.rs     # 交易统计与时长统计
```

---

## 2. 输入数据

绩效分析需要以下输入：

| 输入 | 来源 | 说明 |
|------|------|------|
| `processed_data` | `DataContainer` | 原始 OHLCV 数据，用于提取 `time` 列计算年化因子 |
| `backtest_df` | 回测输出 DataFrame | 含 `equity`, `trade_pnl_pct`, `current_drawdown` 等列 |
| `performance_params` | 用户参数 | 指定需要计算的指标列表和无风险利率 |

### 关键列

| 列名 | 类型 | 说明 |
|------|------|------|
| `equity` | f64 | 每根 K 线的净值 |
| `trade_pnl_pct` | f64 | 该 Bar 的交易盈亏百分比（非零表示有成交） |
| `current_drawdown` | f64 | 当前回撤比例 |
| `entry_long_price` | f64 | 多头持仓价格（NaN 表示无仓位） |
| `entry_short_price` | f64 | 空头持仓价格 |
| `has_leading_nan` | bool | 无效数据标记，用于统计预热期长度 |

---

## 3. 输出指标

### 3.1 收益与统计指标

| 指标 | 键名 | 公式/说明 |
|------|------|----------|
| 总回报率 | `total_return` | 最后一行 `total_return_pct` |
| 年化因子 | `annualization_factor` | `n / time_span_years` |
| 信号无效计数 | `has_leading_nan_count` | `backtest_df` 中 `has_leading_nan` 为 True 的总行数 |

### 3.2 风险调整指标

| 指标 | 键名 | 公式 |
|------|------|------|
| 夏普比率 | `sharpe_ratio` | `(mean_ret × ann_factor - rf) / (std_ret × √ann_factor)` |
| 索提诺比率 | `sortino_ratio` | 同夏普，分母仅用下行波动率 |
| 卡尔马比率 | `calmar_ratio` | `annualized_return / MDD` |
| 非年化夏普比率 | `sharpe_ratio_raw` | `(mean_ret - rf_per_bar) / std_ret` |
| 非年化索提诺比率 | `sortino_ratio_raw` | 同上，分母仅用下行波动率 |
| 非年化卡尔马比率 | `calmar_ratio_raw` | `total_return / MDD` |

### 3.3 回撤指标

| 指标 | 键名 | 说明 |
|------|------|------|
| 最大回撤 | `max_drawdown` | `max(current_drawdown)` |
| 最大回撤持续时长 | `max_drawdown_duration` | 连续 `current_drawdown > 0` 的最长 Bar 数 |
| 最大可承受杠杆 | `max_safe_leverage` | `safety_factor / max_drawdown` |

### 3.4 交易统计

| 指标 | 键名 | 说明 |
|------|------|------|
| 总交易次数 | `total_trades` | `trade_pnl_pct ≠ 0` 的行数 |
| 日均交易次数 | `avg_daily_trades` | `total_trades / days` |
| 胜率 | `win_rate` | 盈利交易数 / 总交易数 |
| 盈亏比 | `profit_loss_ratio` | 平均盈利 / 平均亏损（绝对值） |

### 3.5 时长统计

| 指标 | 键名 | 说明 |
|------|------|------|
| 平均持仓时长 | `avg_holding_duration` | 连续持仓 Bar 数的平均值 |
| 最大持仓时长 | `max_holding_duration` | 单次最长持仓 Bar 数 |
| 平均空仓时长 | `avg_empty_duration` | 连续空仓 Bar 数的平均值 |
| 最大空仓时长 | `max_empty_duration` | 单次最长空仓 Bar 数 |

---

## 4. 年化因子自动推断

模块会根据 `time` 列自动计算年化因子：

```
time_span_ms = time[last] - time[first]
time_span_years = time_span_ms / (365.25 * 24 * 3600 * 1000)
annualization_factor = n / time_span_years
```

例如：15 分钟 K 线数据，一年约有 35,040 根 K 线。

---

## 5. 持仓状态判断

持仓状态通过 `entry_long_price` 和 `entry_short_price` 判断：

```rust
let long_active = entry_long.get(i).map(|v| !v.is_nan()).unwrap_or(false);
let short_active = entry_short.get(i).map(|v| !v.is_nan()).unwrap_or(false);
let is_active = long_active || short_active;
```

- **持仓中**: 对应方向的 entry_price 为有效值（非 NaN）
- **空仓中**: 两个方向均为 NaN

---

## 6. 矢量化实现

### 交易统计 (`stats.rs::calculate_trade_stats`)

使用 Polars `ChunkedArray<Float64Type>` 操作实现矢量化：

```rust
// 过滤非零收益（代表已关闭的交易）
let closed_trades = trade_pnl_pct.filter(&trade_pnl_pct.not_equal(0.0)).unwrap();

// 盈利和亏损交易
let wins = closed_trades.filter(&closed_trades.gt(0.0)).unwrap();
let losses = closed_trades.filter(&closed_trades.lt(0.0)).unwrap();

// 计算胜率和盈亏比
let win_rate = wins.len() as f64 / closed_trades.len() as f64;
let profit_loss_ratio = wins.mean().unwrap_or(0.0) / losses.mean().unwrap_or(0.0).abs();
```

### 时长统计 (`stats.rs::calculate_duration_stats`)

由于涉及状态机切换检测，持仓/空仓时长仍使用**线性扫描**，时间复杂度为 O(n)。

### 最大回撤时长 (`stats.rs::calculate_max_drawdown_duration_vect`)

> [!NOTE]
> 虽然函数名含 `_vect`，但由于 Polars RLE 插件可用性问题，实际实现仍使用**线性扫描**作为回退方案。


---

## 7. Python 接口

### 7.1 推荐方式：通过 Backtest（使用 dataclass）

```python
from py_entry.runner import Backtest
from py_entry.types import PerformanceParams, PerformanceMetric

# 使用 dataclass 构造绩效参数
performance_params = PerformanceParams(
    metrics=[
        PerformanceMetric.TotalReturn,
        PerformanceMetric.MaxDrawdown,
        PerformanceMetric.SharpeRatio,
        PerformanceMetric.CalmarRatio,
        PerformanceMetric.AnnualizationFactor,
        PerformanceMetric.HasLeadingNanCount,
    ],
    risk_free_rate=0.02,         # 2% 无风险利率
    leverage_safety_factor=0.8,  # 杠杆安全系数
)

# 通过 Backtest 执行回测后自动调用绩效分析
run_result = Backtest(..., performance=performance_params).run()
result = run_result.summary.performance if run_result.summary else None
# result: dict[str, float]
# 例如 {"total_return": 0.25, "max_drawdown": 0.15, "sharpe_ratio": 1.5, ...}
```

### 7.2 底层接口：直接调用 pyo3_quant

```python
from pyo3_quant import analyze_performance

# 也可以使用 dict 格式（PyO3 会自动转换）
performance_params = {
    "metrics": ["total_return", "max_drawdown", "sharpe_ratio"],
    "risk_free_rate": 0.02,
    "leverage_safety_factor": 0.8,
}

result = analyze_performance(data_dict, backtest_df, performance_params)
```

**参数类型**：
- `data_dict`: `DataContainer` (含 `base_data_key` 和 `source`)
- `backtest_df`: `polars.DataFrame` (回测引擎输出)
- `performance_params`: `PerformanceParams` (dataclass 或 dict)

**返回值**：
- `dict[str, float]`: 指标名到指标值的映射

> [!TIP]
> 完整的 Python 接口文档请参考 [python_api.md](./python_api.md)。
