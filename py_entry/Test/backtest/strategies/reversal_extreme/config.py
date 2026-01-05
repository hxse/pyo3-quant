"""reversal_extreme 策略共享配置

所有可复用的参数都在此定义一次，供 pyo3.py 和 btp.py 共享使用。
"""

from dataclasses import dataclass
from py_entry.data_generator.time_utils import get_utc_timestamp_ms


@dataclass
class StrategyConfig:
    """策略共享参数"""

    # ========== 数据配置 ==========
    timeframe: str = "15m"
    start_time: int = get_utc_timestamp_ms("2025-01-01 00:00:00")
    num_bars: int = 10000
    fixed_seed: int = 42
    allow_gaps: bool = True

    # ========== 指标参数 ==========
    bbands_period: int = 20
    bbands_std: float = 2.5
    atr_period: int = 14

    # ========== 风控参数 ==========
    sl_pct: float = 0.02  # 2% 止损
    tp_atr: float = 3.0  # 4×ATR 止盈
    tsl_atr: float = 2.0  # 2.0×ATR 跟踪止损 (Relaxed for correlation stability)

    # ========== 引擎特性 (pyo3) ==========
    sl_exit_in_bar: bool = True  # SL 当根 K 线离场
    tp_exit_in_bar: bool = True  # TP 当根 K 线离场

    # 触发模式: True=high/low, False=close
    sl_trigger_mode: bool = True
    tp_trigger_mode: bool = True
    tsl_trigger_mode: bool = True

    # 锚点模式: True=high/low或extremum, False=close
    sl_anchor_mode: bool = False
    tp_anchor_mode: bool = False
    tsl_anchor_mode: bool = True

    tsl_atr_tight: bool = True  # TSL 更新模式

    # ========== 资金参数 ==========
    initial_capital: float = 10000.0
    fee_fixed: float = 0.0
    fee_pct: float = 0.001

    equity_cutoff_ratio: float = 0.10  # 20% equity cutoff for correlation test


# 默认配置实例
CONFIG = StrategyConfig()
