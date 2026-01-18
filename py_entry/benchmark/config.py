NUM_BARS_LIST = [10000]  #  K 线数量
OPT_SAMPLES_LIST = [2000]  # 采样数量
NUM_RUNS = 3
WARMUP_RUNS = 1

# 策略 A 参数范围: SMA + TSL (极端扩大)
STRATEGY_A_PARAMS = {
    "sma_fast": (2, 5000),
    "sma_slow": (5000, 10000),
    "tsl_pct": (0.001, 0.20),
}

# 策略 B 参数范围: EMA + RSI + TSL (极端扩大)
STRATEGY_B_PARAMS = {
    "ema_fast": (2, 5000),
    "ema_slow": (5000, 10000),
    "rsi_period": (2, 4000),  # 扩大范围以确保 VBT 无法有效缓存
    "tsl_pct": (0.001, 0.20),
}

# 策略 C 参数范围: 无指标对比测试
# pyo3: 价格比较 (close > prev_close)，无指标计算
# vectorbt: EMA + RSI，有指标计算
STRATEGY_C_PARAMS = {
    "ema_fast": (2, 5000),
    "ema_slow": (5000, 10000),
    "rsi_period": (2, 4000),
    "tsl_pct": (0.001, 0.20),
}
