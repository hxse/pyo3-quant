import pandas_ta as ta

from py_entry.data_generator import (
    generate_data_dict,
    DataGenerationParams,
)
from py_entry.Test.utils.comparison_tool import assert_indicator_same


def main():
    """
    比较 pandas-ta 在开启和不开启 talib 选项时 RMA 指标的计算结果。
    """
    simulated_data_config = DataGenerationParams(
        timeframes=["15m"],
        start_time=1609459200000,
        num_bars=3000,
        fixed_seed=42,
        base_data_key="ohlcv_15m",
    )
    data_dict = generate_data_dict(data_source=simulated_data_config)

    ohlcv_data_pl = data_dict.source["ohlcv"][0]

    ohlcv_data_pd = ohlcv_data_pl.to_pandas()

    indicator_name = "adx"
    length = 14

    result_pd = getattr(ta, indicator_name)(
        ohlcv_data_pd["high"],
        ohlcv_data_pd["low"],
        ohlcv_data_pd["close"],
        length=length,
        talib=False,
    )
    result_pd = [result_pd[column_name] for column_name in result_pd.columns]

    result_talib = getattr(ta, indicator_name)(
        ohlcv_data_pd["high"],
        ohlcv_data_pd["low"],
        ohlcv_data_pd["close"],
        length=length,
        talib=True,
    )
    result_talib = [result_talib[column_name] for column_name in result_talib.columns]

    for p, t in zip(result_pd, result_talib):
        # 3. 比较结果
        assert_indicator_same(
            array1=p.values,
            array2=t.values,
            indicator_name=indicator_name,
            indicator_info=f"{indicator_name} {length}",
        )


if __name__ == "__main__":
    main()
