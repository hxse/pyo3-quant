import marimo

__generated_with = "0.19.11"
app = marimo.App(width="full")


@app.cell
def _():
    import sys
    from pathlib import Path

    # Jupyter Notebook 环境下的路径处理
    try:
        # 尝试使用 __file__ (在脚本环境中)
        root_path = next(
            (
                p
                for p in Path(__file__).resolve().parents
                if (p / "pyproject.toml").is_file()
            ),
            None,
        )
    except NameError:
        # 在 Notebook/交互环境中，使用当前工作目录
        current_dir = Path.cwd()
        root_path = next(
            (
                p
                for p in [current_dir] + list(current_dir.parents)
                if (p / "pyproject.toml").is_file()
            ),
            None,
        )

    if root_path and str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))
    return


@app.cell
def _():
    from py_entry.private_strategies.live.base import LiveStrategyConfig
    from py_entry.runner import Backtest, FormatResultsConfig, RunResult
    from py_entry.strategies.base import StrategyConfig

    def normalize_strategy_config(
        cfg_like: StrategyConfig | LiveStrategyConfig,
    ) -> StrategyConfig:
        """兼容 StrategyConfig / LiveStrategyConfig 两种返回类型。"""
        if isinstance(cfg_like, LiveStrategyConfig):
            return cfg_like.strategy
        if isinstance(cfg_like, StrategyConfig):
            return cfg_like
        raise TypeError(f"不支持的策略配置类型: {type(cfg_like)}")

    def run_from_config(cfg_like: StrategyConfig | LiveStrategyConfig) -> RunResult:
        """从统一配置对象执行回测。"""
        cfg = normalize_strategy_config(cfg_like)
        bt = Backtest(
            data_source=cfg.data_config,
            indicators=cfg.indicators_params,
            signal=cfg.signal_params,
            backtest=cfg.backtest_params,
            signal_template=cfg.signal_template,
            engine_settings=cfg.engine_settings,
            performance=cfg.performance_params,
        )
        result = bt.run()
        return result.format_for_export(FormatResultsConfig(dataframe_format="csv"))

    return (run_from_config,)


@app.cell
def _(run_from_config):
    from py_entry.example.custom_backtest import get_custom_backtest_config
    from py_entry.example.real_data_backtest import get_real_data_backtest_config
    from py_entry.example.reversal_extreme_backtest import get_reversal_extreme_config

    strategy_configs = {
        "mtf_bbands_rsi_sma": get_custom_backtest_config,
        "real_data_backtest": get_real_data_backtest_config,
        "reversal_extreme": get_reversal_extreme_config,
    }

    STRATEGY = "mtf_bbands_rsi_sma"
    STRATEGY = "real_data_backtest"
    STRATEGY = "reversal_extreme"

    if STRATEGY not in strategy_configs:
        raise ValueError(f"未知策略: {STRATEGY}, 可选: {list(strategy_configs)}")

    cfg = strategy_configs[STRATEGY]()
    result = run_from_config(cfg)
    assert result, f"result 不存在, {result}"
    print(f"运行策略: {STRATEGY}")
    return (result,)


@app.cell
def _(result):
    print(f"Performance: {result.summary.performance}")
    return


@app.cell
def _(result):
    from py_entry.io import DashboardOverride, DisplayConfig

    config = DisplayConfig(
        embed_data=False,
        target="marimo",
        width="100%",
        aspect_ratio="16/9",
        override=DashboardOverride(
            show=["0,0,0,1"],
            showInLegend=["0,0,0,1"],
            showRiskLegend="1,1,1,1",
            showLegendInAll=True,
        ).to_dict(),
    )

    result.display(config=config)
    return


if __name__ == "__main__":
    app.run()
