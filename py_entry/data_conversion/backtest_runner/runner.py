from typing import Optional, Any
import polars as pl

from py_entry.data_conversion.output import BacktestSummary
from py_entry.data_conversion.input import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
    SingleParamSet,
)
from .data_builders import BaseDataBuilder, DefaultDataBuilder
from py_entry.data_conversion.helpers import validate_no_none_fields
from py_entry.data_conversion.helpers.data_generator import (
    DataGenerationParams,
    OtherParams,
    OhlcvDataFetchConfig,
)


from .param_builders import BaseParamBuilder, DefaultParamBuilder
from .template_builders import (
    BaseSignalTemplateBuilder,
    DefaultSignalTemplateBuilder,
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

    def with_data(
        self,
        simulated_data_config: DataGenerationParams | None = None,
        ohlcv_data_config: OhlcvDataFetchConfig | None = None,
        predefined_ohlcv_dfs: list[pl.DataFrame] | None = None,
        other_params: OtherParams | None = None,
        data_builder: BaseDataBuilder | None = None,
    ) -> "BacktestRunner":
        """配置回测所需的数据

        Args:
            simulated_data_config: 模拟数据生成参数配置对象
            ohlcv_data_config: OHLCV数据获取配置对象
            predefined_ohlcv_dfs: 预定义的OHLCV DataFrame列表
            other_params: 其他参数配置对象
            data_builder: 数据构建器(可选,默认使用 DefaultDataBuilder)

        Returns:
            当前的 BacktestRunner 实例,支持链式调用
        """
        if data_builder is None:
            data_builder = DefaultDataBuilder()

        self._data_dict = data_builder.build_data_dict(
            simulated_data_config=simulated_data_config,
            ohlcv_data_config=ohlcv_data_config,
            predefined_ohlcv_dfs=predefined_ohlcv_dfs,
            other_params=other_params,
        )
        return self

    def with_param_set(
        self,
        param_builder: BaseParamBuilder | None = None,
    ) -> "BacktestRunner":
        """构建回测的参数集"""
        if param_builder is None:
            param_builder = DefaultParamBuilder()

        # period_count 可以从 len(data_dict.source["ohlcv"]) 实时计算
        if self._data_dict is None:
            raise ValueError("必须先调用 with_data() 配置数据")

        period_count = len(self._data_dict.source["ohlcv"])

        single_param_sets: list[SingleParamSet] = []
        # param_count 可以从 len(param_set) 实时计算，这里假设只构建一个 SingleParamSet
        # 如果需要多个，则需要外部传入一个数量，或者 param_builder 内部决定
        # 暂时按照 REFACTOR_PLAN.md 的描述，删除 param_count 的计算和传递
        single_set = SingleParamSet(
            indicators=param_builder.build_indicators_params(period_count),
            signal=param_builder.build_signal_params(),
            backtest=param_builder.build_backtest_params(),
            performance=param_builder.build_performance_params(),
        )
        single_param_sets.append(single_set)

        self._param_set = single_param_sets  # ParamSet 现在是 List[SingleParamSet]
        return self

    def with_templates(
        self,
        signal_template_builder: BaseSignalTemplateBuilder | None = None,
    ) -> "BacktestRunner":
        """构建回测所需的模板配置。

        不接受参数，通过覆盖 `_build_signal_template_instance()`

        Returns:
            当前的 BacktestRunner 实例，支持链式调用。
        """
        if signal_template_builder is None:
            signal_template_builder = DefaultSignalTemplateBuilder()

        self._template_config = TemplateContainer(
            signal=signal_template_builder.build_signal_template_instance(),
        )

        return self

    def with_engine_settings(
        self, engine_settings_builder: BaseEngineSettingsBuilder | None = None
    ) -> "BacktestRunner":
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
        if self._data_dict is None:
            raise ValueError("必须先调用 with_data() 配置数据")
        if self._template_config is None:
            raise ValueError("必须先调用 with_templates() 配置模板")
        if self._engine_settings is None:
            raise ValueError("必须先调用 with_engine_settings() 配置引擎设置")
        if self._param_set is None:
            raise ValueError("必须先调用 with_param_set() 配置参数集")

        validate_no_none_fields(self._data_dict)
        validate_no_none_fields(self._template_config)
        validate_no_none_fields(self._engine_settings)
        for i in self._param_set:
            validate_no_none_fields(i)

        # period_count 可以从 len(data_dict.source["ohlcv"]) 实时计算，无需断言

        raw_results: list[dict[str, Any]] = (
            pyo3_quant.backtest_engine.run_backtest_engine(
                self._data_dict,
                self._param_set,
                self._template_config,
                self._engine_settings,
                None,
            )
        )
        return [BacktestSummary.from_dict(result) for result in raw_results]
