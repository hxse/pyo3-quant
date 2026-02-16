# PyO3 接口设计说明（新架构）

本文档描述当前版本（最新状态）的 PyO3 接口设计，用于：

- 快速理解 Rust ↔ Python 的边界与职责。
- 指导新增接口、扩展类型、调试问题时的正确姿势。
- 降低开发中常见错误（类型不匹配、对象写回失效、调用方式不一致等）。

本文档只描述当前实现，不讨论历史方案与演进过程。

---

## 0. 设计意图达成状态

当前版本已经实现最初目标：

1. 回测引擎核心输入/输出类型统一定义在 Rust 侧（`src/types`）。
2. Python 侧不再维护对应的镜像模型文件，改为直接使用 Rust 导出的 `#[pyclass]` 类型。
3. 通过 `just` 工作流自动生成并更新 `.pyi`（`just stub`，`just check` 中也会触发）。
4. 同时具备 Rust 与 Python 两侧静态检查能力：
   - Rust：`cargo check`（由 `just check-rust` / `just check` 触发）
   - Python：`ty check`（由 `just check-py` / `just check` 触发）
5. 开发流程以 `just` 命令为统一入口；`just` 已封装编译、存根生成、类型检查与测试等关键步骤，应优先使用而非直接调用底层命令。

这意味着当前架构已经形成“Rust 类型单一事实源 + 自动存根 + 双侧静态检查”的闭环。

---

## 1. 总体架构

### 1.1 模块分层

当前架构采用“Rust 类型为单一事实源（Single Source of Truth）”的设计：

- Rust 端定义输入/输出类型（`src/types`），并通过 `#[pyclass]` 暴露给 Python。
- 核心计算在 Rust（`src/backtest_engine`）完成。
- Python 端作为编排层，负责组装参数与调用入口。

关键入口：

- Rust 扩展主模块：`pyo3_quant._pyo3_quant`
- Python 包外观：`python/pyo3_quant/__init__.py`
- 引擎子模块：`pyo3_quant.backtest_engine`

### 1.2 主模块注册

`src/lib.rs` 完成以下注册：

1. 注册全部 `#[pyclass]`（输入类型 + 输出类型 + 枚举）。
2. 注册 `backtest_engine` 与 `errors` 子模块。
3. 将子模块写入 `sys.modules`，确保可稳定导入：
   - `import pyo3_quant.backtest_engine`
   - `import pyo3_quant.errors`

这意味着 Python 不再需要做动态桥接注入，模块路径由 Rust 统一管理。

---

## 2. Python 包与接口面

### 2.1 包结构

- `python/pyo3_quant/__init__.py`
  - `from ._pyo3_quant import *`
  - 同时暴露 `errors`、`backtest_engine`
- `python/pyo3_quant/backtest_engine/*.pyi`
  - 每个子模块单独提供类型签名

### 2.2 引擎顶层函数

`pyo3_quant.backtest_engine` 当前主入口：

- `run_backtest_engine(data_dict, param_set, template, engine_settings) -> list[BacktestSummary]`
- `run_single_backtest(data_dict, param, template, engine_settings) -> BacktestSummary`

子模块函数（示例）：

- `backtester.run_backtest(...)`
- `indicators.calculate_indicators(...)`
- `signal_generator.generate_signals(...)`
- `performance_analyzer.analyze_performance(...)`
- `optimizer.py_run_optimizer(...)`
- `walk_forward.run_walk_forward(...)`
- `sensitivity.run_sensitivity_test(...)`

### 2.3 调试索引：PyO3 入口函数全清单（输入/返回）

以下清单以当前自动生成存根为准（`python/pyo3_quant/**/*.pyi`），用于调试时快速定位类型边界。

#### A. 顶层编排入口（推荐业务调用）

1. `pyo3_quant.backtest_engine.run_backtest_engine`
   - 输入：
     - `data_dict: DataContainer`
     - `param_set: list[SingleParamSet]`
     - `template: TemplateContainer`
     - `engine_settings: SettingContainer`
   - 返回：`list[BacktestSummary]`
2. `pyo3_quant.backtest_engine.run_single_backtest`
   - 输入：
     - `data_dict: DataContainer`
     - `param: SingleParamSet`
     - `template: TemplateContainer`
     - `engine_settings: SettingContainer`
   - 返回：`BacktestSummary`

#### B. 子模块低层入口（调试拆解链路时使用）

1. `pyo3_quant.backtest_engine.indicators.calculate_indicators`
   - 输入：
     - `processed_data: DataContainer`
     - `indicators_params: Mapping[str, Mapping[str, Mapping[str, Param]]]`
   - 返回：`dict[str, Any]`
2. `pyo3_quant.backtest_engine.signal_generator.generate_signals`
   - 输入：
     - `processed_data: DataContainer`
     - `indicator_dfs_py: Mapping[str, Any]`
     - `signal_params: Mapping[str, Param]`
     - `signal_template: SignalTemplate`
   - 返回：`Any`（通常为信号 DataFrame）
3. `pyo3_quant.backtest_engine.backtester.run_backtest`
   - 输入：
     - `processed_data: DataContainer`
     - `signals_df_py: Any`
     - `backtest_params: BacktestParams`
   - 返回：`Any`（通常为回测结果 DataFrame）
4. `pyo3_quant.backtest_engine.performance_analyzer.analyze_performance`
   - 输入：
     - `data_dict: DataContainer`
     - `backtest_df_py: Any`
     - `performance_params: PerformanceParams`
   - 返回：`dict[str, float]`
5. `pyo3_quant.backtest_engine.optimizer.py_run_optimizer`
   - 输入：
     - `data_dict: DataContainer`
     - `param: SingleParamSet`
     - `template: TemplateContainer`
     - `engine_settings: SettingContainer`
     - `optimizer_config: OptimizerConfig`
   - 返回：`OptimizationResult`
6. `pyo3_quant.backtest_engine.optimizer.py_run_optimizer_benchmark`
   - 输入：
     - `config: OptimizerConfig`
     - `function: BenchmarkFunction`
     - `bounds: Sequence[tuple[float, float]]`
     - `seed: Optional[int] = None`
   - 返回：`tuple[list[float], float]`
7. `pyo3_quant.backtest_engine.walk_forward.run_walk_forward`
   - 输入：
     - `data_dict: DataContainer`
     - `param: SingleParamSet`
     - `template: TemplateContainer`
     - `engine_settings: SettingContainer`
     - `walk_forward_config: WalkForwardConfig`
   - 返回：`WalkForwardResult`
8. `pyo3_quant.backtest_engine.sensitivity.run_sensitivity_test`
   - 输入：
     - `data_dict: DataContainer`
     - `param: SingleParamSet`
     - `template: TemplateContainer`
     - `engine_settings: SettingContainer`
     - `config: SensitivityConfig`
   - 返回：`SensitivityResult`
9. `pyo3_quant.backtest_engine.action_resolver.resolve_actions`
   - 输入：
     - `row_dict: dict`
     - `symbol: str`
     - `sl_exit_in_bar: bool`
     - `tp_exit_in_bar: bool`
   - 返回：`Any`
10. `pyo3_quant.backtest_engine.backtester.frame_state_name`
    - 输入：`state_id: int`
    - 返回：`str`

---

## 3. 类型系统设计

### 3.1 输入类型（`src/types/inputs`）

核心输入类型：

- `Param` / `ParamType`
- `BacktestParams`
- `PerformanceParams`
- `SingleParamSet`
- `DataContainer`
- `OptimizerConfig`
- `WalkForwardConfig`
- `SensitivityConfig`
- `SettingContainer`
- `SignalGroup` / `SignalTemplate` / `TemplateContainer`

### 3.2 输出类型（`src/types/outputs`）

核心输出类型：

- `BacktestSummary`
- `OptimizationResult` / `RoundSummary` / `SamplePoint`
- `WalkForwardResult` / `WindowResult`
- `SensitivityResult` / `SensitivitySample`

### 3.3 枚举类型

核心枚举（均在 Rust 定义并导出）：

- `ExecutionStage`
- `LogicOp`
- `OptimizeMetric`
- `PerformanceMetric`
- `BenchmarkFunction`

这些枚举直接作为 Python API 类型使用，避免字符串魔法值。

### 3.4 调试索引：核心类型构造入口（`__new__`）

以下类型是最常用“入口参数对象”，调试时先检查这些对象是否构造正确：

1. `Param(value, min=None, max=None, dtype=None, optimize=False, log_scale=False, step=0.01)`
2. `BacktestParams(*, ...)`
3. `PerformanceParams(*, ...)`
4. `SingleParamSet(*, indicators=None, signal=None, backtest=None, performance=None)`
5. `DataContainer(mapping, skip_mask, skip_mapping, source, base_data_key)`
6. `TemplateContainer(signal: SignalTemplate)`
7. `SignalGroup(*, logic, comparisons=None, sub_groups=None)`
8. `SignalTemplate(*, entry_long=None, exit_long=None, entry_short=None, exit_short=None)`
9. `SettingContainer(*, execution_stage=ExecutionStage.Performance, return_only_final=False)`
10. `OptimizerConfig(*, ...)`
11. `WalkForwardConfig(*, ..., optimizer_config=None)`
12. `SensitivityConfig(*, ...)`

调试建议：

- 若入口函数报 `TypeError`，优先核对以上对象的构造签名与字段类型。
- 若行为不符合预期，优先检查 `SingleParamSet` 内四个容器字段是否都已正确落值。

### 3.5 调试索引：核心返回对象字段

1. `BacktestSummary`
   - `indicators: Optional[dict]`
   - `signals: Optional[Any]`
   - `backtest_result: Optional[Any]`
   - `performance: Optional[dict[str, float]]`
2. `OptimizationResult`
   - `best_params: SingleParamSet`
   - `optimize_metric: OptimizeMetric`
   - `optimize_value: float`
   - `metrics: dict[str, float]`
   - `total_samples: int`
   - `rounds: int`
   - `history: list[RoundSummary]`
   - `top_k_params: list[SingleParamSet]`
   - `top_k_samples: list[SamplePoint]`
3. `WalkForwardResult`
   - `windows: list[WindowResult]`
   - `optimize_metric: str`
   - `aggregate_test_metrics: dict[str, float]`
4. `WindowResult`
   - `window_id: int`
   - `train_range: tuple[int, int]`
   - `test_range: tuple[int, int]`
   - `best_params: SingleParamSet`
   - `optimize_metric: str`
   - `train_metrics: dict[str, float]`
   - `test_metrics: dict[str, float]`
   - `history: Optional[list[RoundSummary]]`
5. `SensitivityResult`
   - `target_metric: str`
   - `original_value: float`
   - `samples: list[SensitivitySample]`
   - `mean/std/min/max/median/cv: float`
   - `report() -> str`

---

## 4. 构造器调用规范（关键）

### 4.1 关键字参数优先 / 配置类关键字-only

当前配置类构造器统一采用关键字-only 风格（`*`），例如：

- `BacktestParams(...)`
- `PerformanceParams(...)`
- `SingleParamSet(...)`
- `OptimizerConfig(...)`
- `WalkForwardConfig(...)`
- `SensitivityConfig(...)`
- `SettingContainer(...)`
- `SignalGroup(...)`
- `SignalTemplate(...)`

推荐写法：

```python
params = BacktestParams(
    sl_pct=Param(2.0, min=0.5, max=5.0, step=0.1),
    initial_capital=10000.0,
    fee_pct=0.0006,
)
```

不推荐写法（禁止依赖位置参数顺序）：

```python
# 不要这样做
BacktestParams(None, None, None, None, None, None, None, None, None, None, False, ...)
```

### 4.2 `Option[T]` 与 `None`

在当前 `BacktestParams.__new__` 显式签名下：

- `sl_pct=None`、`tp_atr=None` 等是合法输入。
- 不再依赖 `**kwargs` 的反射式提取逻辑。

### 4.3 `set_*` 接口现状（重要）

当前 PyO3 接口里，`set_*` 能力分为两类：

1. **显式方法（可直接调用）**
   - `SingleParamSet`
     - `set_indicators_params`
     - `set_signal_params`
     - `set_backtest_params`
     - `set_performance_params`
     - `set_indicator_param`
     - `set_signal_param`
     - `set_backtest_optimizable_param`
     - `set_backtest_bool_param`
     - `set_backtest_f64_param`
     - `set_performance_metrics`
     - `set_performance_risk_free_rate`
     - `set_performance_leverage_safety_factor`
   - `BacktestParams`
     - `set_optimizable_param`
     - `set_bool_param`
     - `set_f64_param`

2. **属性 setter（不是可直接调用的 `set_xxx()` 方法）**
   - `DataContainer`
     - `mapping = ...`
     - `skip_mask = ...`
     - `source = ...`
     - `base_data_key = ...`
     - `skip_mapping = ...`
   - `BacktestSummary`
     - `indicators = ...`
     - `signals = ...`
     - `backtest_result = ...`
     - `performance = ...`

注意：

- 在 Rust 代码里，这些属性 setter 的实现函数名可能是 `set_source`、`set_indicators`，但 Python 侧不会暴露同名可调用方法；
- Python 侧要触发它们，必须使用属性赋值语法，而不是 `obj.set_source(...)`。

---

## 5. 数据对象语义与可变性

### 5.1 `#[pyclass(get_all, set_all)]` 的读取语义

在 Python 侧访问某些嵌套字段时，常见行为是“取出对象副本/提取值”。
这会导致一个高频错误：

- 直接改深层字段，但没有写回上层容器，最终修改不生效。

错误示例：

```python
# 可能不会生效（取决于字段提取语义）
bt.params.indicators["ohlcv_15m"]["sma"]["period"].value = 20
```

推荐写法（读-改-写回）：

```python
ind = bt.params.indicators
ind["ohlcv_15m"]["sma"]["period"].value = 20
bt.params.indicators = ind
```

同理适用于：

- `bt.params.signal`
- `bt.params.backtest`

### 5.2 `BacktestSummary` DataFrame 字段

`BacktestSummary` 中 `indicators/signals/backtest_result` 涉及 `polars.DataFrame`，
在 Rust 侧通过 `PyDataFrame` 与 `PyAny` 做显式转换。开发时需注意：

- 传入必须是可提取为 `PyDataFrame` 的对象。
- Setter 中的类型错误会直接抛 Python `TypeError`。

---

## 6. Python 编排层职责

### 6.1 `Backtest` 入口类（`py_entry/runner/backtest.py`）

`Backtest` 负责：

1. 组装数据与参数（通过 `setup_utils`）。
2. 调用 Rust 引擎（run/batch/optimize/walk_forward/sensitivity）。
3. 包装运行结果（如 `RunResult`、`BatchResult`、`OptimizeResult`）。

### 6.2 参数构建与预校验（`setup_utils`）

`setup_utils` 当前策略是：

- Python 端做轻量结构校验（类型、嵌套结构、键路径）。
- Rust 端做最终语义约束（业务规则与计算一致性）。

这层预校验的价值：

- 更早失败（Fail Fast）
- 报错路径更清晰（如 `indicators_params.a.b.c`）

---

## 7. 两条优化路径（必须区分）

### 7.1 Rust 内部优化器

- 入口：`Backtest.optimize(...)`
- 调用：`pyo3_quant.backtest_engine.optimizer.py_run_optimizer(...)`
- 特点：采样与优化逻辑在 Rust 内部执行。

### 7.2 Python + Optuna 优化

- 入口：`Backtest.optimize_with_optuna(...)`
- 调用：`py_entry/runner/optuna_optimizer.py`
- 特点：Optuna 在 Python 侧采样，再把 trial 值注入 `SingleParamSet`。

当前注入策略是“每个 trial 新建对象 + 最小必要拷贝（copy-on-write）”：

- `indicators` 仅拷贝命中的路径。
- `signal` 仅拷贝命中的键。
- `backtest` 仅在有更新时新建，并仅替换命中字段。
- `performance` 不参与采样，直接复用。

这样可避免：

- trial 之间状态污染
- 基准参数被意外修改
- 不必要的全量深拷贝开销

---

## 8. 子模块注册与导入稳定性

`src/backtest_engine/mod.rs` 在 Rust 侧统一完成子模块注册，并写入 `sys.modules`：

- `pyo3_quant.backtest_engine.indicators`
- `pyo3_quant.backtest_engine.signal_generator`
- `pyo3_quant.backtest_engine.backtester`
- `pyo3_quant.backtest_engine.performance_analyzer`
- `pyo3_quant.backtest_engine.optimizer`
- `pyo3_quant.backtest_engine.walk_forward`
- `pyo3_quant.backtest_engine.action_resolver`
- `pyo3_quant.backtest_engine.sensitivity`

这保证导入路径稳定，不依赖 Python 层 hack。

---

## 9. Stub 生成与类型检查

### 9.1 生成流程

- Rust 端使用 `pyo3-stub-gen` 注解：
  - `#[gen_stub_pyclass]`
  - `#[gen_stub_pymethods]`
  - `#[gen_stub_pyfunction]`
- `src/lib.rs` 提供 `define_stub_info_gatherer!(stub_info)`
- `just stub` 生成 `python/pyo3_quant/**/*.pyi`

### 9.2 开发校验命令

按项目约定：

1. `just check`
2. `just test`

`just check` 会包含：

- Rust `cargo check`
- `maturin develop`
- `stub_gen`
- Python 类型检查（`ty check`）

---

## 10. 常见错误清单（高频）

### 10.1 误用位置参数

现象：构造器参数错位或调用失败。
原因：配置类采用关键字-only 签名。
修复：一律使用关键字参数。

### 10.2 嵌套对象修改后未写回

现象：看起来赋值成功，运行结果不变。
原因：getter 提取语义导致修改未落回容器。
修复：遵循“读取-修改-写回”。

### 10.3 向 `Param` 字段传入错误类型

现象：`TypeError`（无法提取为 `Param`）。
原因：结构不匹配或 leaf 非 `Param`。
修复：使用 `Param(...)` 显式构建，并通过 `setup_utils` 预校验。

### 10.4 混淆两条优化路径

现象：调试位置错误，误以为 Rust 优化器问题实际在 Optuna 注入。
修复：先确认调用入口：`optimize` vs `optimize_with_optuna`。

### 10.5 修改 Rust 接口后未同步 stub

现象：运行正常但 IDE/类型检查报错。
修复：执行 `just stub` 或直接 `just check`。

---

## 11. 新增接口的推荐流程

1. 在 `src/types` 定义/扩展类型（优先 Rust 类型）。
2. 在 `src/backtest_engine/...` 增加 `#[pyfunction]`。
3. 用 `#[gen_stub_pyfunction]` 明确 Python 签名。
4. 在模块注册函数中显式 `add_function` / `add_submodule`。
5. 需要时将子模块写入 `sys.modules`。
6. 执行 `just check`，确认 stub 与类型检查通过。
7. 最后执行 `just test`。

---

## 12. 设计原则（当前版本）

- Rust 类型优先：Python 不维护镜像模型。
- 接口明确：强类型、关键字-only、避免隐式行为。
- 失败前置：Python 做结构校验，Rust 做最终语义校验。
- 无兼容层：不保留旧路径，不做双轨 API。
- 可维护优先：可读、可审阅、可追踪的接口胜过技巧性实现。
