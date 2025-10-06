import polars as pl
import pyo3_quant
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Param:
    """定义单个参数的搜索空间和实际值"""

    # 1. --- 没有默认值的参数 (必须在最前面) ---
    initial_value: float  # REQUIRED
    initial_min: float  # REQUIRED
    initial_max: float  # REQUIRED
    initial_step: float  # REQUIRED

    # 2. --- 带有默认值的参数 (必须在后面) ---
    value: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None

    def __post_init__(self):
        """
        初始化完成后自动调用。
        调用 reset()，但通过参数控制只对当前值为 None 的属性进行赋值。
        """
        # 在这里调用 reset，并标记为初始化模式（只对 None 赋值）
        # 这样就不需要手动在外部调用  了
        self.reset(only_none=True)

    def reset(self, only_none: bool = False):
        """
        将当前参数值重置为其对应的初始值。

        Args:
            only_none (bool): 如果为 True，则只对当前值为 None 的属性进行赋值。
                              如果为 False (默认)，则强制覆盖所有属性。

        Returns:
            Param: 返回对象自身 (self)，支持链式调用。
        """
        target_attrs = ["value", "min", "max", "step"]

        for attr_name in target_attrs:
            # 获取当前值
            current_value = getattr(self, attr_name)

            # 判断是否需要赋值：
            # (不是 only_none 模式 - 意味着强制覆盖) OR (当前值为 None)
            if not only_none or current_value is None:
                initial_attr_name = f"initial_{attr_name}"

                if hasattr(self, initial_attr_name):
                    initial_value = getattr(self, initial_attr_name)
                    setattr(self, attr_name, initial_value)

        return self

    def __getitem__(self, key):
        """支持PyO3的字典式访问：obj["key"]"""
        return getattr(self, key)


# os.environ["POLARS_MAX_THREADS"] = "1"


# print("-" * 30)
# print("线程数", pl.thread_pool_size())

# 原有调用
res = pyo3_quant.sum_as_string(5, 25)
print(res)  # 输出: 40

# # 新增调用：创建 DataFrame 并打印
# df = pyo3_quant.create_dataframe()
# print(df)  # 直接打印 PyDataFrame，依赖其 Python 侧表示

# # 新增调用：从 Python 创建 DataFrame 并传递到 Rust 处理
# py_df = pl.DataFrame({"date": [pl.date(2023, 1, 1), pl.date(2023, 2, 1)]})
# processed_df = pyo3_quant.process_dataframe(py_df)
# print(processed_df)  # 输出处理后的 DataFrame


# print("-" * 30)
# print("线程数", pl.thread_pool_size())
# # --- 最小示例：处理多个 DataFrame 的 Vec ---
# # 创建多个 Polars DataFrame
# dfs = [
#     pl.DataFrame({"id": [1, 2], "value": [10.0, 20.0]}),
#     pl.DataFrame({"id": [3, 4], "value": [30.0, 40.0]}),
#     pl.DataFrame({"id": [5], "value": [50.0]}),
# ]

# # 调用入口函数：并发处理 Vec<DataFrame>，每个内部单线程
# processed_dfs = pyo3_quant.process_dataframes_vec(dfs)
# print("\n--- 处理后的 DataFrame 列表 ---")
# for i, pdf in enumerate(processed_dfs):
#     print(f"DataFrame {i + 1}:\n{pdf}\n")


print("-" * 30)
print("线程数", pl.thread_pool_size())

# --- 更新调用：使用 data_dict, param_set, config 调用 process_all_configs ---

from data_generator import generate_data_dict

# 生成示例 data_dict
data_dict = generate_data_dict(
    timeframes=["15m", "1h"], start_time=1735689600000, num_bars=200, brick_size=2.0
)

# 创建 param_set：基于原有 all_configs_py 逻辑，3 个变体
param_set = []
signal_template = [{"a": "close", "b": "sma_0", "compare": "gt", "col": "signal"}]
risk_template = {
    "source": "balance",  # 可选值: "balance", "equity"
    "method": "ema",  # 可选值: "ema", "sma", "wma" 等
}
backtest_config = {
    "sl": Param(initial_value=2.0, initial_min=0.5, initial_max=5.0, initial_step=0.1),
    "tp": Param(initial_value=2.0, initial_min=0.5, initial_max=5.0, initial_step=0.1),
    "position_pct": Param(
        initial_value=1.0, initial_min=0.1, initial_max=1.0, initial_step=0.1
    ),
}

signal_params = {
    "b": Param(initial_value=20.0, initial_min=5.0, initial_max=100.0, initial_step=5.0)
}
risk_params = {
    "size_up_pct": Param(
        initial_value=1.5, initial_min=1.0, initial_max=3.0, initial_step=0.1
    ),
    "size_down_pct": Param(
        initial_value=0.5, initial_min=0.1, initial_max=1.0, initial_step=0.1
    ),
}
import pdb

pdb.set_trace()
for i in range(len(data_dict["data"]["ohlcv"])):
    # 使用纯 dict 定义参数，类似于原有 sma_0, sma_1
    sma_0 = {
        "period": Param(
            initial_value=14 + i, initial_min=5, initial_max=50, initial_step=1
        ),
        "weight": Param(
            initial_value=0.5 + i / 10,
            initial_min=0.1,
            initial_max=1.0,
            initial_step=0.1,
        ),
    }
    sma_1 = {
        "period": Param(
            initial_value=50 + i, initial_min=10, initial_max=100, initial_step=5
        ),
        "weight": Param(
            initial_value=0.8 + i / 10,
            initial_min=0.1,
            initial_max=1.0,
            initial_step=0.1,
        ),
    }

    indicator_config = [
        {
            "sma_0": sma_0,
            "sma_1": sma_1,
        }
    ]

    performance_params = {"metrics": ["total_return", "sharpe_ratio", "max_drawdown"]}

    param_item = {
        "indicator": indicator_config,
        "backtest": backtest_config,
        "signal": signal_params,
        "risk": risk_params,
        "performance": performance_params,  # 新增这一行
    }
    param_set.append(param_item)

# 创建 config
config = {"is_only_performance": False}
template = {"signal": signal_template, "risk": risk_template}

# import pdb

# pdb.set_trace()
# 调用更新后的函数
# result_summary = pyo3_quant.calculate_metrics(data_dict, param_set, template, config)

# print("\n--- 更新后的处理结果 ---")
# print(f"Passed {len(param_set)} param sets from Python to Rust.")
# print(result_summary)

print("-" * 30)
print("测试回测引擎骨架")
start_time = time.perf_counter()

# 调用新的回测引擎入口函数
backtest_result = pyo3_quant.run_backtest_engine(data_dict, param_set, template, config)

print("回测引擎结果:", backtest_result)

print("耗时", time.perf_counter() - start_time)
# import pdb

# pdb.set_trace()
