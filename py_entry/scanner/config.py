"""扫描器配置 - 与项目其他模块完全独立"""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, model_validator


class IndicatorConfig(BaseModel):
    """指标参数配置"""

    ema_period: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    cci_period: int = 14
    cci_threshold: float = 80.0


class TimeframeConfig(BaseModel):
    """单个周期配置"""

    name: str  # 周期名称，如 "5m", "1h"
    seconds: int  # 秒数
    check_type: Literal["crossover", "macd", "cci"]  # 检查逻辑类型


class ScannerConfig(BaseModel):
    """扫描器主配置"""

    # 天勤账户配置 (必须配置)
    tq_username: str = ""
    tq_password: str = ""

    # 节流配置
    # 是否启用节流模式（True: 仅窗口期活跃; False: 全天候活跃）
    enable_throttler: bool = True
    # 窗口宽度（秒），即在 5分钟整点前后多少秒内为活跃期
    throttle_window_seconds: int = 10
    # 非窗口期维持心跳的调用间隔（秒）
    heartbeat_interval_seconds: int = 10

    # K线数据获取数量（默认200，最小建议50，最大8000）
    kline_length: int = 200

    # Telegram 配置
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @model_validator(mode="before")
    @classmethod
    def load_from_external_config(cls, data: Any) -> Any:
        # 如果是字典且尚未提供 username/password，尝试从文件读取
        if isinstance(data, dict):
            # 尝试读取项目根目录下的 data/config.json
            try:
                root_dir = Path(__file__).resolve().parents[2]
                config_path = root_dir / "data" / "config.json"

                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        external_config = json.load(f)

                        # 天勤账号
                        if not data.get("tq_username"):
                            data["tq_username"] = external_config.get("tq_username", "")
                        if not data.get("tq_password"):
                            data["tq_password"] = external_config.get("tq_password", "")

                        # Telegram 配置 (从 json 的 tg_ 前缀映射到 telegram_ 前缀)
                        if not data.get("telegram_bot_token"):
                            data["telegram_bot_token"] = external_config.get(
                                "tg_bot_token", ""
                            )
                        if not data.get("telegram_chat_id"):
                            data["telegram_chat_id"] = external_config.get(
                                "tg_chat_id", ""
                            )

            except Exception:
                # 读取失败则忽略
                pass
        return data

    # 方案一：经典四周期 (5m, 1h, 1d, 1w)
    # timeframes: list[TimeframeConfig] = [
    #     TimeframeConfig(name="5m", seconds=5 * 60, check_type="crossover"),
    #     TimeframeConfig(name="1h", seconds=60 * 60, check_type="macd"),
    #     TimeframeConfig(name="1d", seconds=24 * 3600, check_type="cci"),
    #     TimeframeConfig(name="1w", seconds=7 * 24 * 3600, check_type="cci"),
    # ]

    # 方案二：日内偏好 (3m, 15m, 1h, 1d) - 如需切换，请注释掉上方方案并取消下方注释
    timeframes: list[TimeframeConfig] = [
        TimeframeConfig(name="3m", seconds=3 * 60, check_type="crossover"),
        TimeframeConfig(name="15m", seconds=15 * 60, check_type="macd"),
        TimeframeConfig(name="1h", seconds=60 * 60, check_type="macd"),
        TimeframeConfig(name="1d", seconds=24 * 3600, check_type="cci"),
    ]

    # 需要扫描的期货品种（主力合约）
    symbols: list[str] = [
        # --- 黑色建材 ---
        "KQ.m@SHFE.rb",  # 螺纹钢
        "KQ.m@SHFE.bu",  # 沥青
        # --- 化工 ---
        "KQ.m@CZCE.MA",  # 甲醇
        "KQ.m@DCE.v",  # PVC
        "KQ.m@CZCE.TA",  # PTA
        # --- 农产品/油脂 ---
        "KQ.m@DCE.p",  # 棕榈油
        "KQ.m@CZCE.SR",  # 白糖
        "KQ.m@DCE.m",  # 豆粕
        "KQ.m@DCE.c",  # 玉米
    ]

    # 板块指数映射
    # TODO: 天勤SDK不支持文华商品指数等板块/大盘数据，暂无法实现板块和大盘过滤
    # 当前策略已退化为"只扫描品种自身多周期共振"
    sector_indices: dict[str, str] = {}

    # 品种所属板块
    symbol_sector: dict[str, str] = {}

    # 大盘指数
    # TODO: 同上，因无法获取权威大盘指数，暂不进行大盘环境过滤。
    market_index: str = ""

    indicator: IndicatorConfig = IndicatorConfig()
