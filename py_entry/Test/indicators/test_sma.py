import sys
from pathlib import Path

root_path = next(
    (p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file()),
    None,
)
if root_path:
    sys.path.insert(0, str(root_path))


from Test.utils.over_constants import numba_config


from Test.indicators.indicators_template import (
    compare_indicator_accuracy,
    compare_pandas_ta_with_talib,
)


from Test.utils.conftest import np_data_mock, df_data_mock


np_float = numba_config["np"]["float"]


name = "sma"
params_config_list = [{"nb_params": {"period": 14}, "pd_params": {"length": 14}}]
input_data_keys = ["close"]

nb_pd_talib_key_maps = None
pd_talib_key_maps = None
assert_func_kwargs = {}


def test_accuracy(
    np_data_mock,
    df_data_mock,
    talib=False,
    assert_mode=True,
):
    compare_indicator_accuracy(
        name=name,
        params_config_list=params_config_list,
        tohlcv_np=np_data_mock,
        df_data_mock=df_data_mock,
        input_data_keys=input_data_keys,
        talib=talib,
        assert_mode=assert_mode,
        output_key_maps=nb_pd_talib_key_maps,
        assert_func_kwargs=assert_func_kwargs,
    )


def test_accuracy_talib(np_data_mock, df_data_mock, talib=True, assert_mode=True):
    test_accuracy(np_data_mock, df_data_mock, talib=talib, assert_mode=assert_mode)


def test_pandas_ta_and_talib(df_data_mock, assert_mode=True):
    compare_pandas_ta_with_talib(
        name=name,
        params_config_list=params_config_list,
        df_data_mock=df_data_mock,
        input_data_keys=input_data_keys,
        assert_mode=assert_mode,
        assert_func_kwargs=assert_func_kwargs,
        output_key_maps=pd_talib_key_maps,
    )
