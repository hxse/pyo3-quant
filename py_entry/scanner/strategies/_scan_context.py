from datetime import datetime

import pandas as pd
import polars as pl

from py_entry.data_generator import DirectDataConfig, generate_data_pack
from py_entry.scanner.config import ScanLevel, TimeframeConfig
from py_entry.types import DataPack


class ScanContext:
    """扫描上下文 - 策略输入"""

    def __init__(
        self,
        symbol: str,
        klines: dict[str, pd.DataFrame],
        timeframes: dict[str, TimeframeConfig],
        level_to_tf: dict[ScanLevel, str],
        updated_levels: set[ScanLevel] | None = None,
    ):
        """
        Args:
            symbol: 品种名称
            klines: K线缓存字典，key 为 storage_key
            timeframes: storage_key 与周期配置的映射
            level_to_tf: 级别与 storage_key 的映射
            updated_levels: 本次扫描时刚刚更新过 bar 的逻辑级别集合
        """
        self.symbol = symbol
        self.klines = klines
        self.timeframes = timeframes
        self.level_to_tf = level_to_tf
        self.updated_levels = updated_levels or set()

    def get_tf_name(self, level: ScanLevel) -> str | None:
        """获取级别对应的物理周期名称"""
        storage_key = self.level_to_tf.get(level)
        if storage_key is None:
            return None
        tf = self.timeframes.get(storage_key)
        return tf.name if tf is not None else None

    def get_storage_key(self, level: ScanLevel) -> str:
        """获取级别对应的内部存储键。"""
        storage_key = self.level_to_tf.get(level)
        if storage_key is None:
            raise ValueError(f"未定义的级别: {level}")
        return storage_key

    def get_timeframe(self, level: ScanLevel) -> TimeframeConfig:
        """获取级别对应的完整周期配置。"""
        storage_key = self.get_storage_key(level)
        tf = self.timeframes.get(storage_key)
        if tf is None:
            raise ValueError(f"未定义的周期配置: {storage_key}")
        return tf

    def get_level_dk(self, level: ScanLevel) -> str:
        """获取级别对应的数据源键名。"""
        return f"ohlcv_{self.get_timeframe(level).name}"

    def get_klines_by_level(self, level: ScanLevel) -> pd.DataFrame | None:
        """直接通过级别获取 K 线数据"""
        return self.klines.get(self.get_storage_key(level))

    def validate_levels_existence(self, required_levels: list[ScanLevel]) -> None:
        """检查必要级别数据是否存在且不为空"""
        missing = []
        for lv in required_levels:
            df = self.get_klines_by_level(lv)
            if df is None or df.empty:
                missing.append(lv)

        if missing:
            raise ValueError(f"缺少必要级别数据: {missing}")

    def derive_context(self, level_to_tf: dict[ScanLevel, str]) -> "ScanContext":
        """基于当前缓存构造局部子上下文。"""
        required_storage_keys = set(level_to_tf.values())
        child_updated_levels = {
            level for level in self.updated_levels if level in level_to_tf
        }
        return ScanContext(
            symbol=self.symbol,
            klines={
                storage_key: self.klines[storage_key]
                for storage_key in required_storage_keys
            },
            timeframes={
                storage_key: self.timeframes[storage_key]
                for storage_key in required_storage_keys
            },
            level_to_tf=level_to_tf,
            updated_levels=child_updated_levels,
        )

    def is_level_updated(self, level: ScanLevel) -> bool:
        """判断本次扫描是否由该级别的新 bar 驱动。"""
        return level in self.updated_levels

    def to_data_pack(
        self,
        base_level: ScanLevel = ScanLevel.TRIGGER,
        lookback: int | None = None,
    ) -> DataPack:
        """
        将当前 K 线上下文转换为 BacktestEngine 所需的 DataPack

        Args:
            base_level: 基准级别 (如 ScanLevel.TRIGGER)
            lookback: 可选的回溯长度
        """
        source_dict = {}
        base_dk = self.get_level_dk(base_level)

        for storage_key, pdf in self.klines.items():
            key = f"ohlcv_{self.timeframes[storage_key].name}"
            target_df = pdf if lookback is None else pdf.iloc[-lookback:]

            pl_df = (
                pl.from_pandas(target_df)
                .rename({"datetime": "time"})
                .with_columns(
                    (pl.col("time").cast(pl.Int64) // 1_000_000).alias("time")
                )
            )

            assert pl_df["time"].dtype == pl.Int64

            if not pl_df.is_empty():
                first_ts = pl_df["time"][0]
                sample_year = pl.select(
                    pl.lit(first_ts).cast(pl.Datetime("ms")).dt.year()
                ).item()
                current_year = datetime.now().year
                assert 1970 <= sample_year <= current_year + 10, (
                    f"时间戳异常: 解析年份 {sample_year} 超出合理范围 "
                    f"(1970 ~ {current_year + 10})。期望毫秒级时间戳。"
                )

            source_dict[key] = pl_df

        config = DirectDataConfig(
            data=source_dict,
            base_data_key=base_dk,
            align_to_base_range=False,
        )
        # 中文注释：扫描器需要多周期完整历史用于指标计算，禁止按 base 时间范围裁短高周期数据。
        return generate_data_pack(config)
