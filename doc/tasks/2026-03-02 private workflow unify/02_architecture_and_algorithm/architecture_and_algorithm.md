# 私有工作流统一重构：架构与算法文档（最终版）

## 1. 范围

定义统一后的类型契约、模块加载、执行链路、日志契约、注册器契约。

## 2. 目录

```text
py_entry/
  strategy_hub/
    core/
      spec.py
      spec_loader.py
      executor.py
      strategy_searcher.py
      searcher_args.py
      searcher_runtime.py
      searcher_serialize.py
      searcher_output.py
      strategy_name_guard.py
    test_strategies/
    search_spaces/
    registry/
    demo.ipynb
```

## 3. 三类类型

### 3.1 公共策略类型（最小交集）

```python
@dataclass(frozen=True)
class CommonStrategySpec:
    name: str
    version: str
    data_config: DataSourceConfig
    variant: VariantPayload
```

`VariantPayload`：

```python
@dataclass(frozen=True)
class VariantPayload:
    indicators_params: dict[str, Any]
    signal_params: dict[str, Any]
    backtest_params: BacktestParams
    signal_template: SignalTemplate
```

### 3.2 搜索空间类型

```python
@dataclass(frozen=True)
class SearchSpaceSpec(CommonStrategySpec):
    research: ResearchSpec
    source: Literal["search"] = "search"
```

### 3.3 测试类型

```python
@dataclass(frozen=True)
class TestStrategySpec(CommonStrategySpec):
    research: ResearchSpec | None = None
    btp_strategy_class: Any | None = None
    custom_params: dict[str, Any] | None = None
    chart_layout: Any | None = None
    source: Literal["test"] = "test"
    test_group: str | None = None
```

### 3.4 研究配置

```python
@dataclass(frozen=True)
class ResearchSpec:
    opt_cfg: OptimizerConfig
    sens_cfg: SensitivityConfig
    wf_cfg: WalkForwardConfig
```

## 4. 策略入口与加载

1. 所有策略模块统一导出 `build_strategy_bundle()`。
2. `spec_loader` 负责扫描、导入、入口校验、类型校验。
3. `search_spaces` 扫描时排除 `common.py`（只扫描可执行策略模块）。
4. 加载失败或入口缺失直接报错，不做静默跳过。

## 5. 执行协议

### 5.1 executor

1. 输入 `CommonStrategySpec`。
2. 构建 `Backtest`。
3. 执行阶段：`backtest/optimize/sensitivity/walk_forward`。

### 5.2 searcher

1. `strategy_searcher.py` 只做编排，不做重逻辑。
2. 重逻辑拆分：
   - 参数解析：`searcher_args.py`
   - 运行调度：`searcher_runtime.py`
   - 序列化：`searcher_serialize.py`
   - 输出落盘：`searcher_output.py`

## 6. 日志契约

### 6.1 顶层

```json
{
  "generated_at_utc": "2026-03-03T06:07:50Z",
  "modes": ["backtest", "walk_forward"],
  "results": [ ... ]
}
```

### 6.2 结果项核心字段

1. `strategy_name`
2. `strategy_version`
3. `strategy_module`
4. `mode`
5. `symbol`
6. `base_data_key`
7. `performance`
8. `backtest_default_params`
9. `windows`（WF）
10. `last_window_start_time_ms/last_window_best_params`（WF）
11. `backtest_start_time_ms/backtest_end_time_ms/backtest_span_ms`

### 6.3 路径与命名

1. 日志目录镜像 `search_spaces` 子目录层级。
2. 每个策略子目录固定 `logs/`。
3. 文件名：`<UTC_ISO_秒级(冒号替换下划线)>_<strategy_name>.json`。
4. 同名冲突重试 3 次，失败报错。

## 7. 注册器契约

### 7.1 字段

```json
{
  "log_path": "...",
  "symbol": "BTC/USDT",
  "mode": "backtest|walk_forward",
  "enabled": true,
  "position_size_pct": 0.2,
  "leverage": 2
}
```

### 7.2 预检算法

1. 校验日志存在并可解析。
2. 校验日志为“单文件单策略”。
3. 通过 `(symbol, mode)` 定位条目。
4. `mode=backtest` 读取 `backtest_default_params + backtest_start_time_ms`。
5. `mode=walk_forward` 读取 `last_window_best_params + last_window_start_time_ms`。
6. 启用条目中同一 `symbol` 只能出现一次。

## 8. 已下线能力

1. `core/template.py` 已删除。
2. `runner/pipeline.py` 已删除。
3. `test_strategies/base.py` 与 `StrategyConfig` 投影兼容层已删除。
