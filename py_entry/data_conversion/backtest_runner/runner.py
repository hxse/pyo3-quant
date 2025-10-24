from typing import Optional, List

from py_entry.data_conversion.output import BacktestSummary
from py_entry.data_conversion.input import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
    SingleParamSet,
)
from .data_builders import BaseDataBuilder, DefaultDataBuilder
from py_entry.data_conversion.helpers import generate_data_dict, validate_no_none_fields


from .param_builders import BaseParamBuilder, DefaultParamBuilder
from .template_builders import (
    BaseSignalTemplateBuilder,
    DefaultSignalTemplateBuilder,
    BaseRiskTemplateBuilder,
    DefaultRiskTemplateBuilder,
)
from .engine_settings_builder import (
    BaseEngineSettingsBuilder,
    DefaultEngineSettingsBuilder,
)

import pyo3_quant


class BacktestRunner:
    """回测配置和执行的主类。

    该类提供了一个链式调用的接口来配置回测的各个方面，
    包括数据、参数集、模板和引擎设置，并最终执行回测。
    """

    def __init__(self):
        """初始化 BacktestRunner 实例。

        设置所有内部状态变量为 None，表示尚未进行任何配置。
        """
        self._data_dict: Optional[DataContainer] = None
        self._param_set: Optional[ParamContainer] = None
        self._template_config: Optional[TemplateContainer] = None
        self._engine_settings: Optional[SettingContainer] = None
        self._param_set: Optional[ParamContainer] = None

    def with_data(self, config={}, data_builder: BaseDataBuilder = None):
        """配置回测所需的数据

        Args:
            data_builder: 数据构建器(可选,默认使用 DefaultDataBuilder)
            **kwargs: 传递给 build_data_dict 的参数
                - timeframes: List[str]
                - start_time: int
                - num_bars: int (默认 1000)
                - brick_size: float (默认 2.0)

        Returns:
            当前的 BacktestRunner 实例,支持链式调用
        """
        if data_builder is None:
            data_builder = DefaultDataBuilder()

        self._data_dict = data_builder.build_data_dict(**config)
        return self

    def with_param_set(
        self,
        param_builder: BaseParamBuilder = None,
    ):
        """构建回测的参数集"""
        if param_builder is None:
            param_builder = DefaultParamBuilder()

        # period_count 可以从 len(data_dict.source["ohlcv"]) 实时计算
        period_count = len(self._data_dict.source["ohlcv"])

        single_param_sets = []
        # param_count 可以从 len(param_set) 实时计算，这里假设只构建一个 SingleParamSet
        # 如果需要多个，则需要外部传入一个数量，或者 param_builder 内部决定
        # 暂时按照 REFACTOR_PLAN.md 的描述，删除 param_count 的计算和传递
        single_set = SingleParamSet(
            indicators=param_builder.build_indicators_params(period_count),
            signal=param_builder.build_signal_params(),
            backtest=param_builder.build_backtest_params(),
            risk=param_builder.build_risk_params(),
            performance=param_builder.build_performance_params(),
        )
        single_param_sets.append(single_set)

        self._param_set = single_param_sets  # ParamSet 现在是 List[SingleParamSet]
        return self

    def with_templates(
        self,
        signal_template_builder: BaseSignalTemplateBuilder = None,
        risk_template_builder: BaseRiskTemplateBuilder = None,
    ):
        """构建回测所需的模板配置。

        不接受参数，通过覆盖 `_build_signal_template_instance()` 和
        `_build_risk_template_instance()` 方法来自定义模板。

        Returns:
            当前的 BacktestRunner 实例，支持链式调用。
        """
        if signal_template_builder is None:
            signal_template_builder = DefaultSignalTemplateBuilder()
        if risk_template_builder is None:
            risk_template_builder = DefaultRiskTemplateBuilder()

        self._template_config = TemplateContainer(
            signal=signal_template_builder.build_signal_template_instance(),
            risk=risk_template_builder.build_risk_template_instance(),
        )

        return self

    def with_engine_settings(
        self, engine_settings_builder: BaseEngineSettingsBuilder = None
    ):
        """构建回测引擎的设置。

        不接受参数，通过覆盖 `_build_engine_settings()` 方法来自定义引擎设置。

        Returns:
            当前的 BacktestRunner 实例，支持链式调用。
        """

        if engine_settings_builder is None:
            engine_settings_builder = DefaultEngineSettingsBuilder()

        self._engine_settings = engine_settings_builder.build_engine_settings()
        return self

    def run(self) -> list[BacktestSummary]:
        """执行回测。

        在执行回测之前，会验证所有必要的配置（数据、参数集、模板、引擎设置）是否已完成。

        Returns:
            回测结果。

        Raises:
            ValueError: 如果任何必要的配置缺失。
        """
        validate_no_none_fields(self._data_dict)
        validate_no_none_fields(self._template_config)
        validate_no_none_fields(self._engine_settings)
        for i in self._param_set:  # ParamSet 现在是 List[SingleParamSet]
            validate_no_none_fields(i)

        # period_count 可以从 len(data_dict.source["ohlcv"]) 实时计算，无需断言

        raw_results = pyo3_quant.run_backtest_engine(
            self._data_dict,
            self._param_set,
            self._template_config,
            self._engine_settings,
        )
        return [BacktestSummary.from_dict(result) for result in raw_results]
