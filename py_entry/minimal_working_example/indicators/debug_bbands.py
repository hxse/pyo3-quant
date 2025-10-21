import sys
from pathlib import Path

root_path = next(
    (p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file()),
    None,
)
if root_path:
    sys.path.insert(0, str(root_path))

import pandas as pd
import pandas_ta as ta
from py_entry.data_conversion.helpers.data_generator import generate_ohlcv
from py_entry.Test.utils.comparison_tool import (
    assert_indicator_same,
    assert_indicator_different,
)

import pyo3_quant


def run_debug_bbands():
    timeframes = ["15m"]

    ohlcv_df = generate_ohlcv(
        timeframe="15m", start_time=1735689600000, num_bars=100
    )  # generate_ohlcv 返回 polars DataFrame

    length = 20
    std = 2.0

    for idx, tf in enumerate(timeframes):
        print(f"\n--- Timeframe: {tf} ---")

        # 调用 Rust 实现
        result_rust_pydf = pyo3_quant.debug_bbands(ohlcv_df, length=length, std=std)
        result_rust = result_rust_pydf.to_pandas()

        # 调用 pandas-ta 实现
        result_pandas = ta.bbands(
            ohlcv_df["close"].to_pandas(), length=length, std=std, talib=False, ddof=0
        )

        # 重命名 pandas-ta 的列以匹配 Rust 的输出
        result_pandas = result_pandas.rename(
            columns={
                f"BBL_{length}_{std}": "lower",
                f"BBM_{length}_{std}": "middle",
                f"BBU_{length}_{std}": "upper",
                f"BBB_{length}_{std}": "bandwidth",
                f"BBP_{length}_{std}": "percent",
            }
        )

        # 对比 "lower", "middle", "upper", "bandwidth" 四个指标
        indicators_to_compare = ["lower", "middle", "upper", "bandwidth"]

        print("\nRust (前10行):")
        print(result_rust[indicators_to_compare].head(10))
        print("\npandas-ta (前10行):")
        print(result_pandas[indicators_to_compare].head(10))

        print("\nRust (后10行):")
        print(result_rust[indicators_to_compare].tail(10))
        print("\npandas-ta (后10行):")
        print(result_pandas[indicators_to_compare].tail(10))

        print("\n--- 差异统计 ---")
        for indicator in indicators_to_compare:
            diff = (result_rust[indicator] - result_pandas[indicator]).abs().dropna()
            if not diff.empty:
                max_diff = diff.max()
                mean_diff = diff.mean()
                rmse = (diff**2).mean() ** 0.5
                print(f"指标: {indicator}")
                print(f"  最大差异: {max_diff}")
                print(f"  平均差异: {mean_diff}")
                print(f"  RMSE: {rmse}")
            else:
                print(f"指标: {indicator} - 无差异或数据为空")

        # 测试不同ddof值的影响
        result_pandas_ddof0 = ta.bbands(
            ohlcv_df["close"].to_pandas(), length=length, std=std, talib=False, ddof=0
        )
        result_pandas_ddof1 = ta.bbands(
            ohlcv_df["close"].to_pandas(), length=length, std=std, talib=False, ddof=1
        )

        print("\n--- ddof差异验证 ---")
        print("pandas-ta (ddof=0) lower 后5行:")
        print(result_pandas_ddof0[[f"BBL_{length}_{std}"]].tail())
        print("\npandas-ta (ddof=1) lower 后5行:")
        print(result_pandas_ddof1[[f"BBL_{length}_{std}"]].tail())
        print("\nRust lower 后5行:")
        print(result_rust["lower"].tail())

        print("\n--- ddof=0 一致性验证 ---")
        assert_indicator_same(
            result_pandas_ddof0["BBL_20_2.0"].to_numpy(),
            result_rust["lower"].to_numpy(),
            "lower",
            "pandas-ta (ddof=0) vs Rust",
        )
        assert_indicator_same(
            result_pandas_ddof0["BBU_20_2.0"].to_numpy(),
            result_rust["upper"].to_numpy(),
            "upper",
            "pandas-ta (ddof=0) vs Rust",
        )
        assert_indicator_same(
            result_pandas_ddof0["BBB_20_2.0"].to_numpy(),
            result_rust["bandwidth"].to_numpy(),
            "bandwidth",
            "pandas-ta (ddof=0) vs Rust",
        )

        # print("\n--- ddof=1 一致性验证 ---")
        # assert_indicator_same(
        #     result_pandas_ddof1["BBL_20_2.0"].to_numpy(),
        #     result_rust["lower"].to_numpy(),
        #     "lower",
        #     "pandas-ta (ddof=1) vs Rust",
        # )
        # assert_indicator_same(
        #     result_pandas_ddof1["BBU_20_2.0"].to_numpy(),
        #     result_rust["upper"].to_numpy(),
        #     "upper",
        #     "pandas-ta (ddof=1) vs Rust",
        # )
        # assert_indicator_same(
        #     result_pandas_ddof1["BBB_20_2.0"].to_numpy(),
        #     result_rust["bandwidth"].to_numpy(),
        #     "bandwidth",
        #     "pandas-ta (ddof=1) vs Rust",
        # )


if __name__ == "__main__":
    run_debug_bbands()
