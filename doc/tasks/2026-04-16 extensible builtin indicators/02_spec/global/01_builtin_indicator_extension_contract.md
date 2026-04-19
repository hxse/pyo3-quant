# 内置指标扩展契约

## 1. 唯一路径

新增指标必须进入 Rust 内置指标系统。

正式回测链路中不存在外部自定义指标入口。策略、工作流和回测配置只能声明内置指标参数并消费内置指标输出列。

## 2. 文件结构

新增普通核心指标必须使用：

```text
src/backtest_engine/indicators/<base_name>/
  config.rs
  expr.rs
  pipeline.rs
  indicator.rs
  mod.rs
```

指标存在复杂状态机时，允许在指标目录下增加子模块，但必须保持 `indicator.rs` 作为 trait 实现入口。

## 3. 注册

新增指标必须：

1. 在 `src/backtest_engine/indicators/mod.rs` 声明模块。
2. 在 `src/backtest_engine/indicators/registry.rs` 导入指标类型。
3. 在 registry 初始化中注册 base name。

注册名必须与 `indicators_params` 中的 base name 一致。

## 4. 参数

参数名优先使用正式基准源的参数名。

规则：

1. 必填参数缺失时直接报错。
2. 可选参数必须有唯一默认值。
3. 不为同一语义提供多个别名。
4. 不引入兼容参数。
5. 默认值属于 Rust 指标实现真值，不由外部链路补齐。

## 5. 输出列

单输出指标：

```text
<indicator_key>
```

多输出指标：

```text
<indicator_key>_<suffix>
```

suffix 必须稳定、短、可被信号模板直接引用。

## 6. warmup

每个指标必须声明：

```text
required_warmup_bars
warmup_mode
```

多输出指标按全部输出列的最大前导缺失数量定义 warmup。

默认 `warmup_mode = Strict`。

## 7. 禁止事项

1. 禁止运行时外部自定义指标。
2. 禁止策略局部指标实现。
3. 禁止跳过 registry 直接挂接指标函数。
4. 禁止 silently fallback 到近似指标。
5. 禁止为新指标添加旧名、别名或双轨输出。
