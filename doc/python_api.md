# Python 接口文档

本文档描述 `pyo3-quant` 回测框架的 Python 接口，包括所有数据类（dataclass）定义和使用示例。

---

## 1. 核心入口：BacktestRunner

`BacktestRunner` 是回测框架的主入口类，支持链式调用。

```python
from py_entry.data_conversion.backtest_runner import BacktestRunner

br = BacktestRunner(enable_timing=True)
br.setup(
    data_source=...,
    indicators_params=...,
    signal_params=...,
    backtest_params=...,
    performance_params=...,
    signal_template=...,
    engine_settings=...,
).run()

result = br.results  # List[BacktestSummary]
```

### setup() 方法参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `data_source` | `DataSourceConfig` | 数据源配置（模拟/获取/直接） |
| `other_params` | `OtherParams` | 其他数据参数（HA、Renko等） |
| `indicators_params` | `IndicatorsParams` | 指标参数字典 |
| `signal_params` | `SignalParams` | 信号参数字典 |
| `backtest_params` | `BacktestParams` | 回测参数 |
| `performance_params` | `PerformanceParams` | 绩效分析参数 |
| `signal_template` | `SignalTemplate` | 信号模板 |
| `engine_settings` | `SettingContainer` | 引擎设置 |
| `param_set_size` | `int` | 参数集大小（用于参数优化） |

---

## 2. 数据类定义

### 2.1 Param - 参数值

用于定义可优化的参数。

```python
from py_entry.data_conversion.types import Param

# 简单创建（自动计算 min/max/step）
param = Param.create(14)  # value=14, min=7, max=28, step=10.5

# 完整创建
param = Param.create(
    initial_value=14,
    initial_min=10,
    initial_max=20,
    initial_step=2,
    optimize=True,    # 是否优化
    log_scale=False,  # 是否使用对数分布
)
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `initial_value` | `float` | 初始值 |
| `initial_min` | `float` | 最小值 |
| `initial_max` | `float` | 最大值 |
| `initial_step` | `float` | 步长 |
| `optimize` | `bool` | 是否启用优化（默认 `True`） |
| `log_scale` | `bool` | 是否使用对数分布（默认 `False`） |

---

### 2.2 BacktestParams - 回测参数

```python
from py_entry.data_conversion.types import BacktestParams, Param

backtest_params = BacktestParams(
    # === 资金管理（必填）===
    initial_capital=10000.0,
    fee_fixed=0,
    fee_pct=0.001,

    # === 离场方式（必填）===
    exit_in_bar=True,  # True=当根K线触发离场, False=下根K线开盘离场

    # === 触发模式（必填）===
    sl_trigger_mode=True,   # True=high/low检测, False=close检测
    tp_trigger_mode=True,
    tsl_trigger_mode=True,

    # === 锚点模式（必填）===
    sl_anchor_mode=False,   # True=high/low锚点, False=close锚点
    tp_anchor_mode=False,
    tsl_anchor_mode=False,

    # === 止损止盈（可选）===
    sl_pct=Param.create(0.02),      # 2% 止损
    tp_pct=Param.create(0.06),      # 6% 止盈
    tsl_pct=Param.create(0.02),     # 2% 跟踪止损

    # === ATR 风控（可选）===
    sl_atr=Param.create(2),         # 2 ATR 止损
    tp_atr=Param.create(6),         # 6 ATR 止盈
    tsl_atr=Param.create(2),        # 2 ATR 跟踪止损
    atr_period=Param.create(14),    # ATR 周期（使用ATR时必填）
    tsl_atr_tight=True,             # 每根K线都更新TSL

    # === PSAR 跟踪止损（可选，三个参数需同时存在）===
    tsl_psar_af0=Param.create(0.02),
    tsl_psar_af_step=Param.create(0.02),
    tsl_psar_max_af=Param.create(0.2),
)
```

---

### 2.3 PerformanceParams - 绩效分析参数

```python
from py_entry.data_conversion.types import PerformanceParams, PerformanceMetric

performance_params = PerformanceParams(
    metrics=[
        PerformanceMetric.TOTAL_RETURN,
        PerformanceMetric.MAX_DRAWDOWN,
        PerformanceMetric.SHARPE_RATIO,
        PerformanceMetric.SORTINO_RATIO,
        PerformanceMetric.CALMAR_RATIO,
        PerformanceMetric.TOTAL_TRADES,
        PerformanceMetric.WIN_RATE,
        PerformanceMetric.PROFIT_LOSS_RATIO,
        PerformanceMetric.AVG_HOLDING_DURATION,
        PerformanceMetric.MAX_SAFE_LEVERAGE,
        PerformanceMetric.ANNUALIZATION_FACTOR,
        PerformanceMetric.HAS_LEADING_NAN_COUNT,
    ],
    risk_free_rate=0.0,         # 无风险利率（默认 0）
    leverage_safety_factor=0.8, # 杠杆安全系数（默认 0.8）
)
```

**可用指标（PerformanceMetric）**：

| 枚举值 | 说明 |
|--------|------|
| `TOTAL_RETURN` | 总回报率 |
| `MAX_DRAWDOWN` | 最大回撤 |
| `MAX_DRAWDOWN_DURATION` | 最大回撤持续时长 |
| `SHARPE_RATIO` | 夏普比率 |
| `SORTINO_RATIO` | 索提诺比率 |
| `CALMAR_RATIO` | 卡尔马比率 |
| `TOTAL_TRADES` | 总交易次数 |
| `AVG_DAILY_TRADES` | 日均交易次数 |
| `WIN_RATE` | 胜率 |
| `PROFIT_LOSS_RATIO` | 盈亏比 |
| `AVG_HOLDING_DURATION` | 平均持仓时长 |
| `MAX_HOLDING_DURATION` | 最大持仓时长 |
| `AVG_EMPTY_DURATION` | 平均空仓时长 |
| `MAX_EMPTY_DURATION` | 最大空仓时长 |
| `MAX_SAFE_LEVERAGE` | 最大可承受杠杆 |
| `ANNUALIZATION_FACTOR` | 年化因子 |
| `HAS_LEADING_NAN_COUNT` | 无效信号计数 |

---

### 2.4 SignalTemplate - 信号模板

定义进出场信号逻辑。

```python
from py_entry.data_conversion.types import SignalGroup, SignalTemplate, LogicOp

# 定义进场信号组
entry_long_group = SignalGroup(
    logic=LogicOp.AND,  # 组内条件使用 AND 连接
    comparisons=[
        "close > bbands_upper",
        "rsi,ohlcv_1h, > $rsi_center",        # 跨时间周期
        "sma_0,ohlcv_4h, > sma_1,ohlcv_4h,",  # 指标比较
    ],
)

entry_short_group = SignalGroup(
    logic=LogicOp.AND,
    comparisons=[
        "close < bbands_lower",
        "rsi,ohlcv_1h, < $rsi_center",
        "sma_0,ohlcv_4h, < sma_1,ohlcv_4h,",
    ],
)

signal_template = SignalTemplate(
    entry_long=entry_long_group,
    exit_long=None,     # None 表示不生成对应信号
    entry_short=entry_short_group,
    exit_short=None,
)
```

**比较表达式语法**：
- 基本格式：`left_operand operator right_operand`
- 跨时间周期：`indicator,timeframe, operator value`
- 参数引用：`$param_name`（引用 `signal_params` 中的参数）

---

### 2.5 SettingContainer - 引擎设置

```python
from py_entry.data_conversion.types import SettingContainer, ExecutionStage

engine_settings = SettingContainer(
    execution_stage=ExecutionStage.PERFORMANCE,  # 执行到哪个阶段
    return_only_final=False,                     # 是否只返回最终结果
)
```

**执行阶段（ExecutionStage）**：

| 枚举值 | 说明 |
|--------|------|
| `NONE` | 不执行 |
| `INDICATOR` | 只计算指标 |
| `SIGNALS` | 计算指标 + 生成信号 |
| `BACKTEST` | 计算指标 + 生成信号 + 回测 |
| `PERFORMANCE` | 完整执行（含绩效分析） |

---

### 2.6 DataGenerationParams - 模拟数据参数

```python
from py_entry.data_conversion.data_generator import DataGenerationParams

simulated_data_config = DataGenerationParams(
    timeframes=["15m", "1h", "4h"],  # 时间周期列表
    start_time=1735689600000,        # 起始时间戳（毫秒）
    num_bars=10000,                  # K线数量
    BaseDataKey="ohlcv_15m",         # 基准数据键
    fixed_seed=42,                   # 随机种子（可选）

    # 波动性参数（可选）
    volatility=0.02,     # 波动率（默认 2%）
    trend=0.0,           # 趋势系数（正值上涨，负值下跌）
    gap_factor=0.5,      # 跳空因子
    extreme_prob=0.0,    # 极端行情概率
    extreme_mult=3.0,    # 极端行情波动倍数
    allow_gaps=True,     # 是否允许跳空
)
```

---

## 3. 指标参数配置

指标参数使用嵌套字典结构：

```python
indicators_params = {
    "ohlcv_15m": {           # 数据源键
        "bbands": {          # 指标名
            "period": Param.create(14),
            "std": Param.create(2),
        }
    },
    "ohlcv_1h": {
        "rsi": {
            "period": Param.create(14),
        }
    },
    "ohlcv_4h": {
        "sma_0": {           # 同类型指标使用后缀区分
            "period": Param.create(8),
        },
        "sma_1": {
            "period": Param.create(16),
        },
    },
}
```

**类型定义**：
```python
IndicatorsParams = Dict[str, Dict[str, Dict[str, Param]]]
# {数据源: {指标名: {参数名: Param}}}
```

---

## 4. 信号参数配置

信号参数用于信号模板中的 `$param_name` 引用：

```python
signal_params = {
    "rsi_upper": Param.create(70, 60, 80, 5),
    "rsi_center": Param.create(50, 40, 60, 5),
    "rsi_lower": Param.create(30, 20, 40, 5),
}
```

**类型定义**：
```python
SignalParams = Dict[str, Param]
```

---

## 5. 完整示例

```python
from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.types import (
    BacktestParams,
    Param,
    PerformanceParams,
    PerformanceMetric,
    LogicOp,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
    ExecutionStage,
)
from py_entry.data_conversion.data_generator import DataGenerationParams

# 1. 数据源配置
data_config = DataGenerationParams(
    timeframes=["15m", "1h"],
    start_time=1735689600000,
    num_bars=5000,
    BaseDataKey="ohlcv_15m",
    fixed_seed=42,
)

# 2. 指标参数
indicators_params = {
    "ohlcv_15m": {
        "sma_fast": {"period": Param.create(10)},
        "sma_slow": {"period": Param.create(30)},
    },
}

# 3. 回测参数
backtest_params = BacktestParams(
    initial_capital=10000.0,
    fee_fixed=0,
    fee_pct=0.001,
    exit_in_bar=True,
    sl_trigger_mode=True,
    tp_trigger_mode=True,
    tsl_trigger_mode=True,
    sl_anchor_mode=False,
    tp_anchor_mode=False,
    tsl_anchor_mode=False,
    sl_pct=Param.create(0.02),
    tp_pct=Param.create(0.04),
)

# 4. 信号模板
signal_template = SignalTemplate(
    entry_long=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast > sma_slow"],
    ),
    entry_short=SignalGroup(
        logic=LogicOp.AND,
        comparisons=["sma_fast < sma_slow"],
    ),
)

# 5. 执行回测
br = BacktestRunner(enable_timing=True)
br.setup(
    data_source=data_config,
    indicators_params=indicators_params,
    signal_params={},
    backtest_params=backtest_params,
    performance_params=PerformanceParams(),
    signal_template=signal_template,
    engine_settings=SettingContainer(execution_stage=ExecutionStage.PERFORMANCE),
).run()

# 6. 获取结果
result = br.results[0]
print(f"总回报率: {result.performance.get('total_return', 0):.2%}")
print(f"最大回撤: {result.performance.get('max_drawdown', 0):.2%}")
```

---

## 6. 类型别名参考

```python
from typing import Dict, List

# 类型别名
IndicatorsParams = Dict[str, Dict[str, Dict[str, Param]]]
SignalParams = Dict[str, Param]
ParamContainer = List[SingleParamSet]
```
