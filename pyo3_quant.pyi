import polars
from typing import Any, Dict, List, Optional

# 导入项目中已有的类型定义
from py_entry.types import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
    BacktestSummary,
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    SignalTemplate,
)

# ===== Errors Submodule =====

class errors:
    """
    Custom exceptions raised from the Rust core.
    """
    # Base Quant Error
    class PyQuantError(Exception): ...

    # Backtest Errors
    class PyBacktestError(Exception): ...
    class PyArrayLengthMismatchError(PyBacktestError): ...
    class PyMissingColumnError(PyBacktestError): ...
    class PyNonContiguousDataError(PyBacktestError): ...
    class PyInvalidParameterError(PyBacktestError): ...
    class PyEmptyDataFrameError(PyBacktestError): ...
    class PyContainsNaNError(PyBacktestError): ...
    class PyATRCalculationError(PyBacktestError): ...
    class PyOHLCVNotFoundError(PyBacktestError): ...
    class PyDataValidationError(PyBacktestError): ...
    class PyMissingDataSourceError(PyBacktestError): ...
    class PyValidationError(PyBacktestError): ...

    # Indicator Errors
    class PyIndicatorError(Exception): ...
    class PyIndicatorParameterNotFoundError(PyIndicatorError): ...
    class PyIndicatorInvalidParameterError(PyIndicatorError): ...
    class PyIndicatorColumnNotFoundError(PyIndicatorError): ...
    class PyIndicatorDataTooShortError(PyIndicatorError): ...
    class PyIndicatorNotImplementedError(PyIndicatorError): ...
    class PyDataSourceNotFoundError(PyIndicatorError): ...
    class PyDataSourceLengthMismatchError(PyIndicatorError): ...

    # Signal Errors
    class PySignalError(Exception): ...
    class PySourceNotFoundError(PySignalError): ...
    class PySourceIndexOutOfBoundsError(PySignalError): ...
    class PyColumnNotFoundError(PySignalError): ...
    class PyInvalidSourceFormatError(PySignalError): ...
    class PyMappingColumnNotFound(PySignalError): ...
    class PyMappingCastError(PySignalError): ...
    class PyMappingApplyError(PySignalError): ...
    class PyParameterNotFoundError(PySignalError): ...
    class PyInvalidInputError(PySignalError): ...
    class PyParseError(PySignalError): ...
    class PyInvalidOffsetError(PySignalError): ...

class backtest_engine:
    @staticmethod
    def run_backtest_engine(
        data_dict: DataContainer,
        param_set: ParamContainer,
        template: TemplateContainer,
        engine_settings: SettingContainer,
    ) -> List[Dict[str, Any]]:
        """运行回测引擎

        Returns:
            回测结果摘要字典列表 (Python 端会通过 BacktestSummary.from_dict 进一步转换)
        """
        ...

    @staticmethod
    def run_single_backtest(
        data_dict: DataContainer,
        param: Any,  # 传入 SimpleNamespace 或符合结构的字典
        template: TemplateContainer,
        engine_settings: SettingContainer,
    ) -> Dict[str, Any]:
        """运行单次回测"""
        ...

    @staticmethod
    def calculate_indicators(
        processed_data: DataContainer, indicators_params: IndicatorsParams
    ) -> Dict[str, polars.DataFrame]:
        """计算技术指标"""
        ...

    @staticmethod
    def generate_signals(
        processed_data: DataContainer,
        indicator_dfs: Dict[str, polars.DataFrame],
        signal_params: SignalParams,
        signal_template: SignalTemplate,
    ) -> polars.DataFrame:
        """生成交易信号"""
        ...

    @staticmethod
    def run_backtest(
        processed_data: DataContainer,
        signals_df: polars.DataFrame,
        backtest_params: BacktestParams,
    ) -> polars.DataFrame:
        """运行标准回测"""
        ...

    @staticmethod
    def analyze_performance(
        data_dict: DataContainer,
        backtest_df: polars.DataFrame,
        performance_params: PerformanceParams,
    ) -> Dict[str, float]:
        """分析回测绩效"""
        ...

    class optimizer:
        @staticmethod
        def py_run_optimizer(
            data_dict: DataContainer,
            param: Any,
            template: TemplateContainer,
            engine_settings: SettingContainer,
            optimizer_config: Any,
        ) -> Dict[str, Any]:
            """运行参数优化"""
            ...

    class walk_forward:
        @staticmethod
        def py_run_walk_forward(
            data_dict: DataContainer,
            param: Any,
            template: TemplateContainer,
            engine_settings: SettingContainer,
            config: Any,
        ) -> Dict[str, Any]:
            """运行向前滚动优化"""
            ...
