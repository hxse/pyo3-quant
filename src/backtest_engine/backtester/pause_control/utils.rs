use crate::backtest_engine::utils::column_names::ColumnName;
use crate::{
    data_conversion::BacktestParams,
    error::{backtest_error::BacktestError, QuantError},
};
use polars::prelude::*;

/// 检查信号DataFrame是否只包含信号列
///
/// # 参数
/// * `signals_df` - 信号DataFrame
/// * `context` - 错误上下文信息
///
/// # 返回
/// * `Result<(), QuantError>` - 如果缺少列则返回错误，否则成功
pub fn check_signal_only_columns(signals_df: &DataFrame, context: &str) -> Result<(), QuantError> {
    let required_columns = [
        ColumnName::EnterLong.as_str(),
        ColumnName::EnterShort.as_str(),
        ColumnName::ExitLong.as_str(),
        ColumnName::ExitShort.as_str(),
    ];
    let column_names: Vec<String> = signals_df
        .get_column_names()
        .iter()
        .map(|name| name.to_string())
        .collect();

    for col in required_columns {
        if !column_names.contains(&col.to_string()) {
            return Err(QuantError::Backtest(BacktestError::MissingColumn {
                column: col.to_string(),
                context: context.to_string(),
            }));
        }
    }

    Ok(())
}

/// 检查权益DataFrame是否包含所有必需的列
///
/// # 参数
/// * `equity_df` - 权益DataFrame
/// * `context` - 错误上下文信息
///
/// # 返回
/// * `Result<(), QuantError>` - 如果缺少列则返回错误，否则成功
pub fn check_equity_columns(equity_df: &DataFrame, context: &str) -> Result<(), QuantError> {
    let required_columns = [
        ColumnName::Equity.as_str(),
        ColumnName::CurrentDrawdown.as_str(),
    ];
    let column_names: Vec<String> = equity_df
        .get_column_names()
        .iter()
        .map(|name| name.to_string())
        .collect();

    for col in required_columns {
        if !column_names.contains(&col.to_string()) {
            return Err(QuantError::Backtest(BacktestError::MissingColumn {
                column: col.to_string(),
                context: context.to_string(),
            }));
        }
    }

    Ok(())
}
