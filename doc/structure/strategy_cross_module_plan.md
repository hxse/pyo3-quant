# 策略跨模块统一计划（精简定稿）

## 1. 目标与边界

1. 私有策略主战场是 `py_entry/private_strategies`（research + live）。
2. `private_strategies` 默认手动管理，不上传 GitHub，默认在 `.gitignore` 中。
3. 公共策略主战场是 `py_entry/strategies`，只用于 `example`/`Test` 的示例与基线回归，不用于实盘。
4. 不做复杂插件系统，不做兼容层堆叠，优先唯一写法与清晰边界。
5. 数据源类型统一使用 `DataSourceConfig` 三种实现：`OhlcvDataFetchConfig`（实时网络数据）、`DataGenerationParams`（离线模拟数据）、`DirectDataConfig`（直接喂入数据）。

## 2. 模块职责

### 2.1 `py_entry/private_strategies`

1. `research/`：研究与试验，支持灵活新增/修改多个 `ipynb`。
2. `live/`：机器人实盘策略来源。
3. `research -> live` 采用直接复制：同一份 `.py` 原样复制，保持一模一样。
4. `live` 至少保留骨架：`__init__.py` + 一个示例策略文件。
5. 示例策略仅加载不启用（`enabled=False`），只用于复制写法骨架。
6. 默认使用真实网络数据（`OhlcvDataFetchConfig`），保证研究与实盘数据口径一致。
7. 阶段执行逻辑统一放在 `py_entry/private_strategies/stage_tools.py`，策略文件只负责参数定义与传参调用（便于人工审阅）。

### 2.2 `py_entry/strategies`

1. 公共注册表策略：`StrategyConfig + get_strategy(...)`。
2. 供 `example` 与 `Test` 复用。
3. 不承载 private live 实盘策略。
4. 默认使用离线模拟数据（`DataGenerationParams`）作为稳定基线。

### 2.3 `py_entry/example`

1. `.py`：AI 调试入口（`__main__` 输出摘要）。
2. `ipynb`：人类图表与交互调试入口。
3. `example/example.ipynb` 作为 research notebook 模板来源。
4. AI 默认不读取 `ipynb`；应优先通过命令行执行策略脚本（优先 `just run <py_file>`）获取结果。

### 2.4 `py_entry/Test`

1. 可复用公共注册表策略。
2. 允许测试内自定义最小构造（场景化边界测试）。
3. `Test` 不是策略类型定义来源。
4. 允许“公共策略 + 局部参数覆写”测试：先 `get_strategy(...)` 获取基线配置，再只改测试关注参数，避免复制整套策略。
5. 默认使用离线模拟数据（`DataGenerationParams`）；只有明确的数据链路测试才使用实时网络数据。
6. 允许使用 `DirectDataConfig` 人工构造测试数据（用于边界、异常、最小复现与回归验证）。

### 2.5 `py_entry/trading_bot`

1. 不写策略细节。
2. 通过 `py_entry/trading_bot/live_strategy_callbacks.py` 消费 live 注册表。
3. 仅 `enabled=True` 的 live 策略进入执行链路。
4. 机器人应当定义为：支持多品种，但同一 `symbol` 仅允许一个策略（硬约束）。

## 3. live 注册机制（当前实现）

1. `@register_live_strategy(name)` 只做函数标记，不直接写注册表。
2. 仅 `py_entry/private_strategies/live/__init__.py` 自动扫描 `live/*.py` 并收集标记函数。
3. `research` 文件不会进入 live 注册表（即使有同样装饰器）。
4. 策略名重复时立即报错，不允许覆盖（唯一性原则）。
5. live 与机器人对齐规则：`LiveStrategyCallbacks` 会校验启用策略的 `symbol` 唯一性；若同一 `symbol` 出现多个启用策略，启动即报错。

## 4. Notebook 模板约束

1. `example/example.ipynb` 与 `research/demo.ipynb` 保持同一执行骨架：
   - 路径初始化
   - `run_from_config(...)`
   - `display` 展示区块
2. 策略入口统一走 `strategy_configs` 映射。
3. 新增策略只改导入与映射项，不改执行主流程。
4. 模板默认支持 `StrategyConfig` 与 `LiveStrategyConfig` 两种输入。
5. `ipynb` 内不写具体策略实现，只做策略加载与图表展示，保证模板通用性。
6. `research/*.py` 采用“薄策略文件”写法：只定义 `rc/rt` 与各阶段配置函数，阶段执行由 `stage_tools.py` 统一承载。

## 4.1 example `.py` / `.ipynb` 写法规范

1. `example/*.py` 统一提供 `get_*_config() -> StrategyConfig`。
2. `example/*.py` 统一提供 `run_xxx(..., config: StrategyConfig | None = None)`，未传参时走对应 `get_*_config()`。
3. `example/*.py` 必须保留 `__main__`，并打印 AI 可读摘要（纯文本关键指标）。
4. `example/example.ipynb` 只导入 config getter，不写策略实现。
5. `example/example.ipynb` 统一形态是：`strategy_configs[name] -> cfg -> run_from_config(cfg)`，不再混用 `lambda` 直接跑策略。

`.ipynb` 导入单元格示例（不是 `.py`）：

```python
from py_entry.example.custom_backtest import get_custom_backtest_config
from py_entry.example.real_data_backtest import get_real_data_backtest_config
from py_entry.example.reversal_extreme_backtest import get_reversal_extreme_config
```

`.ipynb` 执行主流程示例：

```python
strategy_configs = {
    "mtf_bbands_rsi_sma": get_custom_backtest_config,
    "real_data_backtest": get_real_data_backtest_config,
    "reversal_extreme": get_reversal_extreme_config,
}

cfg = strategy_configs[STRATEGY]()
result = run_from_config(cfg)
```

## 5. 当前目录状态（现状）

1. `example` 演示 notebook：`py_entry/example/example.ipynb`
   - 三策略：`mtf_bbands_rsi_sma` / `real_data_backtest` / `reversal_extreme`。
   - 三策略统一通过 `py_entry/example/*.py` 的 `get_*_config()` 入口加载，notebook 不直接写策略细节。
2. `research` 研究文件（默认不上传 GitHub，本地私有）：
   - 典型本地文件：`py_entry/private_strategies/research/demo.ipynb`
   - 典型本地文件：`py_entry/private_strategies/research/example_strategy.py`
   - 注意：在新 clone 的仓库里，这些 research 文件不存在是预期行为，不代表结构异常。
   - `research` 与 `live` 的同名策略 `.py` 必须保持原样复制、一模一样。
   - 与 `example` 模板同骨架，仅策略导入与映射可按研究需要调整。
3. `live` 可落地骨架文件（上传 GitHub）：
   - `py_entry/private_strategies/live/__init__.py`
   - `py_entry/private_strategies/live/example_strategy.py`
   - 示例策略仅加载不启用，用于复制写法骨架。
4. 当前示例策略数据源：真实数据（`OhlcvDataFetchConfig + load_local_config()`）。

## 6. 推荐工作流（执行顺序）

1. 在 `py_entry/private_strategies/research` 用 `ipynb` 做研究。
2. 研究通过后，将对应策略 `.py` 原样复制到 `py_entry/private_strategies/live`。
3. 复制后固定执行硬清单：`just live-sync-check` -> `just check` -> `live smoke test` -> 接入机器人。
4. 再由机器人通过 `LiveStrategyCallbacks` 执行 live 策略。
5. 日常门禁顺序：先 `just check`，后 `just test`。
6. AI 调试策略时，默认走命令行执行路径：优先 `just run <py_file>`，而不是读取 notebook 输出。

## 7. 最小示例

### 7.1 公共策略（example/Test）

```python
from py_entry.strategies import get_strategy
from py_entry.runner import Backtest

cfg = get_strategy("mtf_bbands_rsi_sma")
result = Backtest(
    data_source=cfg.data_config,
    indicators=cfg.indicators_params,
    signal=cfg.signal_params,
    backtest=cfg.backtest_params,
    signal_template=cfg.signal_template,
    engine_settings=cfg.engine_settings,
    performance=cfg.performance_params,
).run()
```

### 7.2 private live 策略（注册）

```python
from py_entry.private_strategies.live import register_live_strategy
from py_entry.private_strategies.live.base import LiveStrategyConfig

@register_live_strategy("my_live_strategy")
def get_live_config() -> LiveStrategyConfig:
    ...
```

### 7.3 Test 场景：公共策略局部改参

```python
from py_entry.strategies import get_strategy
from py_entry.runner import Backtest
from py_entry.types import Param

cfg = get_strategy("mtf_bbands_rsi_sma")

# 仅覆写测试关注参数，其余沿用公共基线配置
cfg.indicators_params["ohlcv_15m"]["bbands"]["period"] = Param(20)
cfg.backtest_params.initial_capital = 5000.0

result = Backtest(
    data_source=cfg.data_config,
    indicators=cfg.indicators_params,
    signal=cfg.signal_params,
    backtest=cfg.backtest_params,
    signal_template=cfg.signal_template,
    engine_settings=cfg.engine_settings,
    performance=cfg.performance_params,
).run()
```

### 7.4 机器人桥接

```python
from py_entry.trading_bot import LiveStrategyCallbacks

callbacks = LiveStrategyCallbacks(inner=exchange_callbacks)
```
