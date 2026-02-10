"""测试场景加载器

手动导入所有测试场景，并验证与目录结构的一致性
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Callable

# 手动导入所有场景模块
from py_entry.Test.signal.scenarios.scenario_comprehensive import (
    config as comprehensive_config,
    manual_calc as comprehensive_calc,
)
from py_entry.Test.signal.scenarios.scenario_crossover_down import (
    config as crossover_down_config,
    manual_calc as crossover_down_calc,
)
from py_entry.Test.signal.scenarios.scenario_crossover_up import (
    config as crossover_up_config,
    manual_calc as crossover_up_calc,
)
from py_entry.Test.signal.scenarios.scenario_logic_and import (
    config as logic_and_config,
    manual_calc as logic_and_calc,
)
from py_entry.Test.signal.scenarios.scenario_logic_or import (
    config as logic_or_config,
    manual_calc as logic_or_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_and_list import (
    config as offset_and_list_config,
    manual_calc as offset_and_list_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_and_range import (
    config as offset_and_range_config,
    manual_calc as offset_and_range_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_or_list import (
    config as offset_or_list_config,
    manual_calc as offset_or_list_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_or_range import (
    config as offset_or_range_config,
    manual_calc as offset_or_range_calc,
)
from py_entry.Test.signal.scenarios.scenario_parameters import (
    config as parameters_config,
    manual_calc as parameters_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_invalid_mixed_logic import (
    config as invalid_mixed_logic_config,
    manual_calc as invalid_mixed_logic_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_invalid_length_mismatch import (
    config as invalid_length_mismatch_config,
    manual_calc as invalid_length_mismatch_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_invalid_list_mismatch import (
    config as invalid_list_mismatch_config,
    manual_calc as invalid_list_mismatch_calc,
)
from py_entry.Test.signal.scenarios.scenario_offset_invalid_negative import (
    config as invalid_negative_config,
    manual_calc as invalid_negative_calc,
)
from py_entry.Test.signal.scenarios.scenario_nested_ta_strategy import (
    config as nested_ta_strategy_config,
    manual_calc as nested_ta_strategy_calc,
)
from py_entry.Test.signal.scenarios.scenario_multi_timeframe_indicator_comparison import (
    config as multi_timeframe_indicator_comparison_config,
    manual_calc as multi_timeframe_indicator_comparison_calc,
)
from py_entry.Test.signal.scenarios.scenario_cross_data_source import (
    config as cross_data_source_config,
    manual_calc as cross_data_source_calc,
)
from py_entry.Test.signal.scenarios.scenario_scalar_comparison import (
    config as scalar_comparison_config,
    manual_calc as scalar_comparison_calc,
)
from py_entry.Test.signal.scenarios.scenario_simplified_syntax import (
    config as simplified_syntax_config,
    manual_calc as simplified_syntax_calc,
)
from py_entry.Test.signal.scenarios.scenario_syntax_invalid_missing_name import (
    config as syntax_invalid_missing_name_config,
    manual_calc as syntax_invalid_missing_name_calc,
)
from py_entry.Test.signal.scenarios.scenario_syntax_invalid_partial_commas import (
    config as syntax_invalid_partial_commas_config,
    manual_calc as syntax_invalid_partial_commas_calc,
)
from py_entry.Test.signal.scenarios.scenario_syntax_invalid_wrong_order import (
    config as syntax_invalid_wrong_order_config,
    manual_calc as syntax_invalid_wrong_order_calc,
)
from py_entry.Test.signal.scenarios.scenario_zone_cross_up import (
    config as zone_cross_up_config,
    manual_calc as zone_cross_up_calc,
)
from py_entry.Test.signal.scenarios.scenario_zone_cross_down import (
    config as zone_cross_down_config,
    manual_calc as zone_cross_down_calc,
)
from py_entry.Test.signal.scenarios.scenario_zone_cross_dynamic import (
    config as zone_cross_dynamic_config,
    manual_calc as zone_cross_dynamic_calc,
)
from py_entry.Test.signal.scenarios.scenario_zone_cross_param import (
    config as zone_cross_param_config,
    manual_calc as zone_cross_param_calc,
)
from py_entry.Test.signal.scenarios.scenario_zone_cross_negated import (
    config as zone_cross_negated_config,
    manual_calc as zone_cross_negated_calc,
)
from py_entry.Test.signal.scenarios.scenario_zone_cross_inclusive import (
    config as zone_cross_inclusive_config,
    manual_calc as zone_cross_inclusive_calc,
)


@dataclass
class TestScenario:
    """测试场景配置"""

    name: str  # 场景名称（目录名）
    description: str  # 场景描述
    indicators_params: dict  # 指标参数
    signal_params: dict  # 信号参数
    signal_template: object  # 信号模板
    manual_calculator: Callable  # 手写计算函数
    expected_exception: object = None  # 预期的异常类型，None表示预期成功


# 所有场景（包含预期成功和预期报错的）
_ALL_SCENARIOS = [
    # 预期成功的场景（正常功能测试）
    TestScenario(
        name="scenario_comprehensive",
        description=comprehensive_config.DESCRIPTION,
        indicators_params=comprehensive_config.INDICATORS_PARAMS,
        signal_params=comprehensive_config.SIGNAL_PARAMS,
        signal_template=comprehensive_config.SIGNAL_TEMPLATE,
        manual_calculator=comprehensive_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_crossover_down",
        description=crossover_down_config.DESCRIPTION,
        indicators_params=crossover_down_config.INDICATORS_PARAMS,
        signal_params=crossover_down_config.SIGNAL_PARAMS,
        signal_template=crossover_down_config.SIGNAL_TEMPLATE,
        manual_calculator=crossover_down_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_crossover_up",
        description=crossover_up_config.DESCRIPTION,
        indicators_params=crossover_up_config.INDICATORS_PARAMS,
        signal_params=crossover_up_config.SIGNAL_PARAMS,
        signal_template=crossover_up_config.SIGNAL_TEMPLATE,
        manual_calculator=crossover_up_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_zone_cross_up",
        description=zone_cross_up_config.DESCRIPTION,
        indicators_params=zone_cross_up_config.INDICATORS_PARAMS,
        signal_params=zone_cross_up_config.SIGNAL_PARAMS,
        signal_template=zone_cross_up_config.SIGNAL_TEMPLATE,
        manual_calculator=zone_cross_up_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_zone_cross_down",
        description=zone_cross_down_config.DESCRIPTION,
        indicators_params=zone_cross_down_config.INDICATORS_PARAMS,
        signal_params=zone_cross_down_config.SIGNAL_PARAMS,
        signal_template=zone_cross_down_config.SIGNAL_TEMPLATE,
        manual_calculator=zone_cross_down_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_zone_cross_dynamic",
        description=zone_cross_dynamic_config.DESCRIPTION,
        indicators_params=zone_cross_dynamic_config.INDICATORS_PARAMS,
        signal_params=zone_cross_dynamic_config.SIGNAL_PARAMS,
        signal_template=zone_cross_dynamic_config.SIGNAL_TEMPLATE,
        manual_calculator=zone_cross_dynamic_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_zone_cross_param",
        description=zone_cross_param_config.DESCRIPTION,
        indicators_params=zone_cross_param_config.INDICATORS_PARAMS,
        signal_params=zone_cross_param_config.SIGNAL_PARAMS,
        signal_template=zone_cross_param_config.SIGNAL_TEMPLATE,
        manual_calculator=zone_cross_param_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_zone_cross_negated",
        description=zone_cross_negated_config.DESCRIPTION,
        indicators_params=zone_cross_negated_config.INDICATORS_PARAMS,
        signal_params=zone_cross_negated_config.SIGNAL_PARAMS,
        signal_template=zone_cross_negated_config.SIGNAL_TEMPLATE,
        manual_calculator=zone_cross_negated_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_zone_cross_inclusive",
        description=zone_cross_inclusive_config.DESCRIPTION,
        indicators_params=zone_cross_inclusive_config.INDICATORS_PARAMS,
        signal_params=zone_cross_inclusive_config.SIGNAL_PARAMS,
        signal_template=zone_cross_inclusive_config.SIGNAL_TEMPLATE,
        manual_calculator=zone_cross_inclusive_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_logic_and",
        description=logic_and_config.DESCRIPTION,
        indicators_params=logic_and_config.INDICATORS_PARAMS,
        signal_params=logic_and_config.SIGNAL_PARAMS,
        signal_template=logic_and_config.SIGNAL_TEMPLATE,
        manual_calculator=logic_and_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_logic_or",
        description=logic_or_config.DESCRIPTION,
        indicators_params=logic_or_config.INDICATORS_PARAMS,
        signal_params=logic_or_config.SIGNAL_PARAMS,
        signal_template=logic_or_config.SIGNAL_TEMPLATE,
        manual_calculator=logic_or_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_offset_and_list",
        description=offset_and_list_config.DESCRIPTION,
        indicators_params=offset_and_list_config.INDICATORS_PARAMS,
        signal_params=offset_and_list_config.SIGNAL_PARAMS,
        signal_template=offset_and_list_config.SIGNAL_TEMPLATE,
        manual_calculator=offset_and_list_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_offset_and_range",
        description=offset_and_range_config.DESCRIPTION,
        indicators_params=offset_and_range_config.INDICATORS_PARAMS,
        signal_params=offset_and_range_config.SIGNAL_PARAMS,
        signal_template=offset_and_range_config.SIGNAL_TEMPLATE,
        manual_calculator=offset_and_range_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_offset_or_list",
        description=offset_or_list_config.DESCRIPTION,
        indicators_params=offset_or_list_config.INDICATORS_PARAMS,
        signal_params=offset_or_list_config.SIGNAL_PARAMS,
        signal_template=offset_or_list_config.SIGNAL_TEMPLATE,
        manual_calculator=offset_or_list_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_offset_or_range",
        description=offset_or_range_config.DESCRIPTION,
        indicators_params=offset_or_range_config.INDICATORS_PARAMS,
        signal_params=offset_or_range_config.SIGNAL_PARAMS,
        signal_template=offset_or_range_config.SIGNAL_TEMPLATE,
        manual_calculator=offset_or_range_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_parameters",
        description=parameters_config.DESCRIPTION,
        indicators_params=parameters_config.INDICATORS_PARAMS,
        signal_params=parameters_config.SIGNAL_PARAMS,
        signal_template=parameters_config.SIGNAL_TEMPLATE,
        manual_calculator=parameters_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_nested_ta_strategy",
        description=nested_ta_strategy_config.DESCRIPTION,
        indicators_params=nested_ta_strategy_config.INDICATORS_PARAMS,
        signal_params=nested_ta_strategy_config.SIGNAL_PARAMS,
        signal_template=nested_ta_strategy_config.SIGNAL_TEMPLATE,
        manual_calculator=nested_ta_strategy_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_multi_timeframe_indicator_comparison",
        description=multi_timeframe_indicator_comparison_config.DESCRIPTION,
        indicators_params=multi_timeframe_indicator_comparison_config.INDICATORS_PARAMS,
        signal_params=multi_timeframe_indicator_comparison_config.SIGNAL_PARAMS,
        signal_template=multi_timeframe_indicator_comparison_config.SIGNAL_TEMPLATE,
        manual_calculator=multi_timeframe_indicator_comparison_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_cross_data_source",
        description=cross_data_source_config.DESCRIPTION,
        indicators_params=cross_data_source_config.INDICATORS_PARAMS,
        signal_params=cross_data_source_config.SIGNAL_PARAMS,
        signal_template=cross_data_source_config.SIGNAL_TEMPLATE,
        manual_calculator=cross_data_source_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_scalar_comparison",
        description=scalar_comparison_config.DESCRIPTION,
        indicators_params=scalar_comparison_config.INDICATORS_PARAMS,
        signal_params=scalar_comparison_config.SIGNAL_PARAMS,
        signal_template=scalar_comparison_config.SIGNAL_TEMPLATE,
        manual_calculator=scalar_comparison_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    TestScenario(
        name="scenario_simplified_syntax",
        description=simplified_syntax_config.DESCRIPTION,
        indicators_params=simplified_syntax_config.INDICATORS_PARAMS,
        signal_params=simplified_syntax_config.SIGNAL_PARAMS,
        signal_template=simplified_syntax_config.SIGNAL_TEMPLATE,
        manual_calculator=simplified_syntax_calc.calculate_signals,
        expected_exception=None,  # 预期成功
    ),
    # 预期报错的场景（边界行为测试）
    TestScenario(
        name="scenario_offset_invalid_mixed_logic",
        description=invalid_mixed_logic_config.DESCRIPTION,
        indicators_params=invalid_mixed_logic_config.INDICATORS_PARAMS,
        signal_params=invalid_mixed_logic_config.SIGNAL_PARAMS,
        signal_template=invalid_mixed_logic_config.SIGNAL_TEMPLATE,
        manual_calculator=invalid_mixed_logic_calc.calculate_signals,
        expected_exception=invalid_mixed_logic_config.EXPECTED_EXCEPTION,
    ),
    TestScenario(
        name="scenario_offset_invalid_length_mismatch",
        description=invalid_length_mismatch_config.DESCRIPTION,
        indicators_params=invalid_length_mismatch_config.INDICATORS_PARAMS,
        signal_params=invalid_length_mismatch_config.SIGNAL_PARAMS,
        signal_template=invalid_length_mismatch_config.SIGNAL_TEMPLATE,
        manual_calculator=invalid_length_mismatch_calc.calculate_signals,
        expected_exception=invalid_length_mismatch_config.EXPECTED_EXCEPTION,
    ),
    TestScenario(
        name="scenario_offset_invalid_list_mismatch",
        description=invalid_list_mismatch_config.DESCRIPTION,
        indicators_params=invalid_list_mismatch_config.INDICATORS_PARAMS,
        signal_params=invalid_list_mismatch_config.SIGNAL_PARAMS,
        signal_template=invalid_list_mismatch_config.SIGNAL_TEMPLATE,
        manual_calculator=invalid_list_mismatch_calc.calculate_signals,
        expected_exception=invalid_list_mismatch_config.EXPECTED_EXCEPTION,
    ),
    TestScenario(
        name="scenario_offset_invalid_negative",
        description=invalid_negative_config.DESCRIPTION,
        indicators_params=invalid_negative_config.INDICATORS_PARAMS,
        signal_params=invalid_negative_config.SIGNAL_PARAMS,
        signal_template=invalid_negative_config.SIGNAL_TEMPLATE,
        manual_calculator=invalid_negative_calc.calculate_signals,
        expected_exception=invalid_negative_config.EXPECTED_EXCEPTION,
    ),
    TestScenario(
        name="scenario_syntax_invalid_missing_name",
        description=syntax_invalid_missing_name_config.DESCRIPTION,
        indicators_params=syntax_invalid_missing_name_config.INDICATORS_PARAMS,
        signal_params=syntax_invalid_missing_name_config.SIGNAL_PARAMS,
        signal_template=syntax_invalid_missing_name_config.SIGNAL_TEMPLATE,
        manual_calculator=syntax_invalid_missing_name_calc.calculate_signals,
        expected_exception=syntax_invalid_missing_name_config.EXPECTED_EXCEPTION,
    ),
    TestScenario(
        name="scenario_syntax_invalid_partial_commas",
        description=syntax_invalid_partial_commas_config.DESCRIPTION,
        indicators_params=syntax_invalid_partial_commas_config.INDICATORS_PARAMS,
        signal_params=syntax_invalid_partial_commas_config.SIGNAL_PARAMS,
        signal_template=syntax_invalid_partial_commas_config.SIGNAL_TEMPLATE,
        manual_calculator=syntax_invalid_partial_commas_calc.calculate_signals,
        expected_exception=syntax_invalid_partial_commas_config.EXPECTED_EXCEPTION,
    ),
    TestScenario(
        name="scenario_syntax_invalid_wrong_order",
        description=syntax_invalid_wrong_order_config.DESCRIPTION,
        indicators_params=syntax_invalid_wrong_order_config.INDICATORS_PARAMS,
        signal_params=syntax_invalid_wrong_order_config.SIGNAL_PARAMS,
        signal_template=syntax_invalid_wrong_order_config.SIGNAL_TEMPLATE,
        manual_calculator=syntax_invalid_wrong_order_calc.calculate_signals,
        expected_exception=syntax_invalid_wrong_order_config.EXPECTED_EXCEPTION,
    ),
]


def _validate_scenarios() -> None:
    """
    验证手动导入的场景与目录中的场景是否完全匹配

    异常：
        RuntimeError: 如果手动导入和目录扫描不匹配
    """
    # 扫描目录中的场景
    scenario_dir = Path(__file__).parent
    dir_scenarios = sorted(
        [
            d.name
            for d in scenario_dir.iterdir()
            if d.is_dir()
            and d.name.startswith("scenario_")
            and not d.name.startswith("__")
        ]
    )

    # 获取手动导入的场景名称
    imported_scenarios = sorted([s.name for s in _ALL_SCENARIOS])

    # 检查是否完全匹配
    if dir_scenarios != imported_scenarios:
        missing_in_imports = set(dir_scenarios) - set(imported_scenarios)
        extra_in_imports = set(imported_scenarios) - set(dir_scenarios)

        error_msg = "场景导入与目录不匹配！\n"
        if missing_in_imports:
            error_msg += f"  目录中存在但未导入: {sorted(missing_in_imports)}\n"
        if extra_in_imports:
            error_msg += f"  已导入但目录中不存在: {sorted(extra_in_imports)}\n"

        raise RuntimeError(error_msg)


def get_all_scenarios() -> list[TestScenario]:
    """
    获取所有测试场景

    返回：
        TestScenario 列表，按名称排序
    """
    # 验证场景完整性
    _validate_scenarios()

    # 返回已按名称排序的场景列表
    return _ALL_SCENARIOS


def get_valid_scenarios() -> list[TestScenario]:
    """
    获取预期成功的测试场景

    返回：
        TestScenario 列表，按名称排序
    """
    # 验证场景完整性
    _validate_scenarios()

    # 返回已按名称排序的有效场景列表
    return sorted(
        [s for s in _ALL_SCENARIOS if s.expected_exception is None],
        key=lambda s: s.name,
    )


def get_invalid_scenarios() -> list[TestScenario]:
    """
    获取预期报错的测试场景

    返回：
        TestScenario 列表，按名称排序
    """
    # 验证场景完整性
    _validate_scenarios()

    # 返回已按名称排序的无效场景列表
    return sorted(
        [s for s in _ALL_SCENARIOS if s.expected_exception is not None],
        key=lambda s: s.name,
    )


def get_scenario_by_name(name: str) -> TestScenario:
    """
    按名称获取特定场景

    参数：
        name: 场景名称

    返回：
        TestScenario 对象

    异常：
        ValueError: 场景不存在
    """
    for scenario in _ALL_SCENARIOS:
        if scenario.name == name:
            return scenario
    raise ValueError(f"场景 '{name}' 不存在")


# 导出
__all__ = [
    "TestScenario",
    "get_all_scenarios",
    "get_valid_scenarios",
    "get_invalid_scenarios",
    "get_scenario_by_name",
]
