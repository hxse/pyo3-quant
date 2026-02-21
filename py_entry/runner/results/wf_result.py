from typing import TYPE_CHECKING, Optional, Self, cast
from py_entry.types import (
    BacktestSummary,
    StitchedArtifact,
    WindowArtifact,
    WalkForwardResult,
    SingleParamSet,
    OptimizeMetric,
)
from py_entry.io import DisplayConfig
from py_entry.runner.results.log_level import LogLevel

if TYPE_CHECKING:
    from py_entry.runner import FormatResultsConfig
    from py_entry.runner.results.run_result import RunResult
    from py_entry.io import SaveConfig, UploadConfig


class WalkForwardResultWrapper:
    """向前测试结果"""

    def __init__(self, raw_result: WalkForwardResult, context: dict):
        self._raw = raw_result
        self._context = context
        self._stitched_run_result: "RunResult | None" = None

    @property
    def is_robust(self) -> bool:
        """判断是否稳健"""
        metrics = self.aggregate_test_metrics
        return metrics.get("total_return", 0.0) > 0

    @property
    def recommended_params(self) -> Optional[SingleParamSet]:
        """推荐参数范围（预留接口，暂不实现）"""
        return None

    @property
    def aggregate_test_metrics(self) -> dict:
        """测试集聚合指标"""
        stitched_summary = self._raw.stitched_result.summary
        return stitched_summary.performance or {}

    @property
    def optimize_metric(self) -> OptimizeMetric:
        """优化目标指标类型"""
        # Rust 侧已返回枚举实例，这里直接透传，避免重复构造导致 TypeError。
        return cast(OptimizeMetric, self._raw.optimize_metric)

    @property
    def raw(self) -> WalkForwardResult:
        return self._raw

    @property
    def stitched_result(self) -> StitchedArtifact:
        """拼接级完整产物"""
        return self._raw.stitched_result

    @property
    def window_results(self) -> list[WindowArtifact]:
        """窗口级完整产物数组"""
        return self._raw.window_results

    @property
    def stitched_summary(self) -> BacktestSummary:
        """拼接级回测摘要"""
        return self._raw.stitched_result.summary

    @property
    def stitched_time_range(self) -> list[int]:
        """拼接后样本外时间范围（UTC ms，[start, end]）"""
        start, end = self._raw.stitched_result.time_range
        return [start, end]

    @property
    def stitched_equity(self) -> list[float]:
        """拼接后样本外资金曲线（起点为 initial_capital）"""
        backtest_df = self._raw.stitched_result.summary.backtest_result
        if backtest_df is None:
            return []
        try:
            return backtest_df["equity"].to_list()
        except Exception:
            return []

    def _optimize_metric_key(self) -> str:
        """获取优化指标对应的 performance 字段键名"""
        return str(self.optimize_metric.as_str())

    def _is_minimize_metric(self) -> bool:
        """判断该优化指标是否是越小越优"""
        return self._optimize_metric_key() in {"max_drawdown"}

    @property
    def best_window_id(self) -> int:
        """测试集表现最优窗口 ID（仅返回 ID，不改变 window_results 原有时间顺序）"""
        windows = self._raw.window_results
        if not windows:
            return -1
        metric_key = self._optimize_metric_key()
        minimize = self._is_minimize_metric()
        best_id = windows[0].window_id
        best_score = float("inf") if minimize else float("-inf")
        for w in windows:
            metrics = w.summary.performance or {}
            default_score = float("inf") if minimize else float("-inf")
            score = float(metrics.get(metric_key, default_score))
            if (score < best_score) if minimize else (score > best_score):
                best_score = score
                best_id = w.window_id
        return best_id

    @property
    def worst_window_id(self) -> int:
        """测试集表现最差窗口 ID（仅返回 ID，不改变 window_results 原有时间顺序）"""
        windows = self._raw.window_results
        if not windows:
            return -1
        metric_key = self._optimize_metric_key()
        minimize = self._is_minimize_metric()
        worst_id = windows[0].window_id
        worst_score = float("-inf") if minimize else float("inf")
        for w in windows:
            metrics = w.summary.performance or {}
            default_score = float("-inf") if minimize else float("inf")
            score = float(metrics.get(metric_key, default_score))
            if (score > worst_score) if minimize else (score < worst_score):
                worst_score = score
                worst_id = w.window_id
        return worst_id

    def display(self, config: DisplayConfig | None = None):
        """显示向前测试图表"""
        return self.run_result.display(config=config)

    def _build_stitched_run_result(self) -> "RunResult":
        """构建 stitched 对应的 RunResult（不做格式化）。"""
        from py_entry.runner.results.run_result import RunResult

        windows = self.window_results
        if not windows:
            raise ValueError("window_results 为空，无法构建 stitched RunResult。")
        best_id = self.best_window_id
        target_window = next(
            (w for w in windows if w.window_id == best_id),
            windows[0],
        )
        return RunResult(
            summary=self.stitched_summary,
            params=target_window.best_params,
            data_dict=self.stitched_result.data,
            template_config=self._context["template_config"],
            engine_settings=self._context["engine_settings"],
            enable_timing=self._context.get("enable_timing", False),
        )

    def _ensure_stitched_run_result(self) -> "RunResult":
        """获取 stitched RunResult，不存在则按当前口径惰性构建。"""
        if self._stitched_run_result is None:
            self._stitched_run_result = self._build_stitched_run_result()
        return self._stitched_run_result

    @property
    def run_result(self) -> "RunResult":
        """获取 stitched 结果对应的 RunResult 代理。"""
        return self._ensure_stitched_run_result()

    @property
    def chart_config(self):
        """透传 stitched RunResult 的 chart_config。"""
        return self.run_result.chart_config

    @property
    def export_buffers(self):
        """透传 stitched RunResult 的导出 buffers。"""
        return self.run_result.export_buffers

    @property
    def export_zip_buffer(self):
        """透传 stitched RunResult 的 ZIP 导出缓存。"""
        return self.run_result.export_zip_buffer

    def format_for_export(self, config: "FormatResultsConfig") -> Self:
        """按显式配置格式化 stitched 结果，行为与 RunResult 保持一致。"""
        self.run_result.format_for_export(config)
        return self

    def save(self, config: "SaveConfig") -> Self:
        """透传 stitched RunResult 的保存能力。"""
        self.run_result.save(config)
        return self

    def upload(self, config: "UploadConfig") -> Self:
        """透传 stitched RunResult 的上传能力。"""
        self.run_result.upload(config)
        return self

    def log(self, level: LogLevel = LogLevel.BRIEF) -> None:
        """打印向前测试摘要日志。"""
        agg = self.aggregate_test_metrics
        occ = self._position_occupancy_days()
        if level == LogLevel.BRIEF:
            total_trades = agg.get("total_trades")
            span_days = self._stitched_span_days()
            span_months = (
                span_days / 30.4375
                if isinstance(span_days, (int, float)) and span_days > 0
                else None
            )
            trades_per_day = None
            days_per_trade = None
            if (
                isinstance(total_trades, (int, float))
                and total_trades > 0
                and span_days is not None
                and span_days > 0
            ):
                trades_per_day = float(total_trades) / span_days
                days_per_trade = span_days / float(total_trades)
            out = {
                "optimize_metric": str(self.optimize_metric),
                "total_return": agg.get("total_return"),
                "max_drawdown": agg.get("max_drawdown"),
                "calmar_ratio_raw": agg.get("calmar_ratio_raw"),
                "total_trades": total_trades,
                "stitched_span_days": span_days,
                "stitched_span_months": span_months,
                "trades_per_day": trades_per_day,
                "days_per_trade": days_per_trade,
                "avg_holding_days": occ.get("avg_holding_days"),
                "avg_empty_days": occ.get("avg_empty_days"),
                "max_empty_days": occ.get("max_empty_days"),
                "best_window_id": self.best_window_id,
                "worst_window_id": self.worst_window_id,
            }
            print(f"walk_forward.brief={out}")
            return

        windows = [
            {
                "window_id": w.window_id,
                "train_range": w.train_range,
                "transition_range": w.transition_range,
                "test_range": w.test_range,
                "has_cross_boundary_position": w.has_cross_boundary_position,
                "test_metrics": w.summary.performance or {},
            }
            for w in self.window_results
        ]
        out = {
            "optimize_metric": str(self.optimize_metric),
            "aggregate_test_metrics": agg,
            "best_window_id": self.best_window_id,
            "worst_window_id": self.worst_window_id,
            "stitched_time_range": self.stitched_time_range,
            "stitched_span_days": self._stitched_span_days(),
            "occupancy_days": occ,
            "next_window_hint": {
                "expected_train_start_time_ms": self.stitched_result.next_window_hint.expected_train_start_time_ms,
                "expected_transition_start_time_ms": self.stitched_result.next_window_hint.expected_transition_start_time_ms,
                "expected_test_start_time_ms": self.stitched_result.next_window_hint.expected_test_start_time_ms,
                "expected_test_end_time_ms": self.stitched_result.next_window_hint.expected_test_end_time_ms,
                "expected_window_ready_time_ms": self.stitched_result.next_window_hint.expected_window_ready_time_ms,
                "eta_days": self.stitched_result.next_window_hint.eta_days,
                "based_on_window_id": self.stitched_result.next_window_hint.based_on_window_id,
            },
            "windows": windows,
        }
        print(f"walk_forward.detailed={out}")

    def _stitched_span_days(self) -> float | None:
        """根据 stitched time_range 估算样本外跨度（天）。"""
        start, end = self._raw.stitched_result.time_range
        if not isinstance(start, int) or not isinstance(end, int):
            return None
        span_ms = end - start
        if span_ms <= 0:
            return None
        return span_ms / 86_400_000.0

    def _position_occupancy_days(self) -> dict[str, float | None]:
        """基于 stitched backtest 逐 bar 状态，计算持仓/空仓时长统计（天）。"""
        backtest_df = self.stitched_summary.backtest_result
        source = self.stitched_result.data.source
        base_key = self.stitched_result.data.base_data_key
        if (
            backtest_df is None
            or base_key not in source
            or "time" not in source[base_key].columns
            or backtest_df.height < 2
        ):
            return {
                "avg_holding_days": None,
                "avg_empty_days": None,
                "max_empty_days": None,
            }

        times = source[base_key]["time"].to_list()
        entry_long = backtest_df["entry_long_price"].to_list()
        exit_long = backtest_df["exit_long_price"].to_list()
        entry_short = backtest_df["entry_short_price"].to_list()
        exit_short = backtest_df["exit_short_price"].to_list()

        n = min(
            len(times),
            len(entry_long),
            len(exit_long),
            len(entry_short),
            len(exit_short),
        )
        if n < 2:
            return {
                "avg_holding_days": None,
                "avg_empty_days": None,
                "max_empty_days": None,
            }

        # 中文注释：计算每根 bar 对应的“下一根时间跨度”，最后一根用中位数补齐。
        deltas = [max(int(times[i + 1]) - int(times[i]), 0) for i in range(n - 1)]
        deltas_sorted = sorted([d for d in deltas if d > 0])
        fallback_delta = deltas_sorted[len(deltas_sorted) // 2] if deltas_sorted else 0
        deltas.append(fallback_delta)

        def _is_open(v: float | None) -> bool:
            return v is not None and v == v

        in_position = []
        for i in range(n):
            long_open = _is_open(entry_long[i]) and not _is_open(exit_long[i])
            short_open = _is_open(entry_short[i]) and not _is_open(exit_short[i])
            in_position.append(long_open or short_open)

        hold_segments: list[float] = []
        empty_segments: list[float] = []
        seg_sum = float(deltas[0])
        prev = in_position[0]
        for i in range(1, n):
            curr = in_position[i]
            if curr == prev:
                seg_sum += float(deltas[i])
                continue
            if prev:
                hold_segments.append(seg_sum)
            else:
                empty_segments.append(seg_sum)
            seg_sum = float(deltas[i])
            prev = curr

        if prev:
            hold_segments.append(seg_sum)
        else:
            empty_segments.append(seg_sum)

        ms_per_day = 86_400_000.0
        avg_holding_days = (
            (sum(hold_segments) / len(hold_segments)) / ms_per_day
            if hold_segments
            else None
        )
        avg_empty_days = (
            (sum(empty_segments) / len(empty_segments)) / ms_per_day
            if empty_segments
            else None
        )
        max_empty_days = (max(empty_segments) / ms_per_day) if empty_segments else None
        return {
            "avg_holding_days": avg_holding_days,
            "avg_empty_days": avg_empty_days,
            "max_empty_days": max_empty_days,
        }
