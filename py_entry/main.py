import sys
from pathlib import Path

root_path = next(
    (p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file()),
    None,
)
if root_path:
    sys.path.insert(0, str(root_path))

import polars as pl
import pyo3_quant
import time

from py_entry.data_conversion.input import (
    BacktestConfig,
    DataDict,
    ParamSet,
    TemplateConfig,
)
from py_entry.data_generator import generate_data_dict
from py_entry.templates.signal_template import create_signal_template_instance
from py_entry.templates.risk_template import create_risk_template_instance
from py_entry.configs import create_param_set

print("-" * 30)
print("线程数", pl.thread_pool_size())

# 原有调用
res = pyo3_quant.sum_as_string(5, 25)
print(res)  # 输出: 40

print("-" * 30)
print("线程数", pl.thread_pool_size())

# 生成示例 data_dict
data_dict = generate_data_dict(
    timeframes=["15m", "1h"], start_time=1735689600000, num_bars=200, brick_size=2.0
)

# 创建 param_set
param_set = create_param_set(len(data_dict.ohlcv))

# 创建配置
config = BacktestConfig(is_only_performance=False)

# 创建模板配置
template_config = TemplateConfig(
    signal=create_signal_template_instance(), risk=create_risk_template_instance()
)

# 传递给 Rust
print("-" * 30)
print("测试回测引擎骨架")
start_time = time.perf_counter()

# 调用新的回测引擎入口函数
backtest_result = pyo3_quant.run_backtest_engine(
    data_dict,  # DataDict dataclass
    param_set,  # ParamSet dataclass
    template_config,  # TemplateConfig dataclass
    config,  # BacktestConfig dataclass
)

print("回测引擎结果:", backtest_result)

print("耗时", time.perf_counter() - start_time)
