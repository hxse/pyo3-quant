from typing import Optional, List

from py_entry.data_conversion.input import (
    DataDict,
    ParamSet,
    TemplateConfig,
    EngineSettings,
    SingleParamSet,
)
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

    def with_data(
        self,
        timeframes: List[str],
        start_time: int,
        num_bars: int,
        brick_size: float = 2.0,
    ):
        """配置回测所需的数据。

        通过调用 `generate_data_dict` 辅助函数来生成数据字典。

        Args:
            timeframes: 时间框架列表，例如 ["15m", "1h"]。
            start_time: 数据开始时间戳（毫秒）。
            num_bars: 要生成的数据条数。
            brick_size: 砖块大小，用于数据生成（默认为 2.0）。

        Returns:
            当前的 BacktestRunner 实例，支持链式调用。

        Raises:
            ValueError: 如果数据生成失败。
        """
        self._data_dict = generate_data_dict(
            timeframes, start_time, num_bars, brick_size
        )
        return self

    def with_param_set(self, param_count: int, param_builder: BaseParamBuilder = None):
        """构建回测的参数集"""

        if param_builder is None:
            param_builder = DefaultParamBuilder()

        self._param_count = param_count
        self._period_count = len(self._data_dict.ohlcv)

        single_param_sets = []
        for i in range(param_count):
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

    def run(self):
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

        return pyo3_quant.run_backtest_engine(
            self._data_dict,
            self._param_set,
            self._template_config,
            self._engine_settings,
        )
