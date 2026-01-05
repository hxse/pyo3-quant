from dataclasses import dataclass
from typing import TYPE_CHECKING
from py_entry.data_generator.time_utils import get_utc_timestamp_ms

if TYPE_CHECKING:
    from py_entry.Test.backtest.strategies import StrategyConfig


@dataclass
class CommonConfig:
    """
    相关性分析运行时配置容器

    注意: 所有参数必须显式传入，不设默认值，
    以避免与策略配置产生不一致。
    """

    bars: int
    seed: int
    initial_capital: float
    commission: float
    timeframe: str
    start_time: int
    allow_gaps: bool
    equity_cutoff_ratio: float


def build_config_from_strategy(strategy_name: str, **overrides) -> CommonConfig:
    """
    从策略配置构建 CommonConfig

    Args:
        strategy_name: 策略名称 (如 "reversal_extreme")
        **overrides: 覆盖参数 (如 bars=200, seed=123)

    Returns:
        CommonConfig 实例
    """
    from py_entry.Test.backtest.strategies import get_strategy

    strategy = get_strategy(strategy_name)
    data_cfg = strategy.data_config
    backtest_cfg = strategy.backtest_params

    config = CommonConfig(
        bars=overrides.get("bars", data_cfg.num_bars or 6000),
        seed=overrides.get(
            "seed", data_cfg.fixed_seed if data_cfg.fixed_seed is not None else 42
        ),
        initial_capital=overrides.get(
            "initial_capital", backtest_cfg.initial_capital or 10000.0
        ),
        commission=overrides.get("commission", backtest_cfg.fee_pct or 0.0005),
        timeframe=overrides.get(
            "timeframe", data_cfg.timeframes[0] if data_cfg.timeframes else "15m"
        ),
        start_time=overrides.get(
            "start_time",
            data_cfg.start_time or get_utc_timestamp_ms("2025-01-01 00:00:00"),
        ),
        allow_gaps=overrides.get("allow_gaps", getattr(data_cfg, "allow_gaps", False)),
        equity_cutoff_ratio=overrides.get("equity_cutoff_ratio", 0.20),
    )

    return config
