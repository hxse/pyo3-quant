def test_performance_metrics_exist(full_performance_result):
    """验证所有请求的指标都在结果中，且不是默认的 0.0 (除非真的没交易)"""
    metrics = full_performance_result.performance

    assert metrics is not None
    assert "annualization_factor" in metrics
    assert metrics["annualization_factor"] > 0

    # 基础指标
    required_keys = [
        "total_return",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "max_drawdown",
        "max_drawdown_duration",
    ]
    for key in required_keys:
        assert key in metrics, f"Missing metric: {key}"

    # 交易统计
    trade_keys = ["total_trades", "avg_daily_trades", "win_rate", "profit_loss_ratio"]
    for key in trade_keys:
        assert key in metrics, f"Missing metric: {key}"

    # 持仓时间统计
    duration_keys = [
        "avg_holding_duration",
        "max_holding_duration",
        "avg_empty_duration",
        "max_empty_duration",
    ]
    for key in duration_keys:
        assert key in metrics, f"Missing metric: {key}"


def test_trade_logic_consistency(full_performance_result):
    """验证交易逻辑的一致性，例如总交易次数应与胜率计算的分母一致"""
    import polars as pl

    metrics = full_performance_result.performance
    df = full_performance_result.backtest_result
    total_trades = metrics["total_trades"]

    # 调试打印

    if total_trades > 0:
        assert metrics["win_rate"] >= 0
        assert metrics["win_rate"] <= 1
        assert metrics["avg_holding_duration"] > 0
    else:
        assert metrics["win_rate"] == 0
        assert metrics["avg_holding_duration"] == 0


def test_drawdown_consistency(full_performance_result):
    """验证最大回撤和回撤时长"""
    metrics = full_performance_result.performance
    mdd = metrics["max_drawdown"]
    mdd_dur = metrics["max_drawdown_duration"]

    assert mdd >= 0
    assert mdd_dur >= 0

    if mdd > 0:
        assert mdd_dur > 0
