import numpy as np
import timeit
from numba import njit, float64

N_BARS = 1_000_000

# Data Setup
# Use Random Walk for Price (Realistic)
# Random Walk for Price
returns = np.random.normal(0, 0.01, N_BARS)
price = 100 * np.cumprod(1 + returns)
high = price * (1 + np.abs(np.random.normal(0, 0.005, N_BARS)))
low = price * (1 - np.abs(np.random.normal(0, 0.005, N_BARS)))
atr = price * 0.02

# Signals (Long & Short)
entries_long = np.random.rand(N_BARS) > 0.90
exits_long = np.random.rand(N_BARS) > 0.90
entries_short = np.random.rand(N_BARS) > 0.90
exits_short = np.random.rand(N_BARS) > 0.90

# Volatility
volatility = np.random.rand(N_BARS)
out_pos = np.zeros(N_BARS, dtype=np.float64)


@njit(fastmath=True)
def vbt_simulation_kernel(
    price, high, low, atr, entries_l, exits_l, entries_s, exits_s, output
):
    """
    Case 1: VBT Style Logic (Reactive) - Bi-directional
    """
    n = len(price)
    position = 0.0
    sl_price = 0.0

    for i in range(1, n):
        curr_price = price[i]

        # 1. Exit Logic
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

        # 2. Entry Logic
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
    price, high, low, atr, entries_l, exits_l, entries_s, exits_s, volatility, output
):
    """
    Case 2: pyo3-quant Style (Full Symmetric Architecture)
    Doubled state variables, doubled logic blocks.
    """
    n = len(price)
    state = 0  # 0=Empty, 1=Long, -1=Short, 2=Cooldown

    # State Vars (Long)
    entry_l = 0.0
    sl_l = 0.0
    tp_l = 0.0
    tsl_l = 0.0
    sl_atr_l = 0.0
    tp_atr_l = 0.0
    tsl_atr_l = 0.0
    anchor_h_l = 0.0
    psar_af_l = 0.02
    psar_val_l = 0.0
    psar_ep_l = 0.0

    # State Vars (Short)
    entry_s = 0.0
    sl_s = 0.0
    tp_s = 0.0
    tsl_s = 0.0
    sl_atr_s = 0.0
    tp_atr_s = 0.0
    tsl_atr_s = 0.0
    anchor_l_s = 0.0
    psar_af_s = 0.02
    psar_val_s = 0.0
    psar_ep_s = 0.0

    cooldown_cnt = 0
    peak_equity = 10000.0

    for i in range(1, n):
        curr_price = price[i]
        prev_close = price[i - 1]
        curr_atr = atr[i]

        # --- Phase 1: Cooldown ---
        if state == 2:
            cooldown_cnt -= 1
            if cooldown_cnt <= 0:
                state = 0
            output[i] = 0.0
            continue

        # --- Phase 2: Exit Logic (Symmetric 7-Layer Check) ---
        if state == 1:  # Long Exit
            # TSL Prior Updates (PCT/ATR/PSAR)
            if high[i] > entry_l * 1.05:
                if high[i] * 0.98 > tsl_l:
                    tsl_l = high[i] * 0.98  # TSL PCT
                if high[i] - curr_atr * 1.5 > tsl_atr_l:
                    tsl_atr_l = high[i] - curr_atr * 1.5  # TSL ATR

            # Recursive PSAR Update
            if high[i] > psar_ep_l:
                psar_ep_l = high[i]
                psar_af_l = min(psar_af_l + 0.02, 0.2)
            psar_val_l += psar_af_l * (psar_ep_l - psar_val_l)

            # Check ALL 7 Risk Conditions (Priority: SL -> TP -> TSL)
            triggered = False
            # 1. SL PCT
            if low[i] < sl_l:
                triggered = True
            # 2. TP PCT
            elif high[i] > tp_l:
                triggered = True
            # 3. TSL PCT
            elif low[i] < tsl_l:
                triggered = True
            # 4. SL ATR
            elif low[i] < sl_atr_l:
                triggered = True
            # 5. TP ATR
            elif high[i] > tp_atr_l:
                triggered = True
            # 6. TSL ATR
            elif low[i] < tsl_atr_l:
                triggered = True
            # 7. PSAR
            elif low[i] < psar_val_l:
                triggered = True
            # 8. Signal
            elif exits_l[i]:
                triggered = True

            if triggered:
                state = 2
                cooldown_cnt = 5

        elif state == -1:  # Short Exit
            # TSL Prior Updates
            if low[i] < entry_s * 0.95:
                if low[i] * 1.02 < tsl_s:
                    tsl_s = low[i] * 1.02
                if low[i] + curr_atr * 1.5 < tsl_atr_s:
                    tsl_atr_s = low[i] + curr_atr * 1.5

            # Recursive PSAR Update
            if low[i] < psar_ep_s:
                psar_ep_s = low[i]
                psar_af_s = min(psar_af_s + 0.02, 0.2)
            psar_val_s += psar_af_s * (psar_ep_s - psar_val_s)

            # Check ALL 7 Risk Conditions
            triggered = False
            # 1. SL PCT
            if high[i] > sl_s:
                triggered = True
            # 2. TP PCT
            elif low[i] < tp_s:
                triggered = True
            # 3. TSL PCT
            elif high[i] > tsl_s:
                triggered = True
            # 4. SL ATR
            elif high[i] > sl_atr_s:
                triggered = True
            # 5. TP ATR
            elif low[i] < tp_atr_s:
                triggered = True
            # 6. TSL ATR
            elif high[i] > tsl_atr_s:
                triggered = True
            # 7. PSAR
            elif high[i] > psar_val_s:
                triggered = True
            # 8. Signal
            elif exits_s[i]:
                triggered = True

            if triggered:
                state = 2
                cooldown_cnt = 5

        # --- Phase 3: Entry Logic (Symmetric 7-Layer) ---
        if state == 0:
            # === Long Entry Check ===
            if entries_l[i]:
                is_safe = True
                # L1: Volatility
                if volatility[i] > 0.5:
                    if volatility[i] > 0.8:
                        is_safe = False
                        entry_l = curr_price * (1.0 + volatility[i] * 0.1)
                # L2: SL Logic
                pot_sl = curr_price - curr_atr * 2.0
                if pot_sl < low[i] * 0.99:
                    is_safe = False
                # L3: Trend
                if curr_price < prev_close:
                    is_safe = False
                    entry_l = np.log(curr_price)
                # L4: Spread
                spread = high[i] - low[i]
                if spread / curr_price < 0.005:
                    is_safe = False
                    entry_l = spread * 100.0

                if is_safe:
                    state = 1
                    entry_l = curr_price
                    # Init ALL 7 Risk Prices
                    sl_l = pot_sl
                    tp_l = curr_price * 1.05
                    tsl_l = curr_price - curr_atr * 1.5
                    sl_atr_l = curr_price - curr_atr * 3.0
                    tp_atr_l = curr_price + curr_atr * 5.0
                    tsl_atr_l = curr_price - curr_atr * 2.0
                    # Init Long PSAR
                    psar_val_l = low[i - 1]
                    psar_ep_l = high[i - 1]

            # === Short Entry Check (Additional Logic Block) ===
            elif entries_s[i]:
                is_safe = True
                # L1: Volatility
                if volatility[i] > 0.5:
                    if volatility[i] > 0.8:
                        is_safe = False
                        entry_s = curr_price * (1.0 - volatility[i] * 0.1)
                # L2: SL Logic
                pot_sl = curr_price + curr_atr * 2.0
                if pot_sl > high[i] * 1.01:
                    is_safe = False
                    sl_s = pot_sl
                # L3: Trend
                if curr_price > prev_close:
                    is_safe = False
                    entry_s = np.log(curr_price)
                # L4: Spread
                spread = high[i] - low[i]
                if spread / curr_price < 0.005:
                    is_safe = False
                    entry_s = spread * 100.0

                if is_safe:
                    state = -1
                    entry_s = curr_price
                    # Init ALL 7 Risk Prices
                    sl_s = pot_sl
                    tp_s = curr_price * 0.95
                    tsl_s = curr_price + curr_atr * 1.5
                    sl_atr_s = curr_price + curr_atr * 3.0
                    tp_atr_s = curr_price - curr_atr * 5.0
                    tsl_atr_s = curr_price + curr_atr * 2.0
                    # Init Short PSAR
                    psar_val_s = high[i - 1]
                    psar_ep_s = low[i - 1]

        # --- Phase 4: Capital (Unrealized PnL is simpler, assume Logic cost dominates) ---
        if state != 0:
            # Just a dummy op to keep variables alive
            peak_equity += 1.0

        output[i] = float(state)


def run_test():
    print("Warming up JIT...")
    vbt_simulation_kernel(
        price,
        high,
        low,
        atr,
        entries_long,
        exits_long,
        entries_short,
        exits_short,
        out_pos,
    )
    pyo3_simulation_kernel(
        price,
        high,
        low,
        atr,
        entries_long,
        exits_long,
        entries_short,
        exits_short,
        volatility,
        out_pos,
    )

    print(f"Running Fidelity Comparison with {N_BARS:,} bars...")

    # Measure VBT (Baseline)
    t_vbt = timeit.timeit(
        lambda: vbt_simulation_kernel(
            price,
            high,
            low,
            atr,
            entries_long,
            exits_long,
            entries_short,
            exits_short,
            out_pos,
        ),
        number=100,
    )
    print(f"VBT-Style (Reactive):   {t_vbt:.4f}s")

    # Measure pyo3 (Pre-emptive)
    t_pyo3 = timeit.timeit(
        lambda: pyo3_simulation_kernel(
            price,
            high,
            low,
            atr,
            entries_long,
            exits_long,
            entries_short,
            exits_short,
            volatility,
            out_pos,
        ),
        number=100,
    )
    print(f"pyo3-Style (Pre-emptive): {t_pyo3:.4f}s")

    ratio = t_pyo3 / t_vbt
    print(f"\nComplexity Cost: {ratio:.2f}x Slower")


if __name__ == "__main__":
    run_test()
