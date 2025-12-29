"""sma_crossover 策略共享配置

所有可复用的参数都在此定义一次，供 pyo3.py 和 btp.py 共享使用。
"""

from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """策略共享参数"""

    # ========== 数据配置 ==========
    timeframe: str = "15m"
    start_time: int = 1735689600000
    num_bars: int = 10000
    fixed_seed: int = 42
    allow_gaps: bool = True  # 测试：禁用跳空

    # ========== 指标参数 ==========
    sma_fast_period: int = 5
    sma_slow_period: int = 10

    # ========== 资金参数 ==========
    initial_capital: float = 10000.0
    fee_fixed: float = 0.5  # 禁用固定手续费
    fee_pct: float = 0.001

    # ========== 执行参数 ==========
    exit_in_bar: bool = False
    sl_trigger_mode: bool = False
    tp_trigger_mode: bool = False
    tsl_trigger_mode: bool = False
    sl_anchor_mode: bool = False
    tp_anchor_mode: bool = False
    tsl_anchor_mode: bool = False

    equity_cutoff_ratio: float = 0.10  # 10% equity cutoff for correlation test


# 默认配置实例
CONFIG = StrategyConfig()
