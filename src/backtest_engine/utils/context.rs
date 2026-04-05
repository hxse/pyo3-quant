use crate::backtest_engine::data_ops::build_result_pack;
use crate::backtest_engine::{backtester, utils};
use crate::error::QuantError;
use crate::types::ExecutionStage;
use crate::types::{BacktestParams, DataPack, IndicatorResults, PerformanceMetrics, ResultPack};
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

    /// 执行回测阶段
    pub fn execute_backtest_if_needed(
        &mut self,
        target_stage: ExecutionStage,
        return_only_final: bool,
        data: &DataPack,
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

    /// 转换为阶段结果对象
    pub fn into_result_pack(
        self,
        data: &DataPack,
        return_only_final: bool,
        stop_stage: ExecutionStage,
    ) -> Result<ResultPack, QuantError> {
        let indicators = if return_only_final && stop_stage >= ExecutionStage::Signals {
            None
        } else {
            self.indicator_dfs
        };
        let signals = if return_only_final && stop_stage >= ExecutionStage::Backtest {
            None
        } else {
            self.signals_df
        };
        let backtest = if return_only_final && stop_stage >= ExecutionStage::Performance {
            None
        } else {
            self.backtest_df
        };
        build_result_pack(data, indicators, signals, backtest, self.performance)
    }
}
