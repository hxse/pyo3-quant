# 项目结构说明（当前版）

本文档仅描述当前有效目录与职责，历史目录不再列入。

## 1. 顶层结构

```text
pyo3-quant/
├── src/                    # Rust 核心引擎与 PyO3 绑定
├── py_entry/               # Python 业务层
├── python/                 # 生成的 Python 包与类型存根
├── doc/                    # 文档
├── justfile                # 命令入口
├── Cargo.toml              # Rust 构建配置
└── pyproject.toml          # Python 构建配置
```

## 2. Rust 层（`src/`）

1. `backtest_engine/`：回测、优化、敏感性、向前测试核心计算。
2. `types/`：PyO3 暴露给 Python 的输入输出类型。
3. `error/`：Rust/Python 异常映射。
4. `lib.rs`：PyO3 模块注册入口。

## 3. Python 层（`py_entry/`）

1. `runner/`：`Backtest` 入口、结果对象、展示与导出。
2. `data_generator/`：模拟数据、交易所拉取、直接数据喂入。
3. `io/`：本地保存、上传、图表显示相关能力。
4. `strategy_hub/`：统一策略协议、搜索、注册器、demo。
5. `trading_bot/`：机器人执行框架（不定义策略）。
6. `Test/`：pytest 测试集合。
7. `scanner/`：独立扫描模块（与 strategy_hub 解耦）。

## 4. `strategy_hub` 分层

```text
py_entry/strategy_hub/
├── core/
│   ├── spec.py                 # Common/Search/Test 策略协议
│   ├── spec_loader.py          # 模块发现与加载校验
│   ├── executor.py             # 统一执行入口
│   ├── strategy_searcher.py    # workflow 主入口（薄 orchestrator）
│   ├── searcher_args.py        # searcher 参数解析
│   ├── searcher_runtime.py     # searcher 执行调度
│   ├── searcher_serialize.py   # searcher 结果序列化
│   └── searcher_output.py      # searcher 输出与落盘
├── search_spaces/              # 搜索空间策略（主工作流）
├── test_strategies/            # 测试策略（Test/demo 复用）
├── registry/                   # live 注册器与加载器
└── demo.ipynb                  # 可视化入口
```

## 5. 策略目录约束

1. `search_spaces` 采用“子目录 + common.py + 派生策略文件”强约束。
2. 每个搜索策略子目录内固定使用 `logs/` 存放该子目录策略日志。
3. `test_strategies` 推荐同写法，但允许测试最小样例简化。
4. 策略统一入口：`build_strategy_bundle()`。

## 6. 命令与运行口径

1. 主入口命令：`just workflow ...`。
2. 搜索执行口径：单策略多品种或单品种多策略，不支持多策略多品种混合。
3. 控制台日志统一 JSON 风格（`stage/level/performance`）。

## 7. 文档状态说明

若文档与代码冲突，以代码与以下命令结果为准：

1. `just check`
2. `just test`
