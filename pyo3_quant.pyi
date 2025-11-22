"""Type stubs for pyo3_quant module."""

from typing import Any, Optional, Dict, List, Union
import polars as pl

# 导入项目中已有的类型定义
from py_entry.data_conversion.input import (
    Param,
    CompareOp,
    LogicOp,
    PerformanceMetric,
    ExecutionStage,
    ParamOperand,
    SignalDataOperand,
    SignalCondition,
    SignalGroup,
    SignalTemplate,
    BacktestParams,
    PerformanceParams,
    SingleParamSet,
    ParamContainer,
    SettingContainer,
    TemplateContainer,
    DataContainer,
)
from py_entry.data_conversion.output import BacktestSummary

# 类型别名
IndicatorsParams = Dict[str, List[Dict[str, Dict[str, Param]]]]
SignalParams = Dict[str, Param]
SignalRightOperand = Union[SignalDataOperand, ParamOperand]

# ===== 模块定义 =====

class minimal_working_example:
    @staticmethod
    def sum_as_string(a: int, b: int) -> str:
        """将两个整数相加并返回结果的字符串表示"""
        ...

class backtest_engine:
    @staticmethod
    def run_backtest_engine(
        data_dict: DataContainer,
        param_set: ParamContainer,
        template_config: TemplateContainer,
        engine_settings: SettingContainer,
        debug_config: Optional[BacktestSummary] = None,
    ) -> List[BacktestSummary]:
        """运行回测引擎

        Args:
            data_dict: 市场数据容器
            param_set: 回测参数集合
            template_config: 信号模板配置
            engine_settings: 引擎设置
            debug_config: 可选的已有回测结果，用于增量计算

        Returns:
            回测结果摘要列表
        """
        ...
