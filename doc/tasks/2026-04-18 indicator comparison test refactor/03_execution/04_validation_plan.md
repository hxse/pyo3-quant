# 验证计划

## 1. 静态检查

执行：

```bash
just check
```

## 2. 指标测试

执行：

```bash
just test-py py_entry/Test/indicators
```

## 3. 试点阶段验证

试点迁移阶段允许先执行目标文件：

```bash
just test-py py_entry/Test/indicators/sma/test_contracts.py
just test-py py_entry/Test/indicators/ema/test_contracts.py
just test-py py_entry/Test/indicators/bbands/test_contracts.py
just test-py py_entry/Test/indicators/comparison/test_global_warmup_contracts.py
```

最终仍必须执行完整指标测试目录。

试点阶段还必须确认结构校验会覆盖：

1. 缺少 `test_contracts.py`。
2. 缺少 `test_accuracy`。
3. 缺少 `test_warmup_contract`。
4. 多出第三个 pytest `test_*` 函数。
5. 出现 `for`、`if`、`try`、`with` 或两个固定测试函数之外的函数定义。
6. 出现 case 拼接、筛选、排序、生成、取数、计算、比较或报错逻辑。
7. 单个 pytest case 内部隐藏 dataset 循环。
8. 继续新增 `test_accuracy.py` 或 `test_warmup.py` 旧入口。

## 4. 审查验证

测试通过不等于任务完成。

post-review 必须完成：

1. 语义新增清单核对。
2. 冻结语义清单核对。
3. 完整 diff 审查。
4. 清单外风险扫描。
5. 04-16 文档引用检查。
6. 特殊处理清单检查。
7. 失败上下文输出抽样检查。

## 5. 不要求

本任务不要求、也不鼓励给测试框架再构建一套 meta-test。

测试框架正确性主要靠 Spec、冻结清单、`git diff` 审查和指标测试迁移结果证明。
