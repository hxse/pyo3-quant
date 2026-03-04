# 策略跨模块统一计划（当前版）

## 1. 目标

1. 统一策略协议：搜索、测试、机器人全链路只消费 `CommonStrategySpec` 子类。
2. 统一执行链路：`spec_loader + executor + strategy_searcher`，不保留中间兼容层。
3. 统一日志契约：同一 JSON 结构、同一字段口径、同一落盘规则。
4. 统一目录边界：策略定义集中在 `strategy_hub`，`scanner` 独立不耦合。

## 2. 模块职责

### 2.1 `py_entry/strategy_hub/core`

1. `spec.py`：定义 `CommonStrategySpec`、`SearchSpaceSpec`、`TestStrategySpec`。
2. `spec_loader.py`：扫描模块、加载 `build_strategy_bundle()`、强校验协议。
3. `executor.py`：从 Spec 构建 `Backtest`，执行单阶段。
4. `strategy_searcher.py`：workflow 主入口（薄 orchestrator）。
5. `searcher_args.py`：命令参数与组合模式解析。
6. `searcher_runtime.py`：任务拓扑、阶段执行、排序。
7. `searcher_serialize.py`：参数与窗口结果序列化。
8. `searcher_output.py`：控制台输出与日志落盘。

说明：`core/template.py` 已下线，不再作为执行入口。

### 2.2 `py_entry/strategy_hub/search_spaces`

1. 搜索主战场，策略按子目录组织。
2. 每个子目录必须有 `common.py`，策略文件从 `common.py` 派生。
3. 每个子目录固定 `logs/` 保存该目录策略日志。

### 2.3 `py_entry/strategy_hub/test_strategies`

1. 测试策略来源，返回 `TestStrategySpec`。
2. 供 `Test` 与 `demo.ipynb` 复用。
3. 推荐与 `search_spaces` 同写法，但允许最小样例简化。

### 2.4 `py_entry/strategy_hub/registry`

1. 机器人唯一注册入口。
2. 只接受 JSON 注册器条目，不走策略自动扫描。
3. 通过 `log_path + symbol + mode` 从日志解析参数与起始时间。

### 2.5 `py_entry/trading_bot`

1. 通过 `LiveStrategyCallbacks` 加载注册器并执行。
2. 同一 `symbol` 仅允许一个 `enabled=true` 条目，冲突即启动失败。

## 3. 策略入口与发现规则

1. 策略模块唯一入口：`build_strategy_bundle()`。
2. `search` 与 `test` 两域都走 `spec_loader.discover_modules/load_spec`。
3. 搜索策略支持：
   - 完整名：`folder.module`
   - 短名：`module`（必须全局唯一）
   - `folder.*`：子目录全策略
   - `*`：全部搜索策略

## 4. workflow 命令语义

统一入口：

```bash
just workflow --strategies ... --symbols ... --mode ...
```

1. `--strategies` 必填，支持逗号组合与语法糖。
2. `--symbols` 必填，支持逗号组合。
3. `--mode` 支持组合，按传入顺序串行执行并合并日志。
4. `mode` 重复直接报错。
5. 仅支持：
   - 单策略多品种
   - 单品种多策略

## 5. 日志与输出口径

1. 控制台阶段日志统一标准 JSON：包含 `stage`、`level`、`performance`。
2. 不再使用旧前缀格式（如 `backtest.brief=`）和 `key=value` 文本拼接。
3. 文件名规则：`UTC_ISO秒级(冒号替换下划线)_strategy_name.json`。
4. 同名冲突处理：延迟 1 秒重试 3 次，失败报错建议重跑。

## 6. demo 统一入口

`py_entry/strategy_hub/demo.ipynb` 使用：

1. `build_strategy_runtime("search:..."/"test:...", run_symbol=...)`

不在 notebook 中写策略实现。

## 7. 当前已清理项

1. 已删除 `core/template.py`。
2. 已删除 `runner/pipeline.py`。
3. 已删除 `test_strategies/base.py` 与 `StrategyConfig` 投影兼容层。
4. `strategy_searcher` 已拆分为多模块，主入口保持薄编排。
