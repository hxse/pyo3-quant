import time
import polars as pl

from py_entry.data_conversion.backtest_runner import (
    BacktestRunner,
    DefaultDataBuilder,
    DefaultParamBuilder,
    DefaultEngineSettingsBuilder,
    SettingContainer,
    ExecutionStage,
    DefaultSignalTemplateBuilder,
)
from py_entry.data_conversion.input import (
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    SignalTemplate,
    Param,
)

from py_entry.data_conversion.helpers import (
    signal_data_vs_data,
    signal_data_vs_param,
)

from py_entry.data_conversion.input import (
    SignalTemplate,
    CompareOp,
    LogicOp,
    SignalGroup,
)

import pyo3_quant


from loguru import logger

# ==============================================================================
# 自定义 Builder 类
# ==============================================================================


class CustomParamBuilder(DefaultParamBuilder):
    """
    自定义参数构建器。
    用户可以通过覆盖此类的特定方法来定制回测参数。
    如果某个方法未被覆盖，将使用父类 DefaultParamBuilder 的默认实现。
    """

    def build_indicators_params(self, period_count: int) -> IndicatorsParams:
        """
        构建指标参数。
        用户可以通过取消注释并实现此方法来自定义指标参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_indicators_params(period_count)
        sma_0 = {
            "period": Param.create(8),
        }
        sma_1 = {
            "period": Param.create(16),
        }
        rsi_0 = {
            "period": Param.create(14),
        }
        bbands_0 = {
            "period": Param.create(14),
            "std": Param.create(2),
        }
        indicators_0 = {
            "bbands_0": bbands_0,
        }
        indicators_1 = {
            "rsi_0": rsi_0,
        }
        indicators_2 = {
            "sma_0": sma_0,
            "sma_1": sma_1,
        }

        return {
            "ohlcv": [
                indicators_0,
                indicators_1,
                indicators_2,
                *([{}] * period_count),
            ][:period_count]
        }

    def build_signal_params(self) -> SignalParams:
        """
        构建信号参数。
        用户可以通过取消注释并实现此方法来自定义信号参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_signal_params()
        return {"rsi_midline": Param.create(20, 10, 90, 5)}

    def build_backtest_params(self) -> BacktestParams:
        """
        构建回测参数。
        用户可以通过取消注释并实现此方法来自定义回测参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        return super().build_backtest_params()

    def build_performance_params(self) -> PerformanceParams:
        """
        构建性能参数。
        用户可以通过取消注释并实现此方法来自定义性能参数。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        return super().build_performance_params()


class CustomSignalTemplateBuilder(DefaultSignalTemplateBuilder):
    """
    自定义信号模板构建器。
    用户可以通过覆盖此类的特定方法来定制信号模板。
    如果某个方法未被覆盖，将使用父类 DefaultSignalTemplateBuilder 的默认实现。
    """

    def build_signal_template_instance(self) -> SignalTemplate:
        """
        构建信号模板实例。
        用户可以通过取消注释并实现此方法来自定义信号模板实例。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_signal_template_instance()

        enter_long_group = SignalGroup(
            logic=LogicOp.AND,
            conditions=[
                signal_data_vs_data(
                    compare=CompareOp.GT,
                    a_name="sma_0",
                    a_source="ohlcv_2",
                    a_offset=0,
                    b_name="sma_1",
                    b_source="ohlcv_2",
                    b_offset=0,
                ),
                signal_data_vs_param(
                    compare=CompareOp.GT,
                    a_name="rsi_0",
                    a_source="ohlcv_1",
                    a_offset=0,
                    b_param="rsi_midline",
                ),
                signal_data_vs_data(
                    compare=CompareOp.CGT,
                    a_name="close",
                    a_source="ohlcv_0",
                    a_offset=0,
                    b_name="bbands_0_upper",
                    b_source="ohlcv_0",
                    b_offset=0,
                ),
            ],
        )

        return SignalTemplate(
            name="multi_timeframe_dynamic_strategy", enter_long=[enter_long_group]
        )


class CustomEngineSettingsBuilder(DefaultEngineSettingsBuilder):
    """
    自定义引擎设置构建器。
    用户可以通过覆盖此类的特定方法来定制引擎设置。
    如果某个方法未被覆盖，将使用父类 DefaultEngineSettingsBuilder 的默认实现。
    """

    def build_engine_settings(self) -> SettingContainer:
        """
        构建引擎设置。
        用户可以通过取消注释并实现此方法来自定义引擎设置。
        如果不覆盖此方法，将使用父类的默认实现。
        """
        # return super().build_engine_settings()

        return SettingContainer(
            # execution_stage=ExecutionStage.INDICATOR,
            execution_stage=ExecutionStage.PERFORMANCE,
            return_only_final=False,
        )


if __name__ == "__main__":
    print("-" * 30)
    start_time = time.perf_counter()
    res = pyo3_quant.minimal_working_example.sum_as_string(5, 25)
    print("sum_as_string:", res)
    print("耗时", time.perf_counter() - start_time)

    print("-" * 30)
    start_time = time.perf_counter()

    br = BacktestRunner()

    backtest_result = (
        br.with_data(
            {
                "timeframes": ["15m", "1h", "4h"],
                "start_time": 1735689600000,
                "num_bars": 200,
                "fixed_seed": False,
            },
            data_builder=DefaultDataBuilder(),
        )
        .with_param_set(param_builder=CustomParamBuilder())
        .with_templates(
            signal_template_builder=CustomSignalTemplateBuilder(),
        )
        .with_engine_settings(engine_settings_builder=CustomEngineSettingsBuilder())
        .run()
    )

    print(backtest_result)
    logger.info(f"performance: {backtest_result[0].performance}")

    logger.info(f"耗时 {time.perf_counter() - start_time}")

    # ==============================================================================
    # 回测结果验证
    # ==============================================================================

    # 导入验证模块
    from .validators import validate_backtest_result, get_backtest_summary

    # 检查回测结果是否存在
    if (
        backtest_result
        and len(backtest_result) > 0
        and hasattr(backtest_result[0], "backtest_result")
        and backtest_result[0].backtest_result is not None
    ):
        print("\n" + "=" * 60)
        print("开始验证回测结果...")

        # 获取回测结果DataFrame
        backtest_df = backtest_result[0].backtest_result

        # 执行验证
        validation_result = validate_backtest_result(backtest_df)

        # 显示验证结果
        validation_result.print_report()

        # 获取并显示摘要信息
        if validation_result.is_valid:
            summary = get_backtest_summary(backtest_df)
            print(f"\n📊 回测结果摘要:")
            print(f"   总行数: {summary['basic_info']['total_rows']}")
            print(f"   列数: {len(summary['basic_info']['columns'])}")

            # 显示关键财务指标
            if "financial_stats" in summary:
                stats = summary["financial_stats"]
                if "equity" in stats:
                    final_equity = stats["equity"]["final"]
                    print(f"   最终净值: {final_equity:.4f}")
                if "balance" in stats:
                    final_balance = stats["balance"]["final"]
                    print(f"   最终余额: {final_balance:.4f}")

            # 显示仓位统计
            if "position_stats" in summary:
                pos_stats = summary["position_stats"]
                print(f"   仓位状态分布:")
                # 使用 Polars DataFrame 直接打印，避免 for 循环
                pos_df = pl.DataFrame({
                    "state": list(pos_stats.keys()),
                    "count": list(pos_stats.values())
                })
                print(pos_df)
        else:
            print("\n⚠️  验证失败，建议检查回测逻辑!")
    else:
        print("\n⚠️  未找到可验证的回测结果数据")
    print("=" * 60)
