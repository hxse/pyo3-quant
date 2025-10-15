from typing import Optional, List

from py_entry.data_conversion.output import BacktestSummary
from py_entry.data_conversion.input import (
    DataDict,
    ParamSet,
    TemplateConfig,
    EngineSettings,
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
        self._data_dict: Optional[DataDict] = None
        self._param_set: Optional[ParamSet] = None
        self._template_config: Optional[TemplateConfig] = None
        self._engine_settings: Optional[EngineSettings] = None
        self._param_count: Optional[int] = None
        self._period_count: Optional[int] = None

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
        config={},
        param_builder: BaseParamBuilder = None,
    ):
        """构建回测的参数集"""
        self._param_count = config["param_count"]

        if config.get("period_count", None) is None:
            self._period_count = len(self._data_dict.ohlcv)
        else:
            self._period_count = config["period_count"]

        if param_builder is None:
            param_builder = DefaultParamBuilder()

        single_param_sets = []
        for i in range(self._param_count):
            single_set = SingleParamSet(
                indicators=param_builder.build_indicators_params(self._period_count),
                signal=param_builder.build_signal_params(),
                backtest=param_builder.build_backtest_params(),
                risk=param_builder.build_risk_params(),
                performance=param_builder.build_performance_params(),
            )
            single_param_sets.append(single_set)

        self._param_set = ParamSet(
            params=single_param_sets,
            param_count=self._param_count,
            period_count=self._period_count,
        )
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

        self._template_config = TemplateConfig(
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
        validate_no_none_fields(self._param_set)
        validate_no_none_fields(self._template_config)
        validate_no_none_fields(self._engine_settings)
        for i in self._param_set.params:
            validate_no_none_fields(i)

        assert len(self._data_dict.ohlcv) == self._period_count, (
            "period_count应该等于ohlcv数量"
        )

        raw_results = pyo3_quant.run_backtest_engine(
            self._data_dict,
            self._param_set,
            self._template_config,
            self._engine_settings,
        )
        return [BacktestSummary.from_dict(result) for result in raw_results]
