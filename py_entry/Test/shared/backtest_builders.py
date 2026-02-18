"""
测试共享构造器

目标：
1. 统一测试中的数据配置与回测配置默认值；
2. 允许各模块按需覆盖，避免复制粘贴大段配置。
"""

from typing import Any, Dict, Optional

from py_entry.data_generator import DataSourceConfig
from py_entry.runner import Backtest
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    Param,
    ParamType,
    SignalGroup,
    SignalTemplate,
    SettingContainer,
)


def make_backtest_params(**overrides: Any) -> BacktestParams:
    """创建统一的回测参数默认值；允许测试按需覆盖。"""
    # 默认值严格对齐当前文档约定：所有执行开关默认 False。
    params: Dict[str, Any] = {
        "initial_capital": 10000.0,
        "fee_fixed": 0,
        "fee_pct": 0.001,
        "sl_exit_in_bar": False,
        "tp_exit_in_bar": False,
        "sl_trigger_mode": False,
        "tp_trigger_mode": False,
        "tsl_trigger_mode": False,
        "sl_anchor_mode": False,
        "tp_anchor_mode": False,
        "tsl_anchor_mode": False,
    }
    params.update(overrides)
    return BacktestParams(**params)


def make_engine_settings(
    *,
    execution_stage: ExecutionStage = ExecutionStage.Performance,
    return_only_final: bool = False,
) -> SettingContainer:
    """创建统一引擎设置。"""
    return SettingContainer(
        execution_stage=execution_stage,
        return_only_final=return_only_final,
    )


def make_ma_cross_template(
    *,
    fast_name: str = "sma_fast",
    slow_name: str = "sma_slow",
    source_key: str = "ohlcv_15m",
    offset: int = 0,
) -> SignalTemplate:
    """创建常用均线交叉模板（四向完整模板）。"""
    gt_expr = (
        f"{fast_name}, {source_key}, {offset} > {slow_name}, {source_key}, {offset}"
    )
    lt_expr = (
        f"{fast_name}, {source_key}, {offset} < {slow_name}, {source_key}, {offset}"
    )
    return SignalTemplate(
        entry_long=SignalGroup(logic=LogicOp.AND, comparisons=[gt_expr]),
        entry_short=SignalGroup(logic=LogicOp.AND, comparisons=[lt_expr]),
        exit_long=SignalGroup(logic=LogicOp.AND, comparisons=[lt_expr]),
        exit_short=SignalGroup(logic=LogicOp.AND, comparisons=[gt_expr]),
    )


def make_backtest_runner(
    *,
    data_source: DataSourceConfig,
    indicators: Dict[str, Dict[str, Dict[str, Any]]],
    signal: Optional[Dict[str, Any]] = None,
    backtest: Optional[BacktestParams] = None,
    signal_template: Optional[SignalTemplate] = None,
    engine_settings: Optional[SettingContainer] = None,
    **kwargs: Any,
) -> Backtest:
    """创建统一 Backtest 实例，避免每个模块重复组装构造参数。"""
    return Backtest(
        data_source=data_source,
        indicators=indicators,
        signal=signal or {},
        backtest=backtest,
        signal_template=signal_template,
        engine_settings=engine_settings,
        **kwargs,
    )


def make_optimizer_sma_atr_components(
    *,
    source_key: str = "ohlcv_15m",
) -> tuple[Dict[str, Dict[str, Dict[str, Any]]], SignalTemplate, BacktestParams]:
    """
    创建优化器基准测试常用组件（指标 + 模板 + 回测参数）。

    该场景被 optimizer_benchmark 多处复用，统一后可避免参数漂移。
    """
    indicators = {
        source_key: {
            "sma_fast": {
                "period": Param(
                    20, min=10, max=40, optimize=True, dtype=ParamType.Integer
                )
            },
            "sma_slow": {
                "period": Param(
                    60, min=40, max=100, optimize=True, dtype=ParamType.Integer
                )
            },
        }
    }
    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[f"sma_fast,{source_key},0 x> sma_slow,{source_key},0"],
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,
            comparisons=[f"sma_fast,{source_key},0 x< sma_slow,{source_key},0"],
        ),
    )
    backtest_params = make_backtest_params(
        sl_atr=Param(2.0, min=1.5, max=4.0, step=0.25, optimize=True),
        tsl_atr=Param(3.0, min=2.0, max=6.0, step=0.25, optimize=True),
        atr_period=Param(14, min=10, max=30, optimize=True, dtype=ParamType.Integer),
        initial_capital=10000.0,
        fee_pct=0.0005,
        fee_fixed=0.0,
    )
    return indicators, signal_template, backtest_params
