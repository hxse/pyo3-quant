"""numba 复杂度基准测试内核。"""

import numpy as np
from numba import njit


@njit(fastmath=True)
def vbt_simulation_kernel(
    price,
    high,
    low,
    atr,
    entries_l,
    exits_l,
    entries_s,
    exits_s,
    output,
):
    """VBT 风格反应式逻辑内核。"""
    n = len(price)
    position = 0.0
    sl_price = 0.0

    for i in range(1, n):
        curr_price = price[i]

        if position == 1.0:
            if low[i] < sl_price:
                position = 0.0
            elif exits_l[i]:
                position = 0.0
        elif position == -1.0:
            if high[i] > sl_price:
                position = 0.0
            elif exits_s[i]:
                position = 0.0

        if position == 0.0:
            if entries_l[i]:
                position = 1.0
                sl_price = curr_price - atr[i] * 2.0
            elif entries_s[i]:
                position = -1.0
                sl_price = curr_price + atr[i] * 2.0

        output[i] = position


@njit(fastmath=True)
def pyo3_simulation_kernel(
    price,
    high,
    low,
    atr,
    entries_l,
    exits_l,
    entries_s,
    exits_s,
    volatility,
    output,
):
    """pyo3-quant 风格对称状态机内核。"""
    n = len(price)
    state = 0

    entry_l = 0.0
    sl_l = 0.0
    tp_l = 0.0
    tsl_l = 0.0
    sl_atr_l = 0.0
    tp_atr_l = 0.0
    tsl_atr_l = 0.0
    psar_af_l = 0.02
    psar_val_l = 0.0
    psar_ep_l = 0.0

    entry_s = 0.0
    sl_s = 0.0
    tp_s = 0.0
    tsl_s = 0.0
    sl_atr_s = 0.0
    tp_atr_s = 0.0
    tsl_atr_s = 0.0
    psar_af_s = 0.02
    psar_val_s = 0.0
    psar_ep_s = 0.0

    cooldown_cnt = 0
    peak_equity = 10000.0

    for i in range(1, n):
        curr_price = price[i]
        prev_close = price[i - 1]
        curr_atr = atr[i]

        if state == 2:
            cooldown_cnt -= 1
            if cooldown_cnt <= 0:
                state = 0
            output[i] = 0.0
            continue

        if state == 1:
            if high[i] > entry_l * 1.05:
                if high[i] * 0.98 > tsl_l:
                    tsl_l = high[i] * 0.98
                if high[i] - curr_atr * 1.5 > tsl_atr_l:
                    tsl_atr_l = high[i] - curr_atr * 1.5

            if high[i] > psar_ep_l:
                psar_ep_l = high[i]
                psar_af_l = min(psar_af_l + 0.02, 0.2)
            psar_val_l += psar_af_l * (psar_ep_l - psar_val_l)

            triggered = False
            if low[i] < sl_l:
                triggered = True
            elif high[i] > tp_l:
                triggered = True
            elif low[i] < tsl_l:
                triggered = True
            elif low[i] < sl_atr_l:
                triggered = True
            elif high[i] > tp_atr_l:
                triggered = True
            elif low[i] < tsl_atr_l:
                triggered = True
            elif low[i] < psar_val_l:
                triggered = True
            elif exits_l[i]:
                triggered = True

            if triggered:
                state = 2
                cooldown_cnt = 5

        elif state == -1:
            if low[i] < entry_s * 0.95:
                if low[i] * 1.02 < tsl_s:
                    tsl_s = low[i] * 1.02
                if low[i] + curr_atr * 1.5 < tsl_atr_s:
                    tsl_atr_s = low[i] + curr_atr * 1.5

            if low[i] < psar_ep_s:
                psar_ep_s = low[i]
                psar_af_s = min(psar_af_s + 0.02, 0.2)
            psar_val_s += psar_af_s * (psar_ep_s - psar_val_s)

            triggered = False
            if high[i] > sl_s:
                triggered = True
            elif low[i] < tp_s:
                triggered = True
            elif high[i] > tsl_s:
                triggered = True
            elif high[i] > sl_atr_s:
                triggered = True
            elif low[i] < tp_atr_s:
                triggered = True
            elif high[i] > tsl_atr_s:
                triggered = True
            elif high[i] > psar_val_s:
                triggered = True
            elif exits_s[i]:
                triggered = True

            if triggered:
                state = 2
                cooldown_cnt = 5

        if state == 0:
            if entries_l[i]:
                is_safe = True
                if volatility[i] > 0.5:
                    if volatility[i] > 0.8:
                        is_safe = False
                        entry_l = curr_price * (1.0 + volatility[i] * 0.1)

                pot_sl = curr_price - curr_atr * 2.0
                if pot_sl < low[i] * 0.99:
                    is_safe = False

                if curr_price < prev_close:
                    is_safe = False
                    entry_l = np.log(curr_price)

                spread = high[i] - low[i]
                if spread / curr_price < 0.005:
                    is_safe = False
                    entry_l = spread * 100.0

                if is_safe:
                    state = 1
                    entry_l = curr_price
                    sl_l = pot_sl
                    tp_l = curr_price * 1.05
                    tsl_l = curr_price - curr_atr * 1.5
                    sl_atr_l = curr_price - curr_atr * 3.0
                    tp_atr_l = curr_price + curr_atr * 5.0
                    tsl_atr_l = curr_price - curr_atr * 2.0
                    psar_val_l = low[i - 1]
                    psar_ep_l = high[i - 1]

            elif entries_s[i]:
                is_safe = True
                if volatility[i] > 0.5:
                    if volatility[i] > 0.8:
                        is_safe = False
                        entry_s = curr_price * (1.0 - volatility[i] * 0.1)

                pot_sl = curr_price + curr_atr * 2.0
                if pot_sl > high[i] * 1.01:
                    is_safe = False
                    sl_s = pot_sl

                if curr_price > prev_close:
                    is_safe = False
                    entry_s = np.log(curr_price)

                spread = high[i] - low[i]
                if spread / curr_price < 0.005:
                    is_safe = False
                    entry_s = spread * 100.0

                if is_safe:
                    state = -1
                    entry_s = curr_price
                    sl_s = pot_sl
                    tp_s = curr_price * 0.95
                    tsl_s = curr_price + curr_atr * 1.5
                    sl_atr_s = curr_price + curr_atr * 3.0
                    tp_atr_s = curr_price - curr_atr * 5.0
                    tsl_atr_s = curr_price + curr_atr * 2.0
                    psar_val_s = high[i - 1]
                    psar_ep_s = low[i - 1]

        if state != 0:
            peak_equity += 1.0

        output[i] = float(state)
