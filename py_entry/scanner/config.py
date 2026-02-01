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
    adx_period: int = 14


class TimeframeConfig(BaseModel):
    """单个周期配置"""

    name: str  # 周期名称，如 "5m", "1h"
    seconds: int  # 秒数
    check_type: Literal["crossover", "macd", "cci"]  # 检查逻辑类型
    indicator: IndicatorConfig = IndicatorConfig()  # 每个周期独立的指标配置


class ScannerConfig(BaseModel):
    """扫描器主配置"""

    # 天勤账户配置 (必须配置)
    tq_username: str = ""
    tq_password: str = ""

    # ADX 辅助参考配置
    adx_warning_threshold: float = 25.0
    adx_warning_message: str = "⚠️ 周线ADX走弱，下调预期，建议5分钟1:2直接离场，别拿太久"

    # 节流配置
    # 是否启用节流模式（True: 仅窗口期活跃; False: 全天候活跃）
    enable_throttler: bool = True
    # 窗口宽度（秒），即在 5分钟整点前后多少秒内为活跃期
    throttle_window_seconds: int = 30
    # 非窗口期维持心跳的调用间隔（秒）
    heartbeat_interval_seconds: int = 10

    # K线数据获取数量（默认200，最小建议50，最大8000）
    kline_length: int = 200

    # Telegram 配置
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # 心跳推送配置
    # 是否在控制台打印每次扫描后的心跳 (只有共振机会才会推送到 TG)
    console_heartbeat_enabled: bool = True

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

            except Exception as e:
                raise RuntimeError(f"读取配置文件 {config_path} 失败: {e}") from e
        return data

    # 方案一：经典四周期 (5m, 1h, 1d, 1w) - 从周线开始，更可靠
    timeframes: list[TimeframeConfig] = [
        TimeframeConfig(name="5m", seconds=5 * 60, check_type="crossover"),
        TimeframeConfig(name="1h", seconds=60 * 60, check_type="macd"),
        TimeframeConfig(
            name="1d",
            seconds=24 * 3600,
            check_type="cci",
            indicator=IndicatorConfig(cci_threshold=30.0),  # 日线 CCI > 30
        ),
        TimeframeConfig(
            name="1w",
            seconds=7 * 24 * 3600,
            check_type="cci",
            indicator=IndicatorConfig(cci_threshold=80.0),  # 周线 CCI > 80
        ),
    ]

    # 需要扫描的期货品种（主力合约）
    symbols: list[str] = [
        # ====================
        #  黑色系 / 建材
        # ====================
        "KQ.m@SHFE.rb",  # 螺纹钢
        "KQ.m@SHFE.hc",  # 热卷
        "KQ.m@CZCE.FG",  # 玻璃
        # 成本较高或流动性一般：
        # "KQ.m@DCE.i",    # 铁矿石 (>1w)
        # "KQ.m@DCE.j",    # 焦炭 (>2w)
        # "KQ.m@DCE.jm",   # 焦煤 (>1w)
        # "KQ.m@CZCE.SM",  # 锰硅 (流动性较差)
        # "KQ.m@CZCE.SF",  # 硅铁 (流动性较差)
        # ====================
        #  能源 / 化工
        # ====================
        "KQ.m@SHFE.bu",  # 沥青
        "KQ.m@SHFE.fu",  # 燃油
        "KQ.m@CZCE.MA",  # 甲醇
        "KQ.m@CZCE.UR",  # 尿素
        "KQ.m@CZCE.TA",  # PTA
        "KQ.m@CZCE.SA",  # 纯碱
        "KQ.m@DCE.eg",  # 乙二醇
        "KQ.m@DCE.v",  # PVC
        "KQ.m@DCE.pp",  # 聚丙烯
        "KQ.m@DCE.l",  # 塑料
        # 成本较高或流动性一般：
        # "KQ.m@SHFE.ru",  # 橡胶 (>1w)
        # "KQ.m@SHFE.sp",  # 纸浆 (接近1w)
        # "KQ.m@CZCE.PF",  # 短纤 (流动性一般)
        # ====================
        #  油脂 / 农产
        # ====================
        "KQ.m@DCE.p",  # 棕榈油
        "KQ.m@DCE.y",  # 豆油
        "KQ.m@CZCE.OI",  # 菜油
        "KQ.m@DCE.m",  # 豆粕
        "KQ.m@CZCE.RM",  # 菜粕
        "KQ.m@CZCE.SR",  # 白糖
        "KQ.m@CZCE.CF",  # 棉花
        "KQ.m@DCE.c",  # 玉米
        "KQ.m@DCE.cs",  # 淀粉
        # ====================
        #  有色 / 贵金属
        #  (多数成本>1w，暂不关注)
        # ====================
        # "KQ.m@SHFE.cu",  # 铜 (>3w)
        # "KQ.m@SHFE.al",  # 铝 (~1w)
        # "KQ.m@SHFE.zn",  # 锌 (>1w)
        # "KQ.m@SHFE.ni",  # 镍 (>2w)
        # "KQ.m@SHFE.ag",  # 白银 (>1w)
        # "KQ.m@SHFE.au",  # 黄金 (>5w)
    ]

    # 板块指数映射
    # 天勤SDK(免费版/专业版)目前均不直接提供文华商品指数/板块指数等聚合行情数据。
    # 按照 manual_trading.md 的哲学，理想状态需要进行已"大盘/板块"的共振确认。
    # 但由于数据源限制，目前不得不移除该功能，只保留"品种自身多周期共振"。
    sector_indices: dict[str, str] = {}

    # 品种所属板块
    symbol_sector: dict[str, str] = {}

    # 大盘指数
    # 同上，因无法获取权威大盘指数，暂无法进行大盘环境过滤。
    market_index: str = ""
