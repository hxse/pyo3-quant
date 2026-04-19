# Task 子目录设计

## 1. 设计目标

本任务是长期内置指标扩展任务，不应只服务单个指标。

后续新增指标时，应直接在本 task 下追加该指标的规格和执行记录。这样可以复用项目级扩展协议，同时避免每个指标都重新建立一套全局文档。

## 2. 推荐结构

```text
doc/tasks/2026-04-16 extensible builtin indicators/
  00_meta.md
  01_context/
    global/
  02_spec/
    global/
    indicators/
      kc/
      <future_indicator>/
  03_execution/
    global/
    indicators/
      kc/
      <future_indicator>/
  04_review/
    indicators/
      kc/
      <future_indicator>/
```

## 3. 分层规则

`global/` 只放长期稳定规则：

1. 项目内置指标口径。
2. 指标扩展协议。
3. 真值源优先级。
4. 通用测试和验证要求。

`indicators/<name>/` 只放单个指标的实例化规格：

1. 参数。
2. 公式。
3. 输出列。
4. warmup。
5. 单指标测试计划。
6. 单指标执行和验收记录。

## 4. 后续扩展方式

新增指标时，不改写已完成指标的历史规格，除非该指标本身要被修复。

新增指标应增加：

```text
02_spec/indicators/<name>/
03_execution/indicators/<name>/
04_review/indicators/<name>/
```

若新增指标需要改变项目级扩展协议，必须先更新 `global/`，并在 review 中说明影响范围。
