"""
回测引擎相关性测试

对比 pyo3-quant 和 backtesting.py 两个引擎的回测结果
"""

import pytest

from py_entry.Test.backtest.correlation_analysis.adapters.pyo3_adapter import (
    Pyo3Adapter,
)
from py_entry.Test.backtest.correlation_analysis.adapters.backtestingpy_adapter import (
    BacktestingPyAdapter,
)
from py_entry.Test.backtest.correlation_analysis.data_utils import (
    generate_ohlcv_for_backtestingpy,
)
from py_entry.Test.backtest.correlation_analysis.analysis.correlation import (
    analyze_correlation,
)


from py_entry.Test.backtest.strategies import get_all_strategies
from py_entry.Test.backtest.correlation_analysis.config import CommonConfig


class TestEngineCorrelation:
    """回测引擎相关性测试"""

    @pytest.mark.parametrize(
        "strategy_config",
        [s for s in get_all_strategies() if s.btp_strategy_class is not None],
        ids=lambda s: s.name,
    )
    def test_strategy_correlation(self, strategy_config):
        """测试策略的相关性"""
        strategy_name = strategy_config.name
        btp_class = strategy_config.btp_strategy_class

        print("\n" + "=" * 60)
        print(f"开始策略相关性分析: {strategy_name}")
        print("=" * 60)

        # 直接从策略配置构建 CommonConfig（唯一配置来源）
        data_cfg = strategy_config.data_config
        backtest_cfg = strategy_config.backtest_params

        config = CommonConfig(
            bars=data_cfg.num_bars or 6000,
            seed=data_cfg.fixed_seed if data_cfg.fixed_seed is not None else 42,
            initial_capital=backtest_cfg.initial_capital or 10000.0,
            commission=backtest_cfg.fee_pct or 0.0005,
            timeframe=data_cfg.timeframes[0] if data_cfg.timeframes else "15m",
            start_time=data_cfg.start_time or 1735689600000,
            allow_gaps=getattr(data_cfg, "allow_gaps", False),
            equity_cutoff_ratio=(
                strategy_config.custom_params.get("equity_cutoff_ratio", 0.20)
                if strategy_config.custom_params
                else 0.20
            ),
        )

        # 1. 运行 pyo3-quant 引擎
        print(f"\n[1/3] 运行 pyo3-quant 引擎 ({strategy_name})...")
        pyo3_adapter = Pyo3Adapter(config)
        pyo3_adapter.run(strategy_name)

        pyo3_equity = pyo3_adapter.get_equity_curve()
        pyo3_drawdown = pyo3_adapter.get_drawdown_curve()
        pyo3_total_return = pyo3_adapter.get_total_return_pct()
        pyo3_trade_count = pyo3_adapter.get_trade_count()
        pyo3_win_rate = pyo3_adapter.get_win_rate()

        print(f"  ✓ pyo3-quant 完成，数据长度: {len(pyo3_equity)}")

        # 2. 生成共享 OHLCV 数据并运行 backtesting.py 引擎
        print(f"\n[2/3] 运行 backtesting.py 引擎 ({strategy_name})...")
        ohlcv_df = generate_ohlcv_for_backtestingpy(config)

        btp_adapter = BacktestingPyAdapter(config)
        btp_adapter.run(ohlcv_df, btp_class)

        btp_equity = btp_adapter.get_equity_curve()
        btp_drawdown = btp_adapter.get_drawdown_curve()
        btp_total_return = btp_adapter.get_total_return_pct()
        btp_trade_count = btp_adapter.get_trade_count()
        btp_win_rate = btp_adapter.get_win_rate()

        print(f"  ✓ backtesting.py 完成，数据长度: {len(btp_equity)}")

        # 2.5 验证数据一致性
        print("\n[2.5/3] 验证 OHLC 数据一致性...")
        # 从 Pyo3 runner 获取原始数据
        pyo3_ohlc = None
        if pyo3_adapter.runner and pyo3_adapter.runner.data_dict:
            base_key = f"ohlcv_{config.timeframe}"
            if base_key in pyo3_adapter.runner.data_dict.source:
                pyo3_source = pyo3_adapter.runner.data_dict.source[base_key]
                pyo3_ohlc = {
                    "open": pyo3_source["open"].to_numpy(),
                    "high": pyo3_source["high"].to_numpy(),
                    "low": pyo3_source["low"].to_numpy(),
                    "close": pyo3_source["close"].to_numpy(),
                }

        if pyo3_ohlc:
            import numpy as np

            btp_ohlc = {
                "open": ohlcv_df["Open"].values,
                "high": ohlcv_df["High"].values,
                "low": ohlcv_df["Low"].values,
                "close": ohlcv_df["Close"].values,
            }

            # 向量化匹配全部 OHLC 数据
            all_match = True
            mismatch_info = []
            for col in ["open", "high", "low", "close"]:
                diff = np.abs(pyo3_ohlc[col] - btp_ohlc[col])
                if not np.all(diff < 0.0001):
                    all_match = False
                    mismatch_count = np.sum(diff >= 0.0001)
                    mismatch_info.append(f"{col}: {mismatch_count} 条不匹配")

            if all_match:
                print(f"  ✓ OHLC 数据一致 (全部 {len(pyo3_ohlc['open'])} 条匹配)")
            else:
                print(f"  ❌ OHLC 数据不一致! {', '.join(mismatch_info)}")
                assert False, "OHLC 数据不一致，无法进行相关性对比"
        else:
            print("  ⚠ 无法获取 Pyo3 OHLC 数据，跳过验证")

        # 3. 分析相关性
        print("\n[3/3] 分析相关性...")
        result = analyze_correlation(
            pyo3_equity=pyo3_equity,
            pyo3_drawdown=pyo3_drawdown,
            pyo3_total_return_pct=pyo3_total_return,
            pyo3_trade_count=pyo3_trade_count,
            pyo3_win_rate=pyo3_win_rate,
            btp_equity=btp_equity,
            btp_drawdown=btp_drawdown,
            btp_total_return_pct=btp_total_return,
            btp_trade_count=btp_trade_count,
            btp_win_rate=btp_win_rate,
            initial_capital=config.initial_capital,
            equity_cutoff_ratio=config.equity_cutoff_ratio,
        )

        print("\n" + "=" * 60)
        print(result)
        print("=" * 60)

        # 4. 断言
        assert result.equity_r > 0.85, f"equity 相关性不足: {result.equity_r:.6f}"
        assert result.drawdown_r > 0.85, f"drawdown 相关性不足: {result.drawdown_r:.6f}"
        # 总回报率差异应小于 20.0% (现状: ~16.8% under 1000 bars)
        assert result.total_return_diff < 20.0, (
            f"总回报率差异过大: {result.total_return_diff:.4f}%"
        )
        # 最大回撤差异应小于 15% (现状: ~12.5%)
        assert result.max_drawdown_diff < 15.0, (
            f"最大回撤差异过大: {result.max_drawdown_diff:.4f}%"
        )

        print(f"\n✅ 策略 {strategy_name} 相关性检查通过！")


if __name__ == "__main__":
    # 允许直接运行测试
    pytest.main([__file__, "-v", "-s"])
