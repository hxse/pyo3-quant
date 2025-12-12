# 指标命名规则文档

## 概述

本文档总结了 pyo3-quant 项目中指标名称的生成规则。指标名称由两部分组成：基础指标名和用户定义的标识符，通过下划线连接。

## 基本命名规则

### 指标键名结构

指标键名采用 `{基础指标名}_{标识符}` 的格式，其中：
- 基础指标名：指标的类型（如 sma、rsi、bbands 等）
- 标识符：用户自定义的字符串，可以是数字（如 0、1、2 等）或描述性字符串（如 fast、slow 等）

示例：
- `sma_0`：第一个SMA指标
- `sma_1`：第二个SMA指标
- `sma_fast`：快速SMA指标
- `sma_slow`：慢速SMA指标
- `sma`：简化的SMA指标（允许省略标识符）
- `bbands_upper`：简化的布林带上轨引用（允许省略标识符）

### 指标输出列名规则

每个指标会生成一个或多个输出列，列名遵循以下规则：
- 单输出指标：`{指标键名}`
- 多输出指标：`{指标键名}_{输出组件名}`

## 各指标详细命名规则

### 单输出指标

#### SMA（简单移动平均线）
- 指标键名：`sma_{标识符}`
- 输出列名：`sma_{标识符}`
- 输入参数：
  - `period`: 计算周期（整数，必须为正数）
- 示例：`sma_0`

#### EMA（指数移动平均线）
- 指标键名：`ema_{标识符}`
- 输出列名：`ema_{标识符}`
- 输入参数：
  - `period`: 计算周期（整数，必须为正数）
- 示例：`ema_0`

#### RSI（相对强弱指数）
- 指标键名：`rsi_{标识符}`
- 输出列名：`rsi_{标识符}`
- 输入参数：
  - `period`: 计算周期（整数，必须为正数）
- 示例：`rsi_0`

#### ATR（平均真实波幅）
- 指标键名：`atr_{标识符}`
- 输出列名：`atr_{标识符}`
- 输入参数：
  - `period`: 计算周期（整数，必须为正数）
- 示例：`atr_0`

#### TR（真实波幅）
- 指标键名：`tr_{标识符}`
- 输出列名：`tr_{标识符}`
- 输入参数：无（使用默认的 high、low、close 列）
- 示例：`tr_0`

#### RMA（运行移动平均）
- 指标键名：`rma_{标识符}`
- 输出列名：`rma_{标识符}`
- 输入参数：
  - `period`: 计算周期（整数，必须为正数）
- 示例：`rma_0`

#### SMA-Close-PCT（收盘价相对于SMA的百分比）
- 指标键名：`sma-close-pct_{标识符}`
- 输出列名：`sma-close-pct_{标识符}`
- 输入参数：
  - `period`: SMA计算周期（整数，必须为正数）
- 示例：`sma-close-pct_0`

### 多输出指标

#### 布林带（Bollinger Bands）
- 指标键名：`bbands_{标识符}`
- 输出列名：
  - `bbands_{标识符}_lower`：下轨
  - `bbands_{标识符}_middle`：中轨
  - `bbands_{标识符}_upper`：上轨
  - `bbands_{标识符}_bandwidth`：带宽
  - `bbands_{标识符}_percent`：%B
- 输入参数：
  - `period`: 计算周期（整数，必须为正数）
  - `std`: 标准差倍数（浮点数）
- 示例：`bbands_0_lower`、`bbands_0_middle`、`bbands_0_upper`等

#### MACD（移动平均收敛散度）
- 指标键名：`macd_{标识符}`
- 输出列名：
  - `macd_{标识符}_macd`：MACD线
  - `macd_{标识符}_signal`：信号线
  - `macd_{标识符}_hist`：柱状图
- 输入参数：
  - `fast_period`: 快速EMA周期（整数，必须为正数）
  - `slow_period`: 慢速EMA周期（整数，必须为正数）
  - `signal_period`: 信号线EMA周期（整数，必须为正数）
- 示例：`macd_0_macd`、`macd_0_signal`、`macd_0_hist`

#### ADX（平均方向性指数）
- 指标键名：`adx_{标识符}`
- 输出列名：
  - `adx_{标识符}_adx`：ADX值
  - `adx_{标识符}_adxr`：ADXR值
  - `adx_{标识符}_plus_dm`：正向动向指标
  - `adx_{标识符}_minus_dm`：负向动向指标
- 输入参数：
  - `period`: ADX计算周期（整数，必须为正数）
  - `adxr_length`: ADXR计算周期（整数，必须为正数，默认值为2）
- 示例：`adx_0_adx`、`adx_0_adxr`、`adx_0_plus_dm`、`adx_0_minus_dm`

#### PSAR（抛物线SAR）
- 指标键名：`psar_{标识符}`
- 输出列名：
  - `psar_{标识符}_long`：多头PSAR值
  - `psar_{标识符}_short`：空头PSAR值
  - `psar_{标识符}_af`：加速因子
  - `psar_{标识符}_reversal`：反转信号
- 输入参数：
  - `af0`: 初始加速因子（浮点数）
  - `af_step`: 加速因子步长（浮点数）
  - `max_af`: 最大加速因子（浮点数）
- 示例：`psar_0_long`、`psar_0_short`、`psar_0_af`、`psar_0_reversal`

## 多时间框架指标命名

在多时间框架设置中，指标键名会与数据源名称结合使用：

在信号条件中引用这些指标时，使用格式：`{指标键名},{数据源名},{offset}`

**重要规则**：`indicators_params` 中定义的指标键名和信号条件中引用的指标键名必须完全一致。

其中：
- 指标键名：必须与 `indicators_params` 中定义的键名完全一致
- 数据源名：如 `ohlcv_15m`、`ohlcv_1h` 等
- offset：偏移量，表示引用前几根K线的数据，0表示当前K线，1表示前一根K线，以此类推

#### 引用示例

```python
indicators_params = {
    "ohlcv_15m": {
        "bbands": {           # 省略标识符
            "period": Param.create(14),
            "std": Param.create(2),
        },
        "macd_0": {          # 带标识符
            "fast_period": Param.create(12),
            "slow_period": Param.create(26),
            "signal_period": Param.create(9),
        }
    }
}
```
信号引用：
- `bbands_upper,ohlcv_15m,0`    # 正确：匹配 "bbands" 定义
- `bbands_middle,ohlcv_15m,0`  # 正确：匹配 "bbands" 定义
- `macd_0_macd,ohlcv_15m,0`    # 正确：匹配 "macd_0" 定义
- `macd_0_signal,ohlcv_15m,0`  # 正确：匹配 "macd_0" 定义
- `bbands_0_upper,ohlcv_15m,0`  # 错误：定义的是 "bbands"，不是 "bbands_0"
- `macd_signal,ohlcv_15m,0`  # 错误：定义的是 "macd_0"，不是 "macd"
- `macd_0,ohlcv_15m,0`  # 错误：没有输出列名


#### 关键规则
1. **完全匹配**：信号引用的指标键名必须与 `indicators_params` 中定义的键名完全一致
2. **输出组件**：在指标键名后添加 `_{输出组件名}` 来引用特定的输出列
3. **无第二种写法**：不存在简化的替代写法，只有一种正确的引用方式


## 注意事项

1. **标识符唯一性**：在同一数据源内，标识符应该是唯一的，避免指标键名冲突

2. **命名一致性**：可以使用数字（如 0、1、2）或描述性字符串（如 fast、slow）作为标识符。建议在同一项目中保持命名风格的一致性

3. **标识符省略规则**：
   - **单输出指标**：可以省略标识符，直接使用基础指标名（如 `sma` 而不是 `sma_0`）
   - **多输出指标**：在信号引用中必须使用 `{指标定义键名}_{输出组件名}`
   - **一致性要求**：指标定义的键名和信号引用的键名必须完全一致
   - **无简化写法**：不存在第二种写法，只有一种正确的引用方式

4. **信号引用**：在信号条件中引用指标时，必须同时指定指标键名和数据源名，格式为 `{指标键名},{数据源名}`

5. **扩展性**：添加新指标时，应遵循现有的命名规则，确保与系统的一致性

6. **实现原理**：详见文末的"实现细节"章节



## 实现细节

### 指标键名解析

在 `src/backtest_engine/indicators/mod.rs` 的 `calculate_single_period_indicators` 函数中：

```rust
let base_name = indicator_key.split('_').next().unwrap_or(indicator_key);
```

这段代码通过下划线分割指标键名，获取基础指标名用于在指标注册表中查找对应的指标实现。

### 指标输出列名生成

每个指标的 `Indicator` 实现中的 `calculate` 方法负责生成最终的输出列名。通常通过以下方式：

```rust
config.alias_name = indicator_key.to_string();
```

或者对于多输出指标：

```rust
config.middle_band_alias = format!("{}_middle", indicator_key);
config.upper_band_alias = format!("{}_upper", indicator_key);
config.lower_band_alias = format!("{}_lower", indicator_key);
// ...
```

### 指标键名解析机制

在 `src/backtest_engine/indicators/mod.rs` 的 `calculate_single_period_indicators` 函数中：

```rust
let base_name = indicator_key.split('_').next().unwrap_or(indicator_key);
```

这段代码通过下划线分割指标键名，获取基础指标名用于在指标注册表中查找对应的指标实现。

### 信号解析机制

在信号解析中（`src/backtest_engine/signal_generator/operand_resolver.rs`），系统会直接尝试从指标结果 DataFrame 中查找完整的列名，因此支持省略标识符的简化写法。
