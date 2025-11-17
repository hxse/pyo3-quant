use crate::data_conversion::BacktestParams;
use crate::error::{backtest_error::BacktestError, QuantError};
use polars::prelude::*;
/// 检查信号DataFrame是否包含所有必需的列
///
/// # 参数
/// * `signals_df` - 信号DataFrame
/// * `context` - 错误上下文信息
///
/// # 返回
/// * `Result<(), QuantError>` - 如果缺少列则返回错误，否则成功
pub fn check_required_columns(signals_df: &DataFrame, context: &str) -> Result<(), QuantError> {
    let required_columns = [
        "entry_long",
        "entry_short",
        "exit_long",
        "exit_short",
        "equity",
        "peak_equity",
    ];
    let column_names: Vec<String> = signals_df
        .get_column_names()
        .iter()
        .map(|name| name.to_string())
        .collect();

    for col in &required_columns {
        if !column_names.contains(&col.to_string()) {
            return Err(QuantError::Backtest(BacktestError::MissingColumn {
                column: col.to_string(),
                context: context.to_string(),
            }));
        }
    }

    Ok(())
}
