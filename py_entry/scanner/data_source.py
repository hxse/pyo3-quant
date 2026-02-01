from typing import TYPE_CHECKING, Protocol
import pandas as pd
import numpy as np

if TYPE_CHECKING:
    from tqsdk import TqAuth

from tqsdk import TqApi


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
        # 1. 固定随机种子：确保每次运行结果一致
        # 使用 symbol + duration 的 hash 值作为种子
        seed_value = abs(hash(symbol + str(duration_seconds))) % (2**32)
        rng = np.random.default_rng(seed_value)

        # 生成时间索引
        end_time = pd.Timestamp.now()
        freq = f"{duration_seconds}s"
        # 生成 DatetimeIndex 并转换为 int64 (nanoseconds)
        times = pd.date_range(end=end_time, periods=data_length, freq=freq).astype(
            "int64"
        )

        # 随机游走生成收盘价
        start_price = 1000 + (seed_value % 1000)
        returns = rng.normal(0, 0.002, data_length)
        price = start_price * np.exp(np.cumsum(returns))

        # --- 2. 注入共振模式 ---

        # 定义做多/做空测试品种（需在 config.py 的 symbols 中存在）
        bullish_symbols = ["rb", "p"]  # 螺纹钢, 棕榈油 -> 做多
        bearish_symbols = ["TA"]  # PTA -> 做空

        is_bullish = any(s in symbol for s in bullish_symbols)
        is_bearish = any(s in symbol for s in bearish_symbols)

        if is_bullish:
            if duration_seconds == 300:
                # 5分钟线：制造刚刚 上穿 EMA 的形态
                # 策略：价格直接设为平盘，最后两根制造穿越
                # 倒数第二根 < 1000, 倒数第一根 > 1000
                price[:] = 1000.0
                price[-2] = 990.0  # 下方
                price[-1] = 1010.0  # 上方
            else:
                # 长周期：制造强劲 上涨 趋势 (CCI > 80)
                # 线性上涨 10%
                trend = np.linspace(0, 0.10, 30)
                price[-30:] = price[-30:] * (1 + trend)

        elif is_bearish:
            if duration_seconds == 300:
                # 5分钟线：制造刚刚 下穿 EMA 的形态
                # 策略：价格直接设为平盘，最后两根制造穿越
                # 倒数第二根 > 1000, 倒数第一根 < 1000
                price[:] = 1000.0
                price[-2] = 1010.0  # 上方
                price[-1] = 990.0  # 下方
            else:
                # 长周期：制造强劲 下跌 趋势 (CCI < -80)
                # 线性下跌 10%
                trend = np.linspace(0, 0.10, 30)
                price[-30:] = price[-30:] * (1 - trend)

        close = pd.Series(price, index=times)

        # 生成OHLC
        # 默认波动
        high = close * (1 + np.abs(rng.normal(0, 0.001, data_length)))
        low = close * (1 - np.abs(rng.normal(0, 0.001, data_length)))

        # open 默认 shift(1)
        open_ = close.shift(1).fillna(start_price)

        # 修正 5m 数据的 open/high/low 以匹配人工构造的 price
        if (is_bullish or is_bearish) and duration_seconds == 300:
            pass  # 默认逻辑已经能生成合理 candles

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
                "volume": rng.integers(100, 10000, data_length),
                "open_interest": rng.integers(5000, 50000, data_length),
            }
        )

        return df

    def wait(self, seconds: float):
        """Mock模式直接睡眠"""
        import time

        time.sleep(seconds)

    def close(self):
        pass
