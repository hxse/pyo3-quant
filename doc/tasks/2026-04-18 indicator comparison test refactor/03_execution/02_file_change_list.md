# 文件影响清单

本文件是执行阶段预估清单，具体落地可在 pre-review 后调整。

## 1. 预计新增或重构

可能新增：

```text
py_entry/Test/indicators/comparison/
py_entry/Test/indicators/comparison/case.py
py_entry/Test/indicators/comparison/oracle_types.py
py_entry/Test/indicators/comparison/compare.py
py_entry/Test/indicators/comparison/datasets.py
py_entry/Test/indicators/comparison/reporting.py
py_entry/Test/indicators/comparison/test_global_warmup_contracts.py
py_entry/Test/indicators/<indicator>/
py_entry/Test/indicators/<indicator>/cases.py
py_entry/Test/indicators/<indicator>/adapter.py
py_entry/Test/indicators/<indicator>/test_contracts.py
py_entry/Test/indicators/<indicator>/fixtures/local_csv/
```

具体结构以 `02_spec/11_indicator_directory_structure.md` 为准。

也允许在现有文件内阶段性迁移，但最终不得形成职责过大的测试模板文件。

## 2. 预计修改

```text
py_entry/Test/indicators/indicator_test_template.py
py_entry/Test/utils/comparison_tool.py
py_entry/Test/indicators/conftest.py
py_entry/Test/indicators/test_indicator_warmup_contract.py
```

`test_indicator_warmup_contract.py` 是迁移输入；长期目标是把全局 warmup 冻结项收口到 `comparison/test_global_warmup_contracts.py`。

`conftest.py` 或等价共享 pytest 入口需要新增结构校验：指标目录存在 `cases.py` 与 `adapter.py` 时，必须存在 `test_contracts.py`，且该文件固定只包含 `test_accuracy` 与 `test_warmup_contract` 两个 pytest 函数。该文件还不得包含 `for`、`if`、`try`、`with`、两个固定测试函数之外的函数定义、case 拼接、case 筛选、取数、计算、比较或报错逻辑。

现有平铺文件属于迁移输入或过渡对象：

```text
py_entry/Test/indicators/test_<indicator>.py
```

目标长期结构是 `py_entry/Test/indicators/<indicator>/test_contracts.py`，不再继续新增平铺指标测试文件，也不新增按职责拆开的 `test_accuracy.py` / `test_warmup.py` 旧入口。

## 3. 不应修改

本任务不应修改：

```text
src/backtest_engine/indicators/**
src/backtest_engine/signals/**
py_entry/strategy_hub/**
py_entry/scanner/**
```

若执行中发现必须修改生产代码，应暂停并更新 Task 范围。

## 4. 删除或退出

旧的 `assert_mode_pandas_ta` / `assert_mode_talib` 可以退出长期正式口径。

旧的平铺 `test_<indicator>.py` 也应在迁移完成后退出长期正式口径，指标扩展收口到 `<indicator>/` 目录。

退出前必须确认：

1. 正向一致语义迁移到 primary oracle。
2. 预期不一致语义迁移到 expected different assertion。
3. 没有现有指标测试覆盖被静默删除。
