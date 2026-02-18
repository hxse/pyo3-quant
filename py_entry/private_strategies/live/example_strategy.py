"""
research 示例策略。

设计目标：
1. ipynb 分阶段调用（可视化每个阶段结果）；
2. CLI 在 __main__ 下走顺序管道（默认执行全部阶段）。
"""

import time

from py_entry.constants import GLOBAL_SEED
from py_entry.data_generator import OhlcvDataFetchConfig
from py_entry.data_generator.time_utils import get_utc_timestamp_ms
from py_entry.io import load_local_config
from py_entry.private_strategies import stage_tools as st
from py_entry.private_strategies.live import register_live_strategy
from py_entry.private_strategies.live.base import LiveStrategyConfig
from py_entry.runner import RunResult
from py_entry.strategies.base import StrategyConfig
from py_entry.types import (
    BacktestParams,
    ExecutionStage,
    LogicOp,
    OptimizeMetric,
    OptimizerConfig,
    Param,
    SensitivityConfig,
    SettingContainer,
    SignalGroup,
    SignalTemplate,
    WalkForwardConfig,
)

BASE_DATA_KEY = "ohlcv_15m"

# 中文注释：阈值仅用于摘要审阅，不介入执行流程。
RUNTIME_THRESHOLDS = {
    "min_window_count": 1,  # 向前测试最少窗口数阈值
    "max_drawdown_warn": 0.30,  # 最大回撤预警阈值
    "calmar_ratio_raw_warn": 0.0,  # 非年化卡尔马预警阈值
}


@register_live_strategy("btc_sma15_live")
def get_live_config() -> LiveStrategyConfig:
    """返回 research/live 可复用的策略配置。"""
    request_config = load_local_config()
    real_data_config = OhlcvDataFetchConfig(
        config=request_config,  # 本地数据服务配置
        exchange_name="binance",  # 交易所
        market="future",  # 市场类型
        symbol="BTC/USDT",  # 交易品种
        timeframes=["15m"],  # 使用的时间周期
        since=get_utc_timestamp_ms("2025-12-01 00:00:00"),  # 数据起始时间
        limit=20000,  # 拉取 K 线数量
        enable_cache=True,  # 开启请求缓存
        mode="live",  # 数据模式（实时接口）
        base_data_key=BASE_DATA_KEY,  # 主时间周期键
    )

    indicators = {
        BASE_DATA_KEY: {
            "sma_fast": {"period": Param(8, min=5, max=20, step=1.0, optimize=True)},
            # 快线周期：默认 8，优化区间 5~20，步长 1
            "sma_slow": {"period": Param(21, min=15, max=60, step=1.0, optimize=True)},
            # 慢线周期：默认 21，优化区间 15~60，步长 1
        }
    }

    signal_template = SignalTemplate(
        entry_long=SignalGroup(
            logic=LogicOp.AND,  # 多头入场条件逻辑
            comparisons=[
                f"sma_fast, {BASE_DATA_KEY}, 0 x> sma_slow, {BASE_DATA_KEY}, 0"
            ],
            # 多头入场：快线上穿慢线
        ),
        entry_short=SignalGroup(
            logic=LogicOp.AND,  # 空头入场条件逻辑
            comparisons=[
                f"sma_fast, {BASE_DATA_KEY}, 0 x< sma_slow, {BASE_DATA_KEY}, 0"
            ],
            # 空头入场：快线下穿慢线
        ),
        exit_long=SignalGroup(
            logic=LogicOp.AND,  # 多头离场条件逻辑
            comparisons=[
                f"sma_fast, {BASE_DATA_KEY}, 0 x< sma_slow, {BASE_DATA_KEY}, 0"
            ],
            # 多头离场：快线下穿慢线
        ),
        exit_short=SignalGroup(
            logic=LogicOp.AND,  # 空头离场条件逻辑
            comparisons=[
                f"sma_fast, {BASE_DATA_KEY}, 0 x> sma_slow, {BASE_DATA_KEY}, 0"
            ],
            # 空头离场：快线上穿慢线
        ),
    )

    backtest_params = BacktestParams(
        initial_capital=10000.0,  # 初始资金
        fee_fixed=0.0,  # 固定手续费
        fee_pct=0.001,  # 比例手续费
        sl_exit_in_bar=False,  # 止损是否同 K 内离场
        tp_exit_in_bar=False,  # 止盈是否同 K 内离场
        sl_trigger_mode=False,  # 止损触发模式
        tp_trigger_mode=False,  # 止盈触发模式
        tsl_trigger_mode=False,  # 跟踪止损触发模式
        sl_anchor_mode=False,  # 止损锚点模式
        tp_anchor_mode=False,  # 止盈锚点模式
        tsl_anchor_mode=False,  # 跟踪止损锚点模式
        sl_pct=Param(0.01, min=0.003, max=0.03, step=0.001, optimize=True),
        # 百分比止损：默认 1%，优化区间 0.3%~3%
        tp_pct=Param(0.02, min=0.005, max=0.08, step=0.001, optimize=True),
        # 百分比止盈：默认 2%，优化区间 0.5%~8%
        tsl_pct=Param(0.01, min=0.003, max=0.03, step=0.001, optimize=True),
        # 百分比跟踪止损：默认 1%，优化区间 0.3%~3%
    )

    strategy = StrategyConfig(
        name="btc_sma15_live",  # 策略唯一名称
        description="BTC 15m SMA 交叉 research 模板策略",  # 策略描述
        data_config=real_data_config,  # 数据源配置
        indicators_params=indicators,  # 指标参数配置
        signal_params={},  # 额外信号参数（当前无）
        backtest_params=backtest_params,  # 回测参数配置
        signal_template=signal_template,  # 信号模板配置
        engine_settings=SettingContainer(
            execution_stage=ExecutionStage.Performance,  # 执行到绩效阶段
            return_only_final=False,  # 保留完整中间结果
        ),
    )
    return LiveStrategyConfig(
        strategy=strategy,  # 绑定策略对象
        enabled=False,  # 默认不启用自动实盘执行
        base_data_key=BASE_DATA_KEY,  # 主周期键
        symbol="BTC/USDT",  # 交易品种
        exchange_name="binance",  # 交易所
        market="future",  # 市场类型
        mode="live",  # 运行模式
        position_size_pct=0.2,  # 仓位比例
        leverage=2,  # 杠杆倍数
        settlement_currency="USDT",  # 结算币种
    )


# 中文注释：阶段配置集中定义，避免阶段函数与管道函数重复写参数。
def build_opt_cfg() -> OptimizerConfig:
    return OptimizerConfig(
        min_samples=500,  # 最小采样数（达到后才允许提前停止）
        max_samples=1200,  # 最大采样数（优化预算上限）
        samples_per_round=50,  # 每轮采样数
        stop_patience=6,  # 提前停止耐心轮数
        optimize_metric=OptimizeMetric.CalmarRatioRaw,  # 优化目标指标
        seed=GLOBAL_SEED,  # 优化随机种子
    )


def build_sens_cfg() -> SensitivityConfig:
    return SensitivityConfig(
        jitter_ratio=0.1,  # 参数抖动比例
        n_samples=30,  # 抖动样本数量
        distribution="normal",  # 抖动分布类型
        metric=OptimizeMetric.CalmarRatioRaw,  # 评估指标
        seed=GLOBAL_SEED,  # 敏感性测试随机种子
    )


def build_wf_cfg() -> WalkForwardConfig:
    return WalkForwardConfig(
        train_ratio=0.5,  # 训练窗口比例
        transition_ratio=0.1,  # 过渡窗口比例
        test_ratio=0.25,  # 测试窗口比例
        optimizer_config=OptimizerConfig(
            min_samples=200,  # WF 每窗口最小采样数
            max_samples=600,  # WF 每窗口最大采样数
            samples_per_round=50,  # WF 每窗口每轮采样数
            stop_patience=4,  # WF 每窗口提前停止耐心轮数
            optimize_metric=OptimizeMetric.CalmarRatioRaw,  # WF 每窗口优化目标
            seed=GLOBAL_SEED,  # WF 每窗口优化随机种子
        ),
    )


def run_backtest_stage(config: LiveStrategyConfig) -> RunResult:
    """阶段1：基础回测。"""
    return st.run_backtest_stage(config)


def run_optimization_stage(config: LiveStrategyConfig):
    """阶段2：全局优化。"""
    return st.run_optimization_stage(config, build_opt_cfg())


def run_sensitivity_stage(config: LiveStrategyConfig):
    """阶段3：参数抖动敏感性测试。"""
    return st.run_sensitivity_stage(config, build_sens_cfg())


def run_walk_forward_stage(config: LiveStrategyConfig):
    """阶段4：向前测试。"""
    return st.run_walk_forward_stage(config, build_wf_cfg())


def run_research_pipeline(config: LiveStrategyConfig) -> dict[str, object]:
    """CLI 顺序管道：按阶段自动执行。"""
    return st.run_pipeline(
        config,
        base_data_key=BASE_DATA_KEY,
        opt_cfg=build_opt_cfg(),
        sens_cfg=build_sens_cfg(),
        wf_cfg=build_wf_cfg(),
    )


def format_pipeline_summary_for_ai(
    summary: dict[str, object], elapsed_seconds: float
) -> str:
    """输出给 AI 的结构化摘要。"""
    return st.format_pipeline_summary_for_ai(
        summary,
        elapsed_seconds,
        runtime_config={
            "symbol": "BTC/USDT",
            "base_data_key": BASE_DATA_KEY,
            "mode": "live",
            "since": get_utc_timestamp_ms("2025-12-01 00:00:00"),
            "limit": 20000,
            "optimize_metric": str(OptimizeMetric.CalmarRatioRaw),
            "optimize_min_samples": 500,
            "optimize_max_samples": 1200,
            "optimize_samples_per_round": 50,
            "optimize_stop_patience": 6,
            "optimize_seed": GLOBAL_SEED,
            "wf_train_ratio": 0.5,
            "wf_transition_ratio": 0.1,
            "wf_test_ratio": 0.25,
            "wf_optimize_min_samples": 200,
            "wf_optimize_max_samples": 600,
            "wf_optimize_samples_per_round": 50,
            "wf_optimize_stop_patience": 4,
            "wf_optimize_seed": GLOBAL_SEED,
        },
        runtime_thresholds=RUNTIME_THRESHOLDS,
    )


if __name__ == "__main__":
    # CLI 入口：AI 直接顺序执行完整管道并查看结构化摘要。
    start_time = time.perf_counter()
    live_cfg = get_live_config()
    pipeline_summary = run_research_pipeline(live_cfg)
    elapsed_seconds = time.perf_counter() - start_time
    print(format_pipeline_summary_for_ai(pipeline_summary, elapsed_seconds))
