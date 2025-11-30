from pdb import Pdb
from typing import Optional
import time
from loguru import logger
import polars as pl

from py_entry.data_conversion.types import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    SignalTemplate,
    SingleParamSet,
    BacktestSummary,
)
from py_entry.data_conversion.helpers import validate_no_none_fields
from py_entry.data_conversion.data_generator import (
    generate_data_dict,
    DataGenerationParams,
    OtherParams,
    OhlcvDataFetchConfig,
    DataSourceConfig,
)
from .setup_utils import (
    build_data,
    build_indicators_params,
    build_signal_params,
    build_backtest_params,
    build_performance_params,
    build_signal_template,
    build_engine_settings,
)
from py_entry.data_conversion.file_utils import (
    ResultBuffersCache,
    SaveConfig,
    UploadConfig,
    convert_backtest_results_to_buffers,
    save_backtest_results,
    upload_backtest_results,
)
from pathlib import Path

import pyo3_quant


class BacktestRunner:
    """回测配置和执行的主类。

    该类提供了简洁的配置方式：
    使用 setup() 方法一次性配置所有组件

    配置完成后，调用 run() 方法执行回测。
    """

    def __init__(self, enable_timing: bool = False):
        """初始化 BacktestRunner 实例。

        设置所有内部状态变量为 None，表示尚未进行任何配置。

        Args:
            enable_timing: 是否启用时间测量和日志记录
        """
        self.data_dict: DataContainer | None = None
        self.param_set: ParamContainer | None = None
        self.template_config: TemplateContainer | None = None
        self.engine_settings: SettingContainer | None = None
        self.results: list[BacktestSummary] | None = None
        # 缓存不同格式的转换结果
        self._buffers_cache: ResultBuffersCache = ResultBuffersCache()
        # 时间测量开关
        self.enable_timing = enable_timing

    def setup(
        self,
        data_source: DataSourceConfig | None = None,
        other_params: OtherParams | None = None,
        indicators_params: IndicatorsParams | None = None,
        signal_params: SignalParams | None = None,
        backtest_params: BacktestParams | None = None,
        performance_params: PerformanceParams | None = None,
        signal_template: SignalTemplate | None = None,
        engine_settings: SettingContainer | None = None,
        param_set_size: int = 1,
    ) -> "BacktestRunner":
        """一次性配置回测所需的所有组件

        Args:
            data_source: 数据源配置，可以是四种类型之一：
                - DataGenerationParams: 模拟数据生成参数
                - OhlcvDataFetchConfig: OHLCV数据获取配置
                - list[pl.DataFrame]: 预定义的OHLCV DataFrame列表
                - None: 使用默认模拟数据配置
            other_params: 其他参数配置对象
            indicators_params: 可选的指标参数，如果提供则直接返回，为None时返回默认值
            signal_params: 可选的信号参数，如果提供则直接返回，为None时返回默认值
            backtest_params: 可选的回测参数，如果提供则直接返回，为None时返回默认值
            performance_params: 可选的性能参数，如果提供则直接返回，为None时返回默认值
            signal_template: 可选的信号模板，如果提供则直接返回，为None时返回默认值
            engine_settings: 可选的引擎设置，如果提供则直接返回，为None时返回默认值

        Returns:
            self: 返回自身以支持链式调用
        """
        start_time = time.perf_counter() if self.enable_timing else None

        # 配置数据
        self.data_dict = build_data(
            data_source=data_source,
            other_params=other_params,
        )

        if self.data_dict is None:
            raise ValueError("data_dict 不能为空")

        # 直接创建单个 SingleParamSet
        self.param_set = [
            SingleParamSet(
                indicators=build_indicators_params(indicators_params),
                signal=build_signal_params(signal_params),
                backtest=build_backtest_params(backtest_params),
                performance=build_performance_params(performance_params),
            )
            for _ in range(param_set_size)
        ]

        # 配置模板
        self.template_config = TemplateContainer(
            signal=build_signal_template(signal_template),
        )

        # 配置引擎设置
        self.engine_settings = build_engine_settings(engine_settings)

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"BacktestRunner.setup() 耗时: {elapsed:.4f}秒")

        return self

    def run(self) -> "BacktestRunner":
        """执行回测。

        在执行回测之前，会验证所有必要的配置（数据、参数集、模板、引擎设置）是否已完成。

        Returns:
            self: 返回自身以支持链式调用。结果存储在 self.results 中。

        Raises:
            ValueError: 如果任何必要的配置缺失。
        """
        start_time = time.perf_counter() if self.enable_timing else None

        if self.data_dict is None:
            raise ValueError("必须先调用 setup() 配置回测参数")
        if self.template_config is None:
            raise ValueError("必须先调用 setup() 配置回测参数")
        if self.engine_settings is None:
            raise ValueError("必须先调用 setup() 配置回测参数")
        if self.param_set is None:
            raise ValueError("必须先调用 setup() 配置回测参数")

        validate_no_none_fields(self.data_dict)
        validate_no_none_fields(self.template_config)
        validate_no_none_fields(self.engine_settings)

        # 验证 param_set 是列表类型
        if not isinstance(self.param_set, list):
            raise ValueError(
                f"param_set 应该是列表类型，但得到的是 {type(self.param_set).__name__}"
            )

        for i in self.param_set:
            validate_no_none_fields(i)

        raw_results = pyo3_quant.backtest_engine.run_backtest_engine(
            self.data_dict,
            self.param_set,
            self.template_config,
            self.engine_settings,
            None,
        )
        self.results = [BacktestSummary.from_dict(result) for result in raw_results]

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"BacktestRunner.run() 耗时: {elapsed:.4f}秒")

        return self

    def _ensure_buffers_cache(self, dataframe_format: str) -> None:
        """确保指定格式的buffers已缓存。

        如果缓存中没有该格式的buffers，则进行转换并缓存。
        该方法假设 self.results 已经存在。

        Args:
            dataframe_format: 需要的格式 ("csv" 或 "parquet")
        """
        # 检查是否已缓存
        if self._buffers_cache.get(dataframe_format) is None:
            # 转换并缓存
            assert self.results is not None, (
                "_ensure_buffers_cache 方法要求 self.results 非空，"
                "但当前为 None。请确保在调用此方法前已执行 run() 方法。"
            )
            buffers = convert_backtest_results_to_buffers(
                self.results, dataframe_format
            )
            self._buffers_cache.set(dataframe_format, buffers)

    def save_results(
        self,
        config: SaveConfig,
    ) -> "BacktestRunner":
        """保存回测结果到本地文件。

        Args:
            config: 保存配置对象

        Returns:
            self: 支持链式调用

        Raises:
            ValueError: 如果没有回测结果
        """
        start_time = time.perf_counter() if self.enable_timing else None

        if self.results is None:
            raise ValueError("必须先调用 run() 执行回测")

        # 确保缓存
        self._ensure_buffers_cache(config.dataframe_format)

        # 调用工具函数保存结果
        save_backtest_results(
            results=self.results,
            config=config,
            cache=self._buffers_cache,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"BacktestRunner.save_results() 耗时: {elapsed:.4f}秒")

        return self

    def upload_results(
        self,
        config: UploadConfig,
    ) -> "BacktestRunner":
        """将结果打包并上传到服务器。

        Args:
            config: 上传配置对象

        Returns:
            self: 支持链式调用

        Raises:
            ValueError: 如果没有回测结果
        """
        start_time = time.perf_counter() if self.enable_timing else None

        if self.results is None:
            raise ValueError("必须先调用 run() 执行回测")

        # 确保缓存
        self._ensure_buffers_cache(config.dataframe_format)

        # 调用工具函数上传结果
        upload_backtest_results(
            results=self.results,
            config=config,
            cache=self._buffers_cache,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"BacktestRunner.upload_results() 耗时: {elapsed:.4f}秒")

        return self
