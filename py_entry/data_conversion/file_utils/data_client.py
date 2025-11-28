# 所有导入必须在 sys.path 修改之后立即进行
import json
from dataclasses import dataclass
from typing import Any

import httpx
import polars as pl

from py_entry.data_conversion.file_utils.common import make_authenticated_request
from py_entry.data_conversion.file_utils.types import RequestConfig


@dataclass
class OhlcvDataConfig:
    """OHLCV数据获取配置类"""

    config: RequestConfig
    exchange_name: str
    symbol: str
    period: str
    start_time: int
    count: int = 10
    enable_cache: bool = True


def get_ohlcv_data(
    ohlcv_config: OhlcvDataConfig,
) -> dict[str, Any] | None:
    """
    从服务器获取 OHLCV 数据。

    参数:
    ohlcv_config: OHLCV数据获取配置对象

    返回:
    dict | None: 获取到的数据，如果获取失败则返回 None。
    """

    def get_data_request(
        client: httpx.Client, headers: dict[str, str]
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "exchange_name": ohlcv_config.exchange_name,
            "symbol": ohlcv_config.symbol,
            "period": ohlcv_config.period,
            "start_time": ohlcv_config.start_time,
            "count": ohlcv_config.count,
            "enable_cache": ohlcv_config.enable_cache,
        }

        response = client.get(
            f"{ohlcv_config.config.auth.server_url}/ccxt/ohlcv",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    return make_authenticated_request(
        config=ohlcv_config.config,
        request_func=get_data_request,
        error_context="获取数据",
    )


def convert_to_ohlcv_dataframe(result: Any) -> pl.DataFrame | None:
    """
    将 get_ohlcv_data 函数返回的结果转换为 Polars DataFrame。

    参数:
        result: get_ohlcv_data 函数返回的数据，格式为 [[timestamp, open, high, low, close, volume, date_string], ...]

    返回:
        pl.DataFrame | None: 包含 time, open, high, low, close, volume 字段的 Polars DataFrame，
                            如果输入为 None 或数据格式不正确则返回 None
    """
    if not result:
        return None

    try:
        # 实际返回的数据格式为 [[timestamp, open, high, low, close, volume, date_string], ...]
        data = result

        if not data or len(data) == 0:
            return None

        # 创建 Polars DataFrame，明确指定数据类型
        df = pl.DataFrame(
            {
                "time": [item[0] for item in data],
                "open": [float(item[1]) for item in data],
                "high": [float(item[2]) for item in data],
                "low": [float(item[3]) for item in data],
                "close": [float(item[4]) for item in data],
                "volume": [float(item[5]) for item in data],
            },
            schema={
                "time": pl.Int64,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            },
        )

        return df
    except (IndexError, KeyError, TypeError, ValueError) as e:
        print(f"转换数据时出错: {e}")
        return None


if __name__ == "__main__":
    with open("data/config.json", "r", encoding="utf-8") as file:
        data = json.load(file)

    config = RequestConfig.create(
        username=data["username"],
        password=data["password"],
        server_url=data["server_api"],
        max_retries=0,  # 数据获取失败不重试，除了401错误
    )

    # 调用 get_ohlcv_data 函数
    ohlcv_config = OhlcvDataConfig(
        config=config,
        exchange_name="binance",
        symbol="BTC/USDT",
        period="15m",
        start_time=1740787200000,
        count=10,
        enable_cache=True,
    )
    result = get_ohlcv_data(ohlcv_config)

    ohlcv_df = convert_to_ohlcv_dataframe(result)
    print(ohlcv_df)
