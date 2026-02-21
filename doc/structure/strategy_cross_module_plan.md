# 策略跨模块统一计划（精简定稿）

## 1. 目标与边界

1. 私有策略主战场是 `py_entry/private_strategies`（扁平化策略模块 + 通用模板）。
2. `private_strategies` 默认手动管理，不上传 GitHub，默认在 `.gitignore` 中。
3. 公共策略主战场是 `py_entry/strategies`，只用于 `example`/`Test` 的示例与基线回归，不用于实盘。
4. 不做复杂插件系统，不做兼容层堆叠，优先唯一写法与清晰边界。
5. 数据源类型统一使用 `DataSourceConfig` 三种实现：`OhlcvDataFetchConfig`（实时网络数据）、`DataGenerationParams`（离线模拟数据）、`DirectDataConfig`（直接喂入数据）。

## 2. 模块职责

### 2.1 `py_entry/private_strategies`

1. 目录扁平化：不再区分 `research/live` 子目录。
2. 通用模板：`template.py` 统一承载自动发现、阶段执行与 CLI 入口。
3. 策略文件职责固定为配置定义：`get_live_config`、`build_opt_cfg`、`build_sens_cfg`、`build_wf_cfg`。
4. 策略文件可选提供 `build_runtime_config` 作为运行期元信息，不参与执行逻辑。
5. 阶段执行逻辑统一收敛到 `py_entry/runner`，`template.py` 只做策略发现、缓存与调度。
6. 默认使用真实网络数据（`OhlcvDataFetchConfig`），保证研究与实盘数据口径一致。

### 2.1.0 `config.py` 统一配置入口

1. 新增统一配置文件：`py_entry/private_strategies/config.py`。
2. `build_opt_cfg(overrides=None)`、`build_sens_cfg(overrides=None)`、`build_wf_cfg(overrides=None, opt_overrides=None)`、`build_runtime_config(overrides=None)` 作为唯一通用入口。
3. 策略文件与搜索空间文件统一调用上述构建器，避免两套口径。
4. 默认策略：优先使用统一默认配置；仅在必要时通过覆盖参数做差异化。
5. 覆盖规则：允许策略级/搜索空间级覆盖，但禁止复制整段默认配置，必须走“默认 + 覆盖”写法。

### 2.1.1 `strategy_searcher` 设计约束

1. `py_entry/private_strategies/strategy_searcher.py` 只负责搜索调度，固定顺序执行（不并发）。
2. 搜索器支持两种运行模式：
   - `backtest`：默认参数单次回测（不优化参数）。
   - `walk_forward`：向前测试（窗口优化 + OOS 拼接）。
3. 默认模式是 `walk_forward`；可通过 `--mode backtest` 切换到默认参数回测。
4. 支持 `--positive-only true`，仅保留 `total_return > 0` 的结果，便于快速筛选候选策略。
5. 搜索空间与正式策略文件解耦：搜索组合统一放在 `py_entry/private_strategies/search_spaces/*.py`。
6. 搜索空间模块必须提供 `build_search_space()`，由搜索器自动扫描并加载。
7. 为避免仓库暴露私有组合，`.gitignore` 仅白名单一个示例搜索空间文件，其余本地管理。
8. 搜索任务拓扑仅支持两种模式：
   - 单策略多品种：`len(spaces)=1` 且 `len(symbols)>=1`
   - 单品种多策略：`len(spaces)>=1` 且 `len(symbols)=1`
9. 明确禁止“多策略 + 多品种”混合搜索（不同品种不同策略），命令级直接报错，不做兼容回退。
10. `symbols=""`（空字符串）表示“不覆盖品种”，回退为各搜索空间 `build_search_space()` 中定义的默认 `symbol`。
11. `spaces=""`（空字符串）表示“自动扫描全部搜索空间模块”。

### 2.2 `py_entry/strategies`

1. 公共注册表策略：`StrategyConfig + get_strategy(...)`。
2. 供 `example` 与 `Test` 复用。
3. 不承载 private live 实盘策略。
4. 默认使用离线模拟数据（`DataGenerationParams`）作为稳定基线。

### 2.3 `py_entry/example`

1. `.py`：AI 调试入口（`__main__` 输出摘要）。
2. `ipynb`：人类图表与交互调试入口。
3. `example/example.ipynb` 作为 research notebook 模板来源。
4. AI 默认不读取 `ipynb`；private 策略应优先通过命令行执行模板（优先 `just run strategy=<module_name>`）获取结果。

### 2.4 `py_entry/Test`

1. 可复用公共注册表策略。
2. 允许测试内自定义最小构造（场景化边界测试）。
3. `Test` 不是策略类型定义来源。
4. 允许“公共策略 + 局部参数覆写”测试：先 `get_strategy(...)` 获取基线配置，再只改测试关注参数，避免复制整套策略。
5. 默认使用离线模拟数据（`DataGenerationParams`）；只有明确的数据链路测试才使用实时网络数据。
6. 允许使用 `DirectDataConfig` 人工构造测试数据（用于边界、异常、最小复现与回归验证）。

### 2.5 `py_entry/trading_bot`

1. 不写策略细节。
2. 通过 `py_entry/trading_bot/live_strategy_callbacks.py` 消费 `private_strategies/template.py` 的策略发现结果。
3. 仅 `enabled=True` 的 live 策略进入执行链路。
4. 机器人应当定义为：支持多品种，但同一 `symbol` 仅允许一个策略（硬约束）。

### 2.6 `align_to_base_range` 模块级规则

1. 全局默认值统一为 `False`（`DataGenerationParams` / `OhlcvDataFetchConfig` / `DirectDataConfig` 一致），避免隐式裁剪导致高周期数据长度意外变短。
2. `private_strategies` 默认使用 `False`，保证研究与实盘看到的是原始数据覆盖范围。
3. `example` 默认使用 `False`，确保示例行为与主流程一致，不引入隐藏对齐裁剪副作用。
4. `Test` 默认使用 `False`，仅在“明确要验证 base 对齐裁剪行为”的专项测试里显式传 `True`。
5. `trading_bot` 侧默认沿用策略配置的 `False` 口径；如需对齐裁剪，必须在策略中显式声明，不允许依赖默认值。
6. 规则总结：`True` 只用于“刻意验证/刻意裁剪”的显式场景，不能作为常规配置。

## 3. private 策略发现机制（当前实现）

1. 由 `py_entry/private_strategies/template.py` 扫描同目录策略模块（排除骨架文件）。
2. 每个策略模块必须提供 `get_live_config()`，返回 `StrategyConfig`（且必须带 `live_meta`）。
3. `LiveStrategyCallbacks` 直接消费 `get_live_strategy_names()/get_live_strategy()`，不再依赖子目录扫描注册表。
4. 机器人仍执行 `enabled` 过滤与 `symbol` 唯一性校验；若同一 `symbol` 出现多个启用策略，启动即报错。

## 4. Notebook 模板约束

1. `example/example.ipynb` 与 `private_strategies/demo.ipynb` 保持同一执行骨架：
   - 路径初始化
   - `run_from_config(...)`
   - `display` 展示区块
2. 策略入口统一走 `strategy_configs` 映射。
3. 新增策略只改导入与映射项，不改执行主流程。
4. 模板只支持 `StrategyConfig` 单一输入，不再兼容双类型。
5. `ipynb` 内不写具体策略实现，只做策略加载与图表展示，保证模板通用性。
6. `private_strategies/*.py` 采用“薄策略文件”写法：只定义配置函数，阶段执行由 `runner + template.py` 统一承载。

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
2. `private_strategies` 私有目录（默认本地手动管理）：
   - 通用骨架：`py_entry/private_strategies/template.py`、`py_entry/private_strategies/config.py`
   - 策略配置：`py_entry/private_strategies/sma_2tf.py`等等
   - notebook 模板：`py_entry/private_strategies/demo.ipynb`
   - 示例策略默认 `enabled=False`，仅作复制骨架与研究起点。
3. 当前示例策略数据源：真实数据（`OhlcvDataFetchConfig + load_local_config()`）。

## 6. 推荐工作流（执行顺序）

1. 在 `py_entry/private_strategies` 下新增/维护策略配置文件。
2. 通过 `py_entry/private_strategies/demo.ipynb` 做人类阶段调试。
3. 通过 `just run strategy=<module_name>` 执行统一 CLI 管道。
4. 需要批量筛选时，使用策略搜索器：
   - 单策略多品种：`just search spaces=<space_name> symbols=BTC/USDT,SOL/USDT`
   - 单品种多策略：`just search spaces=<space_a>,<space_b> symbols=BTC/USDT`
5. 固定执行硬清单：`just check` -> `just test` -> 接入机器人。
5. 机器人通过 `LiveStrategyCallbacks` 自动发现并执行 `enabled=True` 的策略。
5. 日常门禁顺序：先 `just check`，后 `just test`。
6. AI 调试 private 策略时，默认走命令行执行路径：优先 `just run strategy=<module_name>`，而不是读取 notebook 输出。

## 6.1 策略搜索双层验证工作流（防过拟合）

1. 第一层：默认参数筛选（单市场多策略）
   - 目标：先筛掉“默认参数即无正收益”的弱策略。
   - 命令示例：`just search --symbols SOL/USDT --mode backtest --positive-only true`
   - 结果处理：仅记录 `total_return > 0` 的策略作为候选池。
2. 第二层：默认参数跨品种一致性（单策略多品种）
   - 目标：验证候选策略是否具备跨品种正收益一致性。
   - 命令示例：`just search --spaces rsi30_macd4h --symbols BTC/USDT,ETH/USDT,SOL/USDT,XRP/USDT,DOGE/USDT,BNB/USDT,LTC/USDT,ADA/USDT,TRX/USDT --mode backtest --positive-only true`
   - 结果处理：仅保留在多个品种仍为正收益的策略。
3. 第三层：向前测试跨品种验证（单策略多品种）
   - 目标：在 OOS 拼接口径下进一步验证稳健性。
   - 命令示例：`just search --spaces rsi30_macd4h --symbols BTC/USDT,ETH/USDT,SOL/USDT,XRP/USDT,DOGE/USDT,BNB/USDT,LTC/USDT,ADA/USDT,TRX/USDT --mode walk_forward --positive-only true`
   - 结果处理：仅记录在 `walk_forward` 下跨品种仍为正收益的策略。
4. 结论口径（统一）
   - 通过标准：`backtest` 跨品种正收益 + `walk_forward` 跨品种正收益。
   - 排序优先级：先看 `calmar_ratio_raw`，再看 `total_return`，最后看 `max_drawdown`。

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

### 7.2 private 策略（通用模板加载）

```python
from py_entry.strategies.base import LiveMeta, StrategyConfig

def get_live_config() -> StrategyConfig:
    strategy = StrategyConfig(...)
    strategy.live_meta = LiveMeta(
        enabled=False,
        position_size_pct=0.2,
        leverage=2,
        settlement_currency="USDT",
    )
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
