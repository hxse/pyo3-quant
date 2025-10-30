from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional
import numpy as np
import pandas as pd

from py_entry.data_conversion.backtest_runner import (
    BacktestRunner,
    DefaultDataBuilder,
    DefaultParamBuilder,
    DefaultEngineSettingsBuilder,
    SettingContainer,
    ExecutionStage,
)
from py_entry.Test.utils.comparison_tool import (
    assert_indicator_same,
)


@dataclass
class IndicatorTestConfig:
    """指标测试配置"""

    indicator_name: str  # 指标名称,如"bbands"

    # 参数配置(每个timeframe一套),使用标准命名: bbands_0, bbands_1, ...
    params_config: List[Dict[str, Dict[str, Any]]]

    suffixes: List[str]

    # 回测引擎结果提取器
    # 输入: (indicators polars DataFrame, indicator_key, params_dict)
    # 输出: Dict[列名, np.ndarray]
    engine_result_extractor: Callable[[Any, str, Dict], Dict[str, np.ndarray]]

    # pandas-ta结果提取器
    # 输入: (ohlcv pandas DataFrame, indicator_key, params_dict, use_talib)
    # 输出: Dict[列名, np.ndarray]
    pandas_ta_result_extractor: Callable[
        [pd.DataFrame, str, Dict, bool], Dict[str, np.ndarray]
    ]

    # 阈值自定义回调(可选)
    # 输入: 列名(如 "bbands_0_percent")
    # 输出: Dict,可包含 "custom_rtol" 和/或 "custom_atol" 键
    tolerance_customizer: Optional[Callable[[str], Dict[str, float]]] = None

    skip_suffixes: List[str] = field(default_factory=list)


def print_array_details(name, arr):
    """
    打印 NumPy 数组的详细统计信息。

    参数:
        name (str): 数组的名称（用于打印输出）。
        arr (np.ndarray): 要分析的 NumPy 数组。
    """
    print(f"\n--- 数组详细信息: {name} ---")

    # 1. 总数量
    total_count = arr.size
    print(f"1. 总元素数量 (Total Count): {total_count}")

    # 2. 前导 NaN 数量
    # 使用 isfinite() 找到第一个非 NaN/inf 值（有效数据）的索引
    first_valid_idx = np.where(np.isfinite(arr))[0]

    if first_valid_idx.size == 0:
        # 数组全为 NaN 或 Inf
        leading_nan_count = total_count
        first_valid_start = "无有效数据"
    else:
        leading_nan_count = first_valid_idx[0]
        first_valid_start = leading_nan_count

    print(f"2. 前导 NaN 数量 (Leading NaNs): {leading_nan_count}")

    # 3. 前 10 个值 (从头开始)
    print(f"3. 数组头部前 {min(10, total_count)} 个值 (Head):")
    print(arr[:10])

    # 4. 后 10 个值 (从尾部开始)
    if total_count > 10:
        print(f"4. 数组尾部后 10 个值 (Tail):")
        print(arr[-10:])
    elif total_count > 0:
        print(f"4. 数组元素不足 10 个，尾部值同头部:")
        print(arr)
    else:
        print("4. 数组为空，无尾部值。")

    # 5. 前 10 个非前导 NaN 的值 (即第一个有效值开始的 10 个值)
    print(
        f"5. 第一个有效值开始的前 {min(10, total_count - leading_nan_count)} 个值 (Valid Head):"
    )
    if first_valid_idx.size > 0:
        start_idx = first_valid_idx[0]
        # 打印从第一个有效索引开始的 10 个值
        print(arr[start_idx : start_idx + 10])
    else:
        print("数组中无有效非 NaN/Inf 数据可打印。")


def _test_indicator_accuracy(
    config: IndicatorTestConfig,
    data_dict,
    enable_talib: bool = False,
    assert_mode_talib: bool = True,  # True=预期与talib相同, False=预期不同
    assert_mode_pandas_ta: bool = True,  # True=预期与pandas_ta相同, False=预期不同
):
    """
    通用指标测试模板

    逻辑:
    1. 根据config.params_config自动生成CustomParamBuilder
    2. 运行回测引擎(使用CustomEngineSettingsBuilder,设置execution_stage=INDICATOR)
    3. 对每个timeframe的每个indicator_key:
       a. 使用engine_result_extractor提取回测引擎结果
       b. 使用pandas_ta_result_extractor提取pandas_ta结果
       c. 根据assert_mode参数决定使用assert_indicator_same还是assert_indicator_different
    """

    class CustomDataBuilder(DefaultDataBuilder):
        def __init__(self, data):
            self.data = data

        def build_data_dict(self):
            return self.data

    class CustomParamBuilder(DefaultParamBuilder):
        def __init__(self, params_config):
            self.params_config = params_config

        def build_indicators_params(
            self, period_count: int
        ) -> Dict[str, List[Dict[str, Any]]]:
            return self.params_config

    class CustomSettingsBuilder(DefaultEngineSettingsBuilder):
        def build_engine_settings(self) -> SettingContainer:
            return SettingContainer(
                execution_stage=ExecutionStage.INDICATOR,
                return_only_final=True,
            )

    timeframes, data = data_dict
    ohlcv_dfs = data.source["ohlcv"]

    runner = BacktestRunner()
    backtest_results = (
        runner.with_data(data_builder=CustomDataBuilder(data))
        .with_param_set(param_builder=CustomParamBuilder(config.params_config))
        .with_templates()
        .with_engine_settings(engine_settings_builder=CustomSettingsBuilder())
        .run()
    )

    for timeframe_idx, timeframe_params in enumerate(config.params_config["ohlcv"]):
        indicators_df_current_timeframe = backtest_results[0].indicators["ohlcv"][
            timeframe_idx
        ]
        for indicator_key, params_dict in timeframe_params.items():
            # 提取回测引擎结果
            engine_results = config.engine_result_extractor(
                indicators_df_current_timeframe,
                indicator_key,
                config.suffixes,
                params_dict,
            )

            # 将Polars DataFrame转换为Pandas DataFrame以兼容pandas_ta
            pandas_df = ohlcv_dfs[timeframe_idx].to_pandas()
            # 提取pandas_ta结果
            pandas_ta_results = config.pandas_ta_result_extractor(
                pandas_df,
                indicator_key,
                config.suffixes,
                params_dict,
                enable_talib=False,
            )

            names = (
                [indicator_key]
                if not config.suffixes
                else [
                    f"{indicator_key}_{i}"
                    for i in config.suffixes
                    if i not in config.skip_suffixes
                ]
            )

            pandas_ta_diff_count = 0
            talib_diff_count = 0

            for name in names:
                # 获取自定义阈值
                tolerance_overrides = {}
                if config.tolerance_customizer:
                    tolerance_overrides = config.tolerance_customizer(name)

                # 比较结果
                indicator_info = f"{name}: {params_dict}"

                # 提取numpy数组
                engine_array = engine_results[name]
                pandas_ta_array = pandas_ta_results[name]

                # pandas_ta 验证逻辑
                try:
                    assert_indicator_same(
                        engine_array,
                        pandas_ta_array,
                        name,
                        indicator_info,
                        is_nested_call=True,
                        **tolerance_overrides,
                    )
                except AssertionError:
                    if assert_mode_pandas_ta:
                        print_array_details(f"engine {name}", engine_array)
                        print_array_details(f"pandas_ta {name}", pandas_ta_array)
                        raise
                    else:
                        pandas_ta_diff_count += 1

                # talib 验证逻辑
                if enable_talib:
                    talib_results = config.pandas_ta_result_extractor(
                        pandas_df,
                        indicator_key,
                        config.suffixes,
                        params_dict,
                        enable_talib=True,
                    )
                    talib_array = talib_results[name]

                    try:
                        assert_indicator_same(
                            engine_array,
                            talib_array,
                            name,
                            indicator_info,
                            is_nested_call=True,
                            **tolerance_overrides,
                        )
                    except AssertionError:
                        if assert_mode_talib:
                            print_array_details(f"engine {name}", engine_array)
                            print_array_details(f"talib {name}", talib_array)
                            raise
                        else:
                            talib_diff_count += 1

            # 循环结束后检查计数
            if not assert_mode_pandas_ta and pandas_ta_diff_count == 0:
                raise AssertionError(
                    f"预期 pandas_ta 结果至少有一列不同，但所有列都相同。指标: {config.indicator_name}, 参数: {params_dict}"
                )

            if enable_talib and not assert_mode_talib and talib_diff_count == 0:
                raise AssertionError(
                    f"预期 talib 结果至少有一列不同，但所有列都相同。指标: {config.indicator_name}, 参数: {params_dict}"
                )
