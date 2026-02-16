"""numba 复杂度基准测试的数据准备。"""

import numpy as np

# 统一样本规模，保证不同实现对比公平。
N_BARS = 1_000_000

# 使用随机游走生成价格序列，近似真实市场噪声。
returns = np.random.normal(0, 0.01, N_BARS)
price = 100 * np.cumprod(1 + returns)
high = price * (1 + np.abs(np.random.normal(0, 0.005, N_BARS)))
low = price * (1 - np.abs(np.random.normal(0, 0.005, N_BARS)))
atr = price * 0.02

# 多空信号独立生成，避免单边偏置。
entries_long = np.random.rand(N_BARS) > 0.90
exits_long = np.random.rand(N_BARS) > 0.90
entries_short = np.random.rand(N_BARS) > 0.90
exits_short = np.random.rand(N_BARS) > 0.90

# 额外风险输入。
volatility = np.random.rand(N_BARS)
out_pos = np.zeros(N_BARS, dtype=np.float64)
