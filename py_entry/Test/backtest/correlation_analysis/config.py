from dataclasses import dataclass
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.data_generator import (
    DataGenerationParams,
    OhlcvDataFetchConfig,
    DirectDataConfig,
)


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
    from py_entry.strategies import get_strategy

    strategy = get_strategy(strategy_name)
    data_cfg = strategy.data_config
    backtest_cfg = strategy.backtest_params

    # 统一三类数据源默认值提取，避免直接假设 data_cfg 一定是模拟数据。
    default_start_time = get_utc_timestamp_ms("2025-01-01 00:00:00")
    bars = 6000
    seed = 42
    timeframe = "15m"
    start_time = default_start_time
    allow_gaps = False

    if isinstance(data_cfg, DataGenerationParams):
        bars = data_cfg.num_bars or bars
        seed = data_cfg.fixed_seed if data_cfg.fixed_seed is not None else seed
        timeframe = data_cfg.timeframes[0] if data_cfg.timeframes else timeframe
        start_time = data_cfg.start_time or start_time
        allow_gaps = data_cfg.allow_gaps
    elif isinstance(data_cfg, OhlcvDataFetchConfig):
        bars = data_cfg.limit or bars
        timeframe = data_cfg.timeframes[0] if data_cfg.timeframes else timeframe
        start_time = data_cfg.since or start_time
    elif isinstance(data_cfg, DirectDataConfig):
        # DirectDataConfig 没有 timeframes/since，尽量从 base_data_key 反推周期。
        if "_" in data_cfg.base_data_key:
            timeframe = data_cfg.base_data_key.split("_", 1)[1]

    config = CommonConfig(
        bars=overrides.get("bars", bars),
        seed=overrides.get("seed", seed),
        initial_capital=overrides.get(
            "initial_capital", backtest_cfg.initial_capital or 10000.0
        ),
        commission=overrides.get("commission", backtest_cfg.fee_pct or 0.0005),
        timeframe=overrides.get("timeframe", timeframe),
        start_time=overrides.get("start_time", start_time),
        allow_gaps=overrides.get("allow_gaps", allow_gaps),
        equity_cutoff_ratio=overrides.get("equity_cutoff_ratio", 0.20),
    )

    return config
