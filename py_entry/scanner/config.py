"""扫描器配置 - 与项目其他模块完全独立"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, model_validator


class TimeframeConfig(BaseModel):
    """单个周期配置"""

    name: str  # 周期名称，如 "5m", "1h"
    seconds: int  # 秒数
    use_index: bool = False  # 是否使用指数合约 (KQ.i@) 获取数据


# --- 周期与数据键名常量 ---
TF_5M = "5m"
TF_1H = "1h"
TF_1D = "1d"
TF_1W = "1w"

DK_5M = f"ohlcv_{TF_5M}"
DK_1H = f"ohlcv_{TF_1H}"
DK_1D = f"ohlcv_{TF_1D}"
DK_1W = f"ohlcv_{TF_1W}"


class ScannerConfig(BaseModel):
    """扫描器主配置"""

    # 天勤账户配置 (必须配置)
    tq_username: str = ""
    tq_password: str = ""

    # 节流配置
    # 是否启用节流模式（True: 仅窗口期活跃; False: 全天候活跃）
    enable_throttler: bool = True
    # 窗口宽度（秒），即在 5分钟整点前后多少秒内为活跃期
    throttle_window_seconds: int = 30
    # 非窗口期维持心跳的调用间隔（秒）
    heartbeat_interval_seconds: int = 10

    # 批量缓冲配置
    batch_buffer_seconds: float = 2.5  # 批量更新缓冲窗口期（秒）

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
    # 大周期 (1h, 1d, 1w) 使用指数合约 (use_index=True) 以获取平滑趋势
    # 小周期 (5m) 使用主连合约 (use_index=False) 以获取真实价格突破
    timeframes: list[TimeframeConfig] = [
        TimeframeConfig(name=TF_5M, seconds=5 * 60, use_index=False),
        TimeframeConfig(name=TF_1H, seconds=60 * 60, use_index=True),
        TimeframeConfig(name=TF_1D, seconds=24 * 3600, use_index=True),
        TimeframeConfig(name=TF_1W, seconds=7 * 24 * 3600, use_index=True),
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
