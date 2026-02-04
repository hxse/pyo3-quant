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

    def get_underlying_symbol(self, symbol: str) -> str: ...

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

    def get_underlying_symbol(self, symbol: str) -> str:
        """
        获取主连合约背后的真实主力合约代码

        Args:
            symbol: 主连合约代码，如 "KQ.m@DCE.i"

        Returns:
            真实合约代码，如 "DCE.i2505"
            如果获取失败或本身就是具体合约，则返回原 symbol
        """
        try:
            quote = self.api.get_quote(symbol)
            underlying = getattr(quote, "underlying_symbol", "")
            if underlying:
                return underlying
            return symbol
        except Exception:
            return symbol

    def close(self):
        """关闭连接"""
        self.api.close()


class MockDataSource:
    """模拟数据源 - 用于离线测试"""

    def __init__(self, symbols: list[str] | None = None, seed: int = 42):
        print(f"注意: 正在使用 MockDataSource (生成模拟数据, 固定种子={seed})")
        # symbols 参数仅用于兼容，实际上 mock 生成逻辑内部可能用到
        self.symbols = symbols if symbols else []
        self.base_seed = seed

    def get_klines(
        self, symbol: str, duration_seconds: int, data_length: int = 200
    ) -> pd.DataFrame:
        """生成随机K线数据"""
        import zlib

        # 1. 确定性随机种子生成
        # 使用 zlib.adler32 替代 hash()，因为 python 的 hash() 是进程随机的
        # hack: 为了让 mock 模式下 KQ.i 和 KQ.m 的数据看起来像是有相关性的（或者就是同一份），我们去掉 .i/.m
        seed_symbol = symbol.replace("KQ.i@", "KQ.m@")
        symbol_code = zlib.adler32(seed_symbol.encode("utf-8"))
        # 组合 base_seed, symbol特征, 周期特征
        local_seed = (self.base_seed + symbol_code + duration_seconds) % (2**32)

        # 创建局部随机生成器，绝对不污染全局 np.random
        rng = np.random.default_rng(local_seed)

        # 生成时间索引 (为了 mock 稳定，时间最好也是按照逻辑生成的，而不是 now)
        # 这里为了简单，我们还是用 now，但对于测试复现，最好是固定的 end_time
        # 如果需要严格复现，应该把 end_time 也固定下来
        # 这里暂且保留 pd.Timestamp.now()，因为用户主要关心 K 线形态
        end_time = pd.Timestamp.now().round("1s")
        freq = f"{duration_seconds}s"
        # 生成 DatetimeIndex (默认 ns 精度)
        times = pd.date_range(end=end_time, periods=data_length, freq=freq)

        # 随机游走生成收盘价
        start_price = 1000 + (local_seed % 1000)
        returns = rng.normal(0, 0.002, data_length)
        price = start_price * np.exp(np.cumsum(returns))

        # --- 2. 注入共振模式 (保留以确保能测出信号) ---

        # 定义做多/做空测试品种（需在 config.py 的 symbols 中存在）
        bullish_symbols = ["rb", "p"]  # 螺纹钢, 棕榈油 -> 做多
        bearish_symbols = ["TA"]  # PTA -> 做空

        is_bullish = any(s in symbol for s in bullish_symbols)
        is_bearish = any(s in symbol for s in bearish_symbols)

        if is_bullish:
            if duration_seconds >= 86400:
                # 日线/周线：制造长期大幅上涨，确保 CCI > 100
                # 策略: 从一半位置开始，稳步拉升 30%
                half_len = data_length // 2
                trend = np.linspace(0, 0.30, half_len)
                price[-half_len:] = price[-half_len:] * (1 + trend)

            elif duration_seconds == 3600:
                # 1小时线：制造近期上涨，确保 MACD 为红柱 (快线 > 慢线)
                # 策略: 最后 1/3 数据拉升 15%
                part_len = data_length // 3
                trend = np.linspace(0, 0.15, part_len)
                price[-part_len:] = price[-part_len:] * (1 + trend)

            elif duration_seconds == 300:
                # 5分钟线：制造刚刚 上穿 EMA 的形态
                # 策略：前段微涨保持均线多头，最后两根制造强力突破
                # 先微涨 5% 垫高均线
                price[:] = price * np.linspace(1.0, 1.05, data_length)
                # 最后制造突破 (注意 Scanner 检查的是倒数第二根 -2)
                base_close = price[-4]
                price[-3] = base_close * 0.995  # N-3: 回踩
                price[-2] = base_close * 1.020  # N-2: 突破 (大阳线) -> 信号点
                price[-1] = price[-2] * 1.001  # N-1: 保持

        elif is_bearish:
            if duration_seconds >= 86400:
                # 日线/周线：制造长期大幅下跌，确保 CCI < -100
                half_len = data_length // 2
                trend = np.linspace(0, 0.30, half_len)
                price[-half_len:] = price[-half_len:] * (1 - trend)

            elif duration_seconds == 3600:
                # 1小时线：制造近期下跌
                part_len = data_length // 3
                trend = np.linspace(0, 0.15, part_len)
                price[-part_len:] = price[-part_len:] * (1 - trend)

            elif duration_seconds == 300:
                # 5分钟线：制造刚刚 下穿 EMA 的形态
                price[:] = price * np.linspace(1.0, 0.95, data_length)
                base_close = price[-4]
                price[-3] = base_close * 1.005  # N-3: 反抽
                price[-2] = base_close * 0.980  # N-2: 破位 (大阴线) -> 信号点
                price[-1] = price[-2] * 0.999  # N-1: 保持

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

        # 3. 组装 DataFrame
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

    def get_underlying_symbol(self, symbol: str) -> str:
        """Mock 返回虚拟的主力合约"""
        # 简单的规则：KQ.m@DCE.i -> DCE.i2501 (模拟)
        parts = symbol.split("@")
        if len(parts) == 2:
            exchange_vari = parts[1]  # SHFE.rb
            return f"{exchange_vari}2505"  # 假装主力是 2505
        return symbol

    def close(self):
        pass
