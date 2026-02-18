"""
策略配置基类

定义策略配置的数据结构，所有策略都需要返回 StrategyConfig 实例。
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Type

from py_entry.data_generator import DataSourceConfig
from py_entry.types import (
    BacktestParams,
    SignalTemplate,
    SettingContainer,
    PerformanceParams,
)

from backtesting import Strategy

# 类型别名
IndicatorsParams = Dict[str, Dict[str, Dict[str, Any]]]
SignalParams = Dict[str, Any]


@dataclass
class StrategyConfig:
    """
    策略配置数据类

    Attributes:
        name: 策略唯一标识符（用于测试报告）
        description: 描述
        data_config: 数据源配置（支持模拟/拉取/直喂）
        indicators_params: 指标参数
        signal_params: 信号参数
        backtest_params: 回测参数
        signal_template: 信号模板（进出场规则）
        engine_settings: 引擎设置
        performance_params: 性能指标参数（可选）
        btp_strategy_class: backtesting.py 策略类（可选，用于相关性分析）
    """

    name: str
    description: str
    data_config: DataSourceConfig
    indicators_params: IndicatorsParams
    signal_params: SignalParams
    backtest_params: BacktestParams
    signal_template: SignalTemplate
    engine_settings: SettingContainer
    performance_params: Optional[PerformanceParams] = None
    btp_strategy_class: Optional[Type[Strategy]] = None
    custom_params: Optional[Dict[str, Any]] = None

    def __repr__(self) -> str:
        return f"StrategyConfig(name='{self.name}')"
