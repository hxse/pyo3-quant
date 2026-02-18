# 项目结构说明（当前版）

本文档仅描述当前有效的高层目录与职责，不再维护过细的逐文件清单。

## 1. 顶层结构

```text
pyo3-quant/
├── src/                    # Rust 核心引擎与 PyO3 绑定
├── py_entry/               # Python 业务层
├── python/                 # 生成的 Python 包与类型存根
├── doc/                    # 文档
├── justfile                # 任务入口
├── Cargo.toml              # Rust 构建配置
└── pyproject.toml          # Python 构建配置
```

## 2. Rust 层（`src/`）

- `backtest_engine/`：回测、优化、向前测试、敏感性等核心计算
- `types/`：暴露给 Python 的核心类型
- `error/`：Rust/Python 异常映射
- `lib.rs`：PyO3 模块注册入口

## 3. Python 层（`py_entry/`）

- `runner/`：`Backtest` 统一入口与结果对象封装
- `data_generator/`：模拟数据、HTTP 拉取数据、直接数据输入
- `io/`：导出、上传、展示、数据客户端
- `strategies/`：策略定义与注册表（独立于测试目录）
- `example/`：示例脚本与 notebook
- `trading_bot/`：交易机器人执行框架（不写策略细节）
- `Test/`：pytest 测试集合

## 4. 策略相关分层（当前约定）

- `example`：示例与展示
- `private_strategies`：私有策略（可本地忽略、手动部署）
- `strategies`：公共策略定义来源（`StrategyConfig` 与注册表）
- `Test`：消费 `strategies` 做公共回归 + 自定义测试场景
- `trading_bot`：消费策略配置并执行，不定义策略本体

详见：`doc/structure/strategy_cross_module_plan.md`

## 5. 文档状态说明

本目录下文档按“当前版”维护：

- `pyo3_interface_design.md`：接口设计规范
- `strategy_cross_module_plan.md`：跨模块策略计划
- `python_api.md`：Python API 使用说明
- `usage_scenarios.md`：Backtest 场景说明
- `project_structure.md`：目录职责说明（本文）

若与代码冲突，以代码与 `just check`/`just test` 结果为准。
