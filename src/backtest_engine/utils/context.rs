use crate::backtest_engine::{
    backtester, indicators, performance_analyzer, signal_generator, utils,
};
use crate::error::QuantError;
use crate::types::ExecutionStage;
use crate::types::SignalTemplate;
use crate::types::{
    BacktestParams, DataContainer, IndicatorsParams, PerformanceParams, SignalParams,
};
use crate::types::{BacktestSummary, IndicatorResults, PerformanceMetrics};
use polars::prelude::DataFrame;

/// 回测执行上下文：持有所有阶段的中间结果
/// 采用状态机模式，每个执行阶段都是对 Context 的一次转换
pub struct BacktestContext {
    pub indicator_dfs: Option<IndicatorResults>,
    pub signals_df: Option<DataFrame>,
    pub backtest_df: Option<DataFrame>,
    pub performance: Option<PerformanceMetrics>,
}

impl BacktestContext {
    /// 创建空的回测上下文
    pub fn new() -> Self {
        Self {
            indicator_dfs: None,
            signals_df: None,
            backtest_df: None,
            performance: None,
        }
    }

    /// 执行技术指标计算阶段
    pub fn execute_indicator_if_needed(
        &mut self,
        target_stage: ExecutionStage,
        data: &DataContainer,
        params: &IndicatorsParams,
    ) -> Result<(), QuantError> {
        if target_stage >= ExecutionStage::Indicator {
            self.indicator_dfs = Some(indicators::calculate_indicators(data, params)?);
        }
        Ok(())
    }

    /// 执行信号生成阶段
    pub fn execute_signals_if_needed(
        &mut self,
        target_stage: ExecutionStage,
        return_only_final: bool,
        data: &DataContainer,
        signal_params: &SignalParams,
        signal_template: &SignalTemplate,
    ) -> Result<(), QuantError> {
        if target_stage >= ExecutionStage::Signals {
            if let Some(ref ind_dfs) = self.indicator_dfs {
                let df = signal_generator::generate_signals(
                    data,
                    ind_dfs,
                    signal_params,
                    signal_template,
                )?;
                self.signals_df = Some(df);

                // 在 return_only_final 模式下，信号计算完成后释放指标数据
                utils::maybe_release_indicators(return_only_final, &mut self.indicator_dfs);
            }
        }
        Ok(())
    }

    /// 执行回测阶段
    pub fn execute_backtest_if_needed(
        &mut self,
        target_stage: ExecutionStage,
        return_only_final: bool,
        data: &DataContainer,
        backtest_params: &BacktestParams,
    ) -> Result<(), QuantError> {
        if target_stage >= ExecutionStage::Backtest {
            if let Some(ref sig_df) = self.signals_df {
                let df = backtester::run_backtest(data, sig_df, backtest_params)?;
                self.backtest_df = Some(df);

                // 在 return_only_final 模式下，回测完成后释放信号数据
                utils::maybe_release_signals(return_only_final, &mut self.signals_df);
            }
        }
        Ok(())
    }

    /// 执行绩效分析阶段
    pub fn execute_performance_if_needed(
        &mut self,
        target_stage: ExecutionStage,
        return_only_final: bool,
        data: &DataContainer,
        performance_params: &PerformanceParams,
    ) -> Result<(), QuantError> {
        if target_stage >= ExecutionStage::Performance {
            if let Some(ref bt_df) = self.backtest_df {
                let metrics =
                    performance_analyzer::analyze_performance(data, bt_df, performance_params)?;
                self.performance = Some(metrics);

                // 在 return_only_final 模式下，绩效分析完成后释放回测结果
                utils::maybe_release_backtest(return_only_final, &mut self.backtest_df);
            }
        }
        Ok(())
    }

    /// 转换为最终的 BacktestSummary
    pub fn into_summary(
        self,
        return_only_final: bool,
        stop_stage: ExecutionStage,
    ) -> BacktestSummary {
        utils::create_backtest_summary(
            return_only_final,
            stop_stage,
            self.indicator_dfs,
            self.signals_df,
            self.backtest_df,
            self.performance,
        )
    }
}
