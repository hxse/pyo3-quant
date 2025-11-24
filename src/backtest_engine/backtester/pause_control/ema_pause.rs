use crate::backtest_engine::backtester::pause_control::utils::{
    check_equity_columns, check_signal_only_columns,
};
use crate::backtest_engine::{indicators::ema, utils::column_names::ColumnName};
use crate::data_conversion::BacktestParams;
use crate::error::{backtest_error::BacktestError, QuantError};
use polars::prelude::*;

/// 计算是否触发EMA暂停的表达式
///
/// 当equity < equity_ema时触发暂停
fn pause_expression() -> Expr {
    col("equity_temp").lt(col("equity_ema"))
}

/// 根据EMA暂停信号修改信号
///
/// 当账户净值小于账户净值的EMA时触发暂停
pub fn pause_ema_signals(
    equity_df: &DataFrame,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<(DataFrame, Series), QuantError> {
    // 检查信号DataFrame是否包含必要的信号列
    check_signal_only_columns(signals_df, "pause_ema_signals")?;

    // 检查权益DataFrame是否包含必要的权益列
    check_equity_columns(equity_df, "pause_ema_signals")?;

    // 克隆signals_df并转换为lazy模式
    let mut lazy_df = signals_df.clone().lazy();

    // 从 equity_df 中获取 equity 列的数据，并直接使用表达式
    let equity_lazy_df = equity_df.clone().lazy();
    lazy_df = lazy_df
        .with_context(&[equity_lazy_df])
        .with_columns([col("equity").alias("equity_temp")]);

    // 计算equity的EMA，复用ema模块的表达式
    let ema_period = backtest_params.pause_ema.value as i64;
    let ema_config = ema::EMAConfig {
        period: ema_period,
        column_name: "equity_temp".to_string(),
        alias_name: "equity_ema".to_string(),
        processed_column_alias: "ema_processed_equity_temp".to_string(),
        initial_value_temp: "ema_initial_value_temp".to_string(),
        start_offset: 0,
        ignore_nulls: true,
    };
    let (processed_expr, ema_expr) = ema::ema_expr(&ema_config)?;
    lazy_df = lazy_df
        .with_row_index("index", None)
        .with_column(processed_expr)
        .with_column(ema_expr);

    // 计算是否触发暂停
    lazy_df = lazy_df.with_column(pause_expression().alias("pause"));

    // 应用EMA暂停逻辑修改信号
    lazy_df = lazy_df
        .with_column(
            // 当暂停时，将enter_long设为false
            when(col("pause"))
                .then(lit(false))
                .otherwise(col(ColumnName::EnterLong.as_str()))
                .alias(ColumnName::EnterLong.as_str()),
        )
        .with_column(
            // 当暂停时，将enter_short设为false
            when(col("pause"))
                .then(lit(false))
                .otherwise(col(ColumnName::EnterShort.as_str()))
                .alias(ColumnName::EnterShort.as_str()),
        );

    // 获取所有原始列名，除了临时添加的列
    let original_columns: Vec<String> = signals_df
        .get_column_names()
        .iter()
        .map(|name| name.to_string())
        .collect();

    // 选择原始列和pause列
    let mut select_columns: Vec<Expr> = original_columns.iter().map(|name| col(name)).collect();
    select_columns.push(col("pause"));

    lazy_df = lazy_df.select(select_columns);

    // 执行lazy计算并提取pause列
    let mut df = lazy_df.collect().map_err(|e| {
        QuantError::Backtest(BacktestError::DataValidationError {
            message: format!("Failed to execute lazy operations: {}", e),
            context: "pause_ema_signals".to_string(),
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
