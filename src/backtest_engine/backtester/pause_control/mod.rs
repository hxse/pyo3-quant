pub mod drawdown_pause;
pub mod ema_pause;
pub mod sma_pause;
pub mod utils;

use crate::data_conversion::BacktestParams;
use crate::error::QuantError;
use drawdown_pause::drawdown_pause_signals;
use ema_pause::pause_ema_signals;
use polars::prelude::*;
use sma_pause::pause_sma_signals;

/// 根据暂停参数选择相应的暂停控制函数
///
/// 按优先级检查暂停参数：pause_resume > pause_sma > pause_ema
/// 只使用第一个有效的暂停参数
pub fn apply_pause_control(
    equity_df: &DataFrame,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<Option<(DataFrame, Series)>, QuantError> {
    // 使用match语句按优先级检查暂停参数
    match (
        backtest_params.pause_drawdown.value > 0.0,
        backtest_params.pause_sma.value > 0.0,
        backtest_params.pause_ema.value > 0.0,
    ) {
        (true, _, _) => {
            // pause_resume有效，使用回撤暂停控制
            Ok(Some(drawdown_pause_signals(
                equity_df,
                signals_df,
                backtest_params,
            )?))
        }
        (_, true, _) => {
            // pause_sma有效，使用SMA暂停控制
            Ok(Some(pause_sma_signals(
                equity_df,
                signals_df,
                backtest_params,
            )?))
        }
        (_, _, true) => {
            // pause_ema有效，使用EMA暂停控制
            Ok(Some(pause_ema_signals(
                equity_df,
                signals_df,
                backtest_params,
            )?))
        }
        _ => {
            // 所有暂停参数都无效，返回None
            Ok(None)
        }
    }
}
