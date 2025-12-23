from loguru import logger
import json

# 项目导入
import pyo3_quant

from py_entry.data_conversion.backtest_runner import BacktestRunner
from py_entry.data_conversion.types import Param
from py_entry.data_conversion.data_generator import DataGenerationParams
from py_entry.data_conversion.file_utils import RequestConfig


# 创建 DataGenerationParams 对象
simulated_data_config = DataGenerationParams(
    timeframes=["15m", "1h"],
    start_time=1735689600000,
    num_bars=10000,
    fixed_seed=42,
    BaseDataKey="ohlcv_15m",
)

# 构建指标参数
indicators_params = {
    "ohlcv_15m": {
        "sma_0": {"period": Param.create(14, 5, 50, 1)},
        "sma_1": {
            "period": Param.create(200, 100, 300, 10),
        },
    },
    "ohlcv_4h": {  # 数据没有4h, 预期报错
        "sma_0": {"period": Param.create(14, 5, 50, 1)},
    },
}


if __name__ == "__main__":
    # 配置logger
    # 创建启用时间测量的 BacktestRunner
    br = BacktestRunner(enable_timing=False)

    # 使用链式调用执行完整的回测流程
    logger.info("开始执行回测流程")

    # 读取配置文件
    with open("data/config.json", "r") as f:
        json_config = json.load(f)

    request_cfg = RequestConfig.create(
        username=json_config["username"],
        password=json_config["password"],
        server_url=json_config["server_url"],
    )

    try:
        # 完整的链式调用：配置 -> 运行 -> 保存 -> 上传
        br.setup(
            data_source=simulated_data_config,
            indicators_params=indicators_params,
        ).run()
    except pyo3_quant.errors.PyDataSourceNotFoundError as e:
        logger.info(f"成功捕获异常: {e}")
