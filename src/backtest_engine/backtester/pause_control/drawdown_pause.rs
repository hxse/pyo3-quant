use crate::backtest_engine::backtester::pause_control::utils::{
    check_equity_columns, check_signal_only_columns,
};
use crate::backtest_engine::utils::column_names::ColumnName;
use crate::data_conversion::BacktestParams;
use crate::error::{backtest_error::BacktestError, QuantError};
use polars::prelude::*;

/// 计算是否触发暂停的表达式
///
/// 当回撤幅度 >= stop_pct 时触发暂停
fn pause_expression(stop_pct: f64) -> Expr {
    drawdown_expression().gt_eq(lit(stop_pct))
}

/// 计算回撤幅度的表达式
///
/// 直接使用 current_drawdown 列
fn drawdown_expression() -> Expr {
    col(ColumnName::CurrentDrawdown.as_str())
}

/// 根据回撤情况修改信号
///
/// # 参数
/// * `equity_df` - 包含equity和current_drawdown两列的DataFrame
/// * `signals_df` - 原始信号DataFrame
/// * `backtest_params` - 回测参数，包含stop_pct和resume_pct
///
/// # 返回
/// * `(DataFrame, Series)` - 修改后的信号DataFrame和表示是否触发暂停的Series
pub fn drawdown_pause_signals(
    equity_df: &DataFrame,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<(DataFrame, Series), QuantError> {
    // 检查信号DataFrame是否包含必要的信号列
    check_signal_only_columns(signals_df, "modify_signals_based_on_drawdown")?;

    // 检查权益DataFrame是否包含必要的权益列
    check_equity_columns(equity_df, "modify_signals_based_on_drawdown")?;

    // 克隆signals_df并转换为lazy模式
    let mut lazy_df = signals_df.clone().lazy();

    // 从 equity_df 中引入列进行计算
    let equity_lazy_df = equity_df.clone().lazy();
    lazy_df = lazy_df.with_context(&[equity_lazy_df]);

    // 先计算是否触发暂停
    lazy_df =
        lazy_df.with_column(pause_expression(backtest_params.pause_drawdown.value).alias("pause"));

    // 应用回撤逻辑修改信号
    lazy_df = lazy_df
        .with_column(
            // 当暂停时，将entry_long设为false
            when(col("pause"))
                .then(lit(false))
                .otherwise(col(ColumnName::EntryLong.as_str()))
                .alias(ColumnName::EntryLong.as_str()),
        )
        .with_column(
            // 当暂停时，将entry_short设为false
            when(col("pause"))
                .then(lit(false))
                .otherwise(col(ColumnName::EntryShort.as_str()))
                .alias(ColumnName::EntryShort.as_str()),
        );

    // 获取所有原始列名，除了临时添加的列
    let original_columns: Vec<String> = signals_df
        .get_column_names()
        .iter()
        .map(|name| name.to_string())
        .collect();

    // 选择原始列和pause列
    let mut select_columns: Vec<Expr> = original_columns.iter().map(col).collect();
    select_columns.push(col("pause"));

    lazy_df = lazy_df.select(select_columns);

    // 执行lazy计算并提取pause列
    let mut df = lazy_df.collect().map_err(|e| {
        QuantError::Backtest(BacktestError::DataValidationError {
            message: format!("Failed to execute lazy operations: {}", e),
            context: "modify_signals_based_on_drawdown".to_string(),
        })
    })?;

    // 提取pause列并转换为Series
    let pause_column = df.column("pause").map_err(|e| {
        QuantError::Backtest(BacktestError::MissingColumn {
            column: "pause".to_string(),
            context: format!("Failed to get pause column: {}", e),
        })
    })?;
    let pause_series = pause_column.as_materialized_series().clone();

    // 移除pause列，只保留原始列
    let _ = df.drop_in_place("pause");

    Ok((df, pause_series))
}
