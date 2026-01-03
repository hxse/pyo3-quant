# Runner 使用场景文档

本文档梳理了 `BacktestRunner` (或重构后的 `Backtest`) 类的所有使用场景，作为 API 设计的参考依据。

---

## 场景概览

| 场景 | 核心操作 | 参数需求 | 后续操作 |
|------|---------|---------|---------|
| 1. 快速验证 | `run()` | 单个 | `display()` |
| 2. 正式回测 | `run()` | 单个 | `format()` → `save()` → `display()` |
| 3. 参数优化 | `optimize()` | 单个(内部扩展) | 查看 `best_params` |
| 4. 优化后详细回测 | `optimize()` → `run()` | 单个 + 参数覆盖 | `display()` |
| 5. 向前测试 | `walk_forward()` | 单个(内部扩展) | 查看稳健性 |
| 6. 向前测试后详细回测 | `walk_forward()` → `run()` | 单个 + 参数覆盖 | `display()` |
| 7. 全局优化 + 向前测试 | `optimize()` → `walk_forward()` | 单个 + 参数覆盖 | 验证泛化能力 |
| 8. 自定义优化器(批量并发) | `batch()` | 参数列表 | 分析比较 |
| 9. Notebook 交互探索 | 分步 `run()` | 灵活覆盖 | 各种 |

---

## 场景详解

### 场景 1：快速验证策略逻辑

**目标**：验证策略代码是否正确运行，看基本的回测曲线

**用户心理**：*"我刚写完策略，想快速看看能不能跑通"*

```python
br = Backtest(data, params, template)
result = br.run()
result.display()  # 直接看图
```

**特点**：
- 只需要单次回测
- 需要看图表 (`display`)
- 不需要保存

---

### 场景 2：正式回测 + 保存结果

**目标**：完整回测一次，保存结果供以后分析

**用户心理**：*"策略确认没问题，正式跑一次并保存"*

```python
br = Backtest(data, params, template)
result = br.run()
result.format_for_export(config)
      .save(path)
      .upload(server)  # 可选
      .display()
```

**特点**：
- 单次回测
- 需要格式化导出
- 需要保存/上传
- 可能需要显示

---

### 场景 3：参数优化

**目标**：找到最优参数组合

**用户心理**：*"策略逻辑 OK，但不知道最优参数是什么"*

```python
br = Backtest(data, params, template)  # params 包含参数范围（如 Param.create(14, 10, 20, 2)）
opt_result = br.optimize(config)

# 查看优化结果
print(opt_result.best_params)
print(opt_result.summary_table)  # 所有参数组合的结果表
```

**特点**：
- 基于单个参数的范围定义，优化器内部自动扩展参数组合
- 关注最优参数是什么
- 可能需要导出优化过程的表格

---

### 场景 4：优化后详细回测

**目标**：用最优参数跑一次完整回测，查看详细图表

**用户心理**：*"找到最优参数了，想看这个参数的详细回测曲线"*

```python
br = Backtest(data, params, template)
opt_result = br.optimize(config)

# 用最优参数再跑一次详细回测
detailed = br.run(params_override=opt_result.best_params)
detailed.display()  # 看详细图表
detailed.save(path) # 保存详细数据
```

**特点**：
- 分两步：优化 → 详细回测
- 需要复用同一个 `br` 实例（避免重复加载数据）
- 需要用优化结果的参数覆盖

---

### 场景 5：向前测试（Walk Forward）

**目标**：验证参数在未来数据上的稳健性

**用户心理**：*"参数优化结果可能过拟合，需要验证稳健性"*

```python
br = Backtest(data, params, template)
wf_result = br.walk_forward(config)

# 查看向前测试结果
print(wf_result.is_robust)  # 是否稳健
wf_result.display()  # 显示滚动窗口的表现
```

**特点**：
- 基于单个参数的范围
- 关注参数稳健性
- 有独立的结果结构

---

### 场景 6：向前测试后详细回测

**目标**：用向前测试推荐的参数跑详细回测

**用户心理**：*"向前测试通过了，用推荐参数看详细图表"*

```python
br = Backtest(data, params, template)
wf_result = br.walk_forward(config)

# 用推荐参数详细回测
detailed = br.run(params_override=wf_result.recommended_params)
detailed.display()
detailed.save(path)
```

**特点**：
- 分两步：向前测试 → 详细回测
- 复用同一个实例

---

### 场景 7：全局优化 + 向前测试验证

**目标**：先用全局优化找到候选参数，再用向前测试验证其泛化能力

**用户心理**：*"全局优化找到的参数可能过拟合，我要用向前测试验证它在不同时间段的表现"*

```python
br = Backtest(data, params, template)

# 第一步：全局优化
opt_result = br.optimize(config)
print(f"最优参数: {opt_result.best_params}")

# 第二步：用最优参数作为基础，进行向前测试
wf_result = br.walk_forward(
    config=WalkForwardConfig(...),
    params_override=opt_result.best_params  # 用优化得到的参数范围
)

# 查看泛化能力
print(f"泛化能力: {wf_result.is_robust}")
wf_result.display()

# 第三步（可选）：如果泛化测试通过，看最终详细回测
if wf_result.is_robust:
    final = br.run(params_override=wf_result.recommended_params)
    final.display()
    final.save(path)
```

**特点**：
- 三步流程：优化 → 向前测试 → 详细回测
- 全程复用同一个实例
- 验证策略的真实可用性

---

### 场景 8：自定义优化器 / 批量并发（高级）

**目标**：用户想用自己的优化算法（如 Optuna、贝叶斯优化），需要利用 Rust 层的并发能力

**用户心理**：*"内置优化器不够好，我想用 Optuna / 自己的算法"*

#### 方式 A：单次调用（简单）

```python
br = Backtest(data, params, template)

import optuna

def objective(trial):
    custom_params = generate_params_from_trial(trial)
    result = br.run(params_override=custom_params)
    return result.summary.performance.sharpe_ratio

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)
```

#### 方式 B：批量并发（高性能）

```python
br = Backtest(data, params, template)

# 自己生成参数列表
param_list = [generate_params(i) for i in range(100)]

# 利用 Rust 并发一次性跑完
batch_result = br.batch(param_list)

# 分析结果
best = batch_result.best_by(metric="sharpe_ratio")
print(f"最优参数: {best.params}")
best.display()
```

**特点**：
- 锦上添花功能，给高级用户使用
- `batch()` 需要显式传入参数列表
- 利用 Rust 的 Rayon 并发，避免 Python GIL 限制
- 返回批量结果，可以分析比较

---

### 场景 9：Jupyter Notebook 交互式探索

**目标**：分步骤执行，每步查看中间结果，灵活调整

**用户心理**：*"我在 Notebook 里探索，想一步步看结果"*

```python
# Cell 1: 初始化
br = Backtest(data, params, template)

# Cell 2: 运行回测
result = br.run()
print(result.summary.performance)

# Cell 3: 看图
result.display()

# Cell 4: 调整参数再跑
new_params = modify_params(params)
result2 = br.run(params_override=new_params)
result2.display()

# Cell 5: 满意了，保存
result2.format_for_export(config).save(path)

# Cell 6: 跑个优化看看
opt = br.optimize(OptConfig(...))
opt.best().display()
```

**特点**：
- 分步执行，灵活调整
- 频繁查看中间结果
- 可能多次修改参数重跑
- 同一个 `br` 实例反复使用

---

## API 设计要点（基于场景分析）

### 1. 初始化

```python
br = Backtest(
    data=...,           # 数据配置
    params=...,         # 单个参数集（包含参数范围定义）
    template=...,       # 信号模板
    settings=...,       # 引擎设置
)
```

- 初始化时设置**单个参数集**
- 数据只加载一次，后续操作复用

### 2. 执行方法

| 方法 | 参数需求 | 说明 |
|------|---------|------|
| `run(params_override=None)` | 单个参数 | 使用初始化的参数，或用 `params_override` 覆盖 |
| `optimize(config)` | 单个参数(内部扩展) | 基于初始化参数的范围进行优化 |
| `walk_forward(config, params_override=None)` | 单个参数 | 可覆盖参数范围 |
| `batch(param_list)` | 参数列表 | 显式传入，用于自定义优化器 |

### 3. 结果对象

每个执行方法返回独立的结果对象：

- `run()` → `RunResult`
- `optimize()` → `OptimizeResult`
- `walk_forward()` → `WalkForwardResult`
- `batch()` → `BatchResult`

### 4. 结果后续操作

```python
result.format_for_export(config)  # 格式化导出
      .save(path)                 # 保存到本地
      .upload(server)             # 上传到服务器
      .display()                  # 显示图表
```

### 5. 参数覆盖

支持在执行时覆盖初始化的参数：

```python
# 用优化结果的参数跑详细回测
detailed = br.run(params_override=opt_result.best_params)

# 用向前测试的参数继续跑
wf = br.walk_forward(config, params_override=opt_result.best_params)
```

---

## 场景关系图

```
                    ┌────────────────────────┐
                    │      Backtest()        │
                    │    (初始化 + 参数)      │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
   ┌─────────┐           ┌──────────────┐        ┌─────────────┐
   │  run()  │           │  optimize()  │        │walk_forward()│
   └────┬────┘           └──────┬───────┘        └──────┬──────┘
        │                       │                       │
        │                       ▼                       │
        │              ┌────────────────┐               │
        │              │  best_params   │               │
        │              └───────┬────────┘               │
        │                      │                        │
        │         ┌────────────┴────────────┐           │
        │         │                         │           │
        │         ▼                         ▼           │
        │    run(override)          walk_forward(override)
        │         │                         │           │
        │         ▼                         ▼           │
        │    详细回测                   验证泛化能力     │
        │                                   │           │
        │                                   ▼           │
        │                          recommended_params   │
        │                                   │           │
        │                                   ▼           │
        │                              run(override)    │
        │                                   │           │
        ▼                                   ▼           ▼
   ┌─────────────────────────────────────────────────────┐
   │      format_for_export() → save() → display()      │
   └─────────────────────────────────────────────────────┘


   ┌─────────────────────────────────────────────────────┐
   │              batch(param_list)                      │
   │         (自定义优化器 / Optuna 场景)                 │
   └─────────────────────────────────────────────────────┘
```
