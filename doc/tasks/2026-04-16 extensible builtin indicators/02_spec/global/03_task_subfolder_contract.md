# Task 子文件夹契约

## 1. 全局规则目录

全局规则固定放在：

```text
01_context/global/
02_spec/global/
03_execution/global/
```

这些文件只描述长期稳定协议，不描述某个指标的临时实现细节。

## 2. 单指标规格目录

每个指标必须拥有自己的规格目录：

```text
02_spec/indicators/<base_name>/
```

目录内至少包含：

```text
01_contract.md
02_test_contract.md
```

复杂指标可以继续拆分算法、边界和失败语义文件。

## 3. 单指标执行目录

每个指标必须拥有自己的执行目录：

```text
03_execution/indicators/<base_name>/
```

目录内至少包含：

```text
01_implementation_plan.md
02_validation_plan.md
03_legacy_kill_list.md
```

## 4. 单指标验收目录

进入执行后，每个指标的结果记录放在：

```text
04_review/indicators/<base_name>/
```

未进入执行前不创建结果性验收内容。

## 5. 后续指标追加规则

后续新增指标时：

1. 不新建全局任务。
2. 不复制 `global/` 文件。
3. 只追加对应指标的 `02_spec/indicators/<base_name>/` 与 `03_execution/indicators/<base_name>/`。
4. 若必须修改全局协议，先更新 `global/` 并说明影响范围。
