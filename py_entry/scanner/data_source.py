from typing import TYPE_CHECKING, Protocol
import pandas as pd
import numpy as np

if TYPE_CHECKING:
    from tqsdk import TqAuth  # type: ignore

from tqsdk import TqApi  # type: ignore


class DataSourceProtocol(Protocol):
    """数据源接口定义"""

    def get_klines(
        self, symbol: str, duration_seconds: int, data_length: int = 200
    ) -> pd.DataFrame: ...

    def wait(self, seconds: float) -> None: ...

    def close(self) -> None: ...


class TqDataSource:
    """天勤量化数据源封装"""

    def __init__(self, auth: "TqAuth | None" = None):
        """
        初始化数据源

        Args:
            auth: 天勤账号认证，免费版可传 None 使用游客模式
        """
        self.api = TqApi(auth=auth) if auth else TqApi()

    def get_klines(
        self, symbol: str, duration_seconds: int, data_length: int = 200
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 合约代码，如 "SHFE.au@MAIN"
            duration_seconds: K线周期（秒）
            data_length: 获取数量（免费版最多8000根）

        Returns:
            包含 datetime, open, high, low, close, volume, open_interest 等列的 DataFrame
        """
        klines = self.api.get_kline_serial(symbol, duration_seconds, data_length)
        # TqSdk 返回的 klines 已经是 DataFrame 格式，直接 copy 一份快照即可
        return klines.copy()

    def wait(self, seconds: float):
        """
        等待指定时间，期间驱动 TqSdk 事件循环更新数据
        """
        import time
        import logging

        logger = logging.getLogger("scanner.data_source")

        deadline = time.time() + seconds
        while time.time() < deadline:
            # wait_update 会在有数据更新时返回 或者 超时返回
            # 我们使用 deadline 参数让它在剩余时间内持续工作
            try:
                self.api.wait_update(deadline=deadline)
            except (ConnectionError, TimeoutError, OSError) as e:
                # 只捕获网络/连接相关的异常
                logger.warning(f"网络异常，继续等待: {e}")
            except Exception as e:
                # 其他异常打印日志并重新抛出，避免掩盖真正问题
                logger.error(f"wait_update 发生非预期异常: {e}")
                raise

    def close(self):
        """关闭连接"""
        self.api.close()


class MockDataSource:
    """模拟数据源 - 用于离线测试"""

    def __init__(self):
        print("注意: 正在使用 MockDataSource (生成模拟数据)")

    def get_klines(
        self, symbol: str, duration_seconds: int, data_length: int = 200
    ) -> pd.DataFrame:
        """生成随机K线数据"""
        # 生成时间索引
        end_time = pd.Timestamp.now()
        freq = f"{duration_seconds}s"
        times = pd.date_range(end=end_time, periods=data_length, freq=freq)

        # 随机游走生成收盘价
        # 起始价格根据 symbol hash 稍微变动一下，避免所有品种一样
        start_price = 1000 + (hash(symbol) % 1000)
        returns = np.random.normal(0, 0.002, data_length)
        price = start_price * np.exp(np.cumsum(returns))

        # 为了测试“共振”，我们强制让最后一段是上涨趋势
        # 模拟强劲上涨：最后 20 根K线持续上涨
        if "au" in symbol or "cu" in symbol:  # 让黄金铜走出共振
            trend = np.linspace(0, 0.05, 30)  # 最后30根涨5%
            price[-30:] = price[-30:] * (1 + trend)

        close = pd.Series(price, index=times)

        # 生成OHLC
        high = close * (1 + np.abs(np.random.normal(0, 0.001, data_length)))
        low = close * (1 - np.abs(np.random.normal(0, 0.001, data_length)))
        open_ = close.shift(1).fillna(start_price)

        # 修正 high/low
        high = pd.concat([high, open_], axis=1).max(axis=1)
        low = pd.concat([low, open_], axis=1).min(axis=1)

        df = pd.DataFrame(
            {
                "datetime": times,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.randint(100, 10000, data_length),
                "open_interest": np.random.randint(5000, 50000, data_length),
            }
        )

        return df

    def wait(self, seconds: float):
        """Mock模式直接睡眠"""
        import time

        time.sleep(seconds)

    def close(self):
        pass
