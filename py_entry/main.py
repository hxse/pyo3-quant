import polars as pl
import pyo3_quant
import time

from py_entry.data_conversion.input import (
    EngineSettings,
    TemplateConfig,
)
from py_entry.data_conversion.helpers import (
    generate_data_dict,
    create_signal_template_instance,
    create_risk_template_instance,
    create_param_set,
)


if __name__ == "__main__":
    print("-" * 30)
    start_time = time.perf_counter()
    res = pyo3_quant.sum_as_string(5, 25)
    print("sum_as_string:", res)
    print("耗时", time.perf_counter() - start_time)

    print("-" * 30)
    start_time = time.perf_counter()
    data_dict = generate_data_dict(
        timeframes=["15m", "1h"], start_time=1735689600000, num_bars=200, brick_size=2.0
    )

    param_set = create_param_set(10,len(data_dict.ohlcv))

    processed_settings = EngineSettings(is_only_performance=False)

    template_config = TemplateConfig(
        signal=create_signal_template_instance(), risk=create_risk_template_instance()
    )
    print("配置生成:", len(param_set.params))
    print("耗时", time.perf_counter() - start_time)

    print("-" * 30)
    start_time = time.perf_counter()

    backtest_result = pyo3_quant.run_backtest_engine(
        data_dict,  # DataDict dataclass
        param_set,  # ParamSet dataclass
        template_config,  # TemplateConfig dataclass
        processed_settings,  # EngineSettings dataclass
    )

    print("performance:", backtest_result[0]["performance"])

    print("耗时", time.perf_counter() - start_time)
    import pdb; pdb.set_trace()
    
    
    