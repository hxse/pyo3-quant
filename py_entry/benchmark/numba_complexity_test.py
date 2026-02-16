import timeit

from py_entry.benchmark._numba_complexity_data import (
    N_BARS,
    atr,
    entries_long,
    entries_short,
    exits_long,
    exits_short,
    high,
    low,
    out_pos,
    price,
    volatility,
)
from py_entry.benchmark._numba_complexity_kernels import (
    pyo3_simulation_kernel,
    vbt_simulation_kernel,
)


def run_test():
    """运行 numba 复杂度对比测试。"""
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
