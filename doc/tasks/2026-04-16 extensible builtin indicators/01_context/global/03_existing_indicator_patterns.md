# 现有指标范式

## 1. 模块结构

普通核心指标默认使用以下结构：

```text
src/backtest_engine/indicators/<indicator>/
  config.rs
  expr.rs
  pipeline.rs
  indicator.rs
  mod.rs
```

职责分工：

1. `config.rs` 定义参数、输入列名和输出列名。
2. `expr.rs` 构造 Polars 表达式。
3. `pipeline.rs` 组合 lazy/eager 执行流程，并做参数合法性和数据长度检查。
4. `indicator.rs` 实现 `Indicator` trait，读取 `Param` map，绑定输出列名，返回 `Series`，声明 warmup 契约。
5. `mod.rs` 只做模块导出。

## 2. 注册和分发

指标统一注册在：

```text
src/backtest_engine/indicators/registry.rs
```

运行时通过：

```text
indicator_key.split('_').next()
```

得到 base name，再从 registry 中取指标实现。

示例：

1. `ema_fast` 的 base name 是 `ema`。
2. `bbands_20` 的 base name 是 `bbands`。
3. `opening-bar_0` 的 base name 是 `opening-bar`。
4. `cci-divergence_x` 的 base name 是 `cci-divergence`。

## 3. 输出列命名

单输出指标直接使用 `indicator_key` 作为列名。

多输出指标使用：

```text
<indicator_key>_<suffix>
```

示例：

1. `bbands_0_lower`
2. `bbands_0_middle`
3. `bbands_0_upper`
4. `macd_0_hist`
5. `adx_0_plus_dm`

## 4. warmup 契约

每个指标必须显式实现：

1. `required_warmup_bars(...)`
2. `warmup_mode(...)`

多输出指标按全列口径定义 warmup：所有输出列中前导缺失数量的最大值。

默认使用 `Strict`。只有存在结构性空值且已有测试证明非预热段合法时，才允许使用 `Relaxed`。
