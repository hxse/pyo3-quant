"""Type stubs for pyo3_quant module."""

from typing import Any, Dict, List, Optional, Union

# 导入项目中已有的类型定义
from py_entry.data_conversion.types import (
    Param,
    ParamOperand,
    SignalDataOperand,
    # SingleParamSet,  # 已注释，因为未使用
    ParamContainer,
    SettingContainer,
    TemplateContainer,
    DataContainer,
    BacktestSummary,
)

# 类型别名
IndicatorsParams = Dict[str, Dict[str, Dict[str, Param]]]
SignalParams = Dict[str, Param]
SignalRightOperand = Union[SignalDataOperand, ParamOperand]

# ===== 模块定义 =====

class minimal_working_example:
    @staticmethod
    def sum_as_string(a: int, b: int) -> str:
        """将两个整数相加并返回结果的字符串表示"""
        ...

    @staticmethod
    def test_custom_from_py_object(data_dict: Any) -> str:
        """测试自定义FromPyObject转换
        Args:
            data_dict: 测试数据字典
        Returns:
            转换结果字符串
        """
        ...

class backtest_engine:
    @staticmethod
    def run_backtest_engine(
        data_dict: DataContainer,
        param_set: ParamContainer,
        template_config: TemplateContainer,
        engine_settings: SettingContainer,
        debug_config: Optional[BacktestSummary] = None,
    ) -> List[Dict[str, Any]]:
        """运行回测引擎

        Args:
            data_dict: 市场数据容器
            param_set: 回测参数集合
            template_config: 信号模板配置
            engine_settings: 引擎设置
            debug_config: 可选的已有回测结果，用于增量计算

        Returns:
            回测结果摘要字典列表
        """
        ...
