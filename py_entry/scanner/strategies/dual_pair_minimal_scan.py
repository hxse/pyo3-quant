from typing import Final

from py_entry.scanner.config import ScanLevel, TimeframeConfig
from py_entry.scanner.strategies.base import (
    ScanContext,
    StrategyBase,
    StrategySignal,
    format_timestamp,
    run_scan_backtest,
)
from py_entry.scanner.strategies.registry import StrategyRegistry
from py_entry.types import LogicOp, Param, SignalGroup, SignalTemplate


@StrategyRegistry.register
class DualPairMinimalScanStrategy(StrategyBase):
    """
    最小裁量扫描策略

    设计原则：
    1. 扫描器只负责给出最低限度值得看盘的行情。
    2. 不附加更多过滤条件，避免把扫描器做成交易指导系统。
    3. 仅实现用户明确给出的多头口径，不擅自扩写空头镜像。
    """

    name: Final[str] = "dual_pair_minimal_scan"
    ER_THRESHOLD_RATIO: Final[float] = 0.2

    def get_timeframes(self, defaults: list[TimeframeConfig]) -> list[TimeframeConfig]:
        """仅该策略把 wave 周期覆盖为 30m，其余级别沿用默认画像。"""
        default_by_level = {tf.level: tf for tf in defaults}
        return [
            default_by_level[ScanLevel.TRIGGER].model_copy(deep=True),
            TimeframeConfig(
                level=ScanLevel.WAVE, name="30m", seconds=30 * 60, use_index=False
            ),
            default_by_level[ScanLevel.TREND].model_copy(deep=True),
            default_by_level[ScanLevel.MACRO].model_copy(deep=True),
        ]

    def get_watch_levels(self) -> list[ScanLevel]:
        """5m 与 30m 任一更新，都可能产生新的观察信号。"""
        return [ScanLevel.TRIGGER, ScanLevel.WAVE]

    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        # 中文注释：本策略依赖 5m / 30m / 1d / 1w 四个层级。
        required_levels = [
            ScanLevel.TRIGGER,
            ScanLevel.WAVE,
            ScanLevel.TREND,
            ScanLevel.MACRO,
        ]
        ctx.validate_levels_existence(required_levels)

        fired_pairs: list[dict[str, float | int | str]] = []

        if ctx.is_level_updated(ScanLevel.TRIGGER):
            trigger_pair = self._scan_pair(
                ctx=ctx,
                lower_level=ScanLevel.TRIGGER,
                higher_level=ScanLevel.TREND,
            )
            if trigger_pair is not None:
                fired_pairs.append(trigger_pair)

        if ctx.is_level_updated(ScanLevel.WAVE):
            wave_pair = self._scan_pair(
                ctx=ctx,
                lower_level=ScanLevel.WAVE,
                higher_level=ScanLevel.MACRO,
            )
            if wave_pair is not None:
                fired_pairs.append(wave_pair)

        if not fired_pairs:
            return None

        # 中文注释：主展示值取最近一次触发的组合，详情里保留全部触发组合。
        latest_pair = max(fired_pairs, key=lambda item: int(item["time"]))
        trigger_labels = [str(item["pair_label"]) for item in fired_pairs]

        detail_lines = [
            f"时间: {format_timestamp(int(latest_pair['time']))}",
            f"价格: {latest_pair['price']}",
            "定位: 扫描器只负责筛出最低限度值得看盘的行情，是否参与交给盘感。",
        ]
        detail_lines.extend(
            str(item["detail"]) for item in fired_pairs if "detail" in item
        )

        return StrategySignal(
            strategy_name=self.name,
            symbol=ctx.symbol,
            direction="long",
            trigger=f"{' / '.join(trigger_labels)} 多头触发",
            summary=f"{ctx.symbol} minimal scan 观察多头机会",
            detail_lines=detail_lines,
            metadata={
                "price": latest_pair["price"],
                "time": latest_pair["time"],
                "fired_pairs": trigger_labels,
            },
        )

    def _scan_pair(
        self,
        ctx: ScanContext,
        lower_level: ScanLevel,
        higher_level: ScanLevel,
    ) -> dict[str, float | int | str] | None:
        """执行单组周期组合扫描。"""
        lower_dk = ctx.get_level_dk(lower_level)
        higher_dk = ctx.get_level_dk(higher_level)

        lower_tf_name = ctx.get_tf_name(lower_level)
        higher_tf_name = ctx.get_tf_name(higher_level)
        if lower_tf_name is None or higher_tf_name is None:
            raise ValueError(f"未定义的扫描组合: {lower_level} -> {higher_level}")

        # 中文注释：回测容器要求 base_level 必须是当前容器里的最小周期。
        # 因此每次只为当前组合构造局部上下文，避免 30m 组合被全局 5m 数据压住。
        pair_ctx = ctx.derive_context(
            level_to_tf={
                lower_level: ctx.get_storage_key(lower_level),
                higher_level: ctx.get_storage_key(higher_level),
            }
        )

        indicators = {
            lower_dk: {
                "ema_fast": {"period": Param(20)},
                "ema_slow": {"period": Param(50)},
                # 中文注释：ER 周期未单独指定，沿用 pandas-ta 常见默认长度 10。
                "er_ltf": {"length": Param(10)},
            },
            higher_dk: {
                "ema_htf_fast": {"period": Param(20)},
                "ema_htf_slow": {"period": Param(50)},
            },
        }

        template = SignalTemplate(
            entry_long=SignalGroup(
                logic=LogicOp.AND,
                comparisons=[
                    f"close,{lower_dk},0 > ema_htf_fast,{higher_dk},0",
                    f"close,{lower_dk},0 > ema_htf_slow,{higher_dk},0",
                    f"ema_fast,{lower_dk},0 > ema_slow,{lower_dk},0",
                    f"close,{lower_dk},0 x> ema_fast,{lower_dk},0",
                    # 中文注释：底层 ER 指标返回 0~1 比例值，盘面口径的“20”需要映射为 0.2。
                    f"er_ltf,{lower_dk},0 > {self.ER_THRESHOLD_RATIO}",
                ],
            ),
            entry_short=SignalGroup(
                logic=LogicOp.AND,
                # 中文注释：本策略不实现空头口径，这里只保留统一模板所需的占位条件。
                comparisons=[f"close,{lower_dk},0 < 0"],
            ),
        )

        result = run_scan_backtest(
            ctx=pair_ctx,
            indicators=indicators,
            signal_template=template,
            base_level=lower_level,
        )
        if result is None:
            return None

        signal_dict, price, timestamp_ms = result
        long_signal = signal_dict.get("entry_long", 0.0)
        if long_signal <= 0.5:
            return None

        return {
            "pair_label": f"{lower_tf_name} + {higher_tf_name}",
            "price": price,
            "time": timestamp_ms,
            "detail": (
                f"组合: {lower_tf_name} + {higher_tf_name} | "
                f"条件: {lower_tf_name} close > {higher_tf_name} EMA20/EMA50, "
                f"{lower_tf_name} EMA20 > EMA50, "
                f"{lower_tf_name} close x> EMA20, "
                f"{lower_tf_name} ER > 20"
            ),
        }
