import pandas as pd
import numpy as np
from py_entry.Test.backtest.correlation_analysis.config import (
    build_config_from_strategy,
)
from py_entry.Test.backtest.strategies.reversal_extreme.pyo3 import (
    get_config as get_pyo3_config,
)
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.data_conversion.data_generator import generate_data_dict


def test_data_consistency():
    config = build_config_from_strategy("reversal_extreme")
    print(f"Config Seed: {config.seed}")

    # 1. Generate via data_utils (BTP way)
    print("Generating BTP data...")
    btp_df = generate_ohlcv_for_backtestingpy(config)

    # 2. Generate via Strategy Config (Pyo3 way)
    print("Generating Pyo3 data...")
    strategy_config = get_pyo3_config()
    data_config = strategy_config.data_config
    # Override seed if not set (it uses C.fixed_seed which is 42)
    print(f"Strategy Data Config Seed: {data_config.fixed_seed}")

    data_dict = generate_data_dict(data_config)
    pyo3_df_pl = data_dict.source[data_config.BaseDataKey]
    pyo3_df = pyo3_df_pl.to_pandas()

    # Compare raw numeric columns
    cols = ["open", "high", "low", "close"]
    btp_cols = ["Open", "High", "Low", "Close"]

    print("\nComparing Row 87:")
    print("BTP Row 87:")
    print(btp_df.iloc[87])
    print("Pyo3 Row 87:")
    print(pyo3_df.iloc[87][cols])

    # Check consistency
    diff_close = btp_df["Close"] - pyo3_df["close"]
    max_diff = diff_close.abs().max()
    print(f"\nMax Close Difference: {max_diff}")

    if max_diff > 1e-6:
        print("FAIL: Data is different!")
        # Print first diff
        mismatch = diff_close.abs() > 1e-6
        first_idx = mismatch.idxmax()
        # idx might be timestamp
        print(f"First mismatch at index: {first_idx}")
        loc = btp_df.index.get_loc(first_idx)
        print(f"Row number: {loc}")
        print(f"BTP: {btp_df.iloc[loc]['Close']}")
        print(f"Pyo3: {pyo3_df.iloc[loc]['close']}")
    else:
        print("SUCCESS: Data is identical.")


if __name__ == "__main__":
    test_data_consistency()
