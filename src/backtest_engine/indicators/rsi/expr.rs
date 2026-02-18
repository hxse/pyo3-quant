use super::super::utils::null_when_expr;
use super::config::RSIConfig;
use crate::backtest_engine::indicators::rma::{rma_expr, RMAConfig};
use crate::error::QuantError;
use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;

/// 返回计算 RSI 所需的核心表达式集合。
pub fn rsi_expr(
    config: &RSIConfig,
) -> Result<(Expr, Expr, Expr, Expr, Expr, Expr, Expr, Expr), QuantError> {
    let col_name = config.column_name.as_str();
    let period = config.period;

    // 计算过程中的临时列名，避免污染业务字段命名。
    let change_temp_name = "rsi_change_temp";
    let gain_temp_name = "rsi_gain_temp";
    let loss_temp_name = "rsi_loss_temp";
    let initial_avg_gain_temp_name = "rsi_initial_avg_gain_temp";
    let initial_avg_loss_temp_name = "rsi_initial_avg_loss_temp";
    let processed_gain_temp_name = "rsi_processed_gain_temp";
    let processed_loss_temp_name = "rsi_processed_loss_temp";
    let avg_gain_temp_name = "rsi_avg_gain_temp";
    let avg_loss_temp_name = "rsi_avg_loss_temp";
    let index_col_name = "index";

    // 1. 价格变化
    let change_expr = col(col_name)
        .diff(lit(1), Default::default())
        .alias(change_temp_name);

    // 2. gain/loss 拆分
    let gain_expr = when(col(change_temp_name).gt(lit(0.0)))
        .then(col(change_temp_name))
        .otherwise(lit(0.0))
        .alias(gain_temp_name);

    let loss_expr = when(col(change_temp_name).lt(lit(0.0)))
        .then(col(change_temp_name).abs())
        .otherwise(lit(0.0))
        .alias(loss_temp_name);

    // 3. 初始化 Wilder 平滑首值（与 TA-Lib 切片行为对齐）
    let initial_avg_gain_expr = col(gain_temp_name)
        .slice(lit(1), lit(period as u32))
        .mean()
        .alias(initial_avg_gain_temp_name);

    let initial_avg_loss_expr = col(loss_temp_name)
        .slice(lit(1), lit(period as u32))
        .mean()
        .alias(initial_avg_loss_temp_name);

    // 4. 预处理序列（period 之前置空，period 位置写入初始均值）
    let processed_gain_expr = when(col(index_col_name).cast(DataType::Int64).lt(lit(period)))
        .then(null_when_expr(
            col(index_col_name).cast(DataType::Int64).lt(lit(period)),
            col(gain_temp_name),
        ))
        .when(col(index_col_name).cast(DataType::Int64).eq(lit(period)))
        .then(initial_avg_gain_expr)
        .otherwise(col(gain_temp_name))
        .alias(processed_gain_temp_name);

    let processed_loss_expr = when(col(index_col_name).cast(DataType::Int64).lt(lit(period)))
        .then(null_when_expr(
            col(index_col_name).cast(DataType::Int64).lt(lit(period)),
            col(loss_temp_name),
        ))
        .when(col(index_col_name).cast(DataType::Int64).eq(lit(period)))
        .then(initial_avg_loss_expr)
        .otherwise(col(loss_temp_name))
        .alias(processed_loss_temp_name);

    // 5. Wilder 平滑
    let avg_gain_expr = rma_expr(&RMAConfig {
        column_name: processed_gain_temp_name.to_string(),
        alias_name: avg_gain_temp_name.to_string(),
        period,
    })?;

    let avg_loss_expr = rma_expr(&RMAConfig {
        column_name: processed_loss_temp_name.to_string(),
        alias_name: avg_loss_temp_name.to_string(),
        period,
    })?;

    // 6. RSI 公式
    let rsi_expr = (lit(100.0) * col(avg_gain_temp_name)
        / (col(avg_gain_temp_name) + col(avg_loss_temp_name)))
    .alias(config.alias_name.as_str());

    Ok((
        change_expr,
        gain_expr,
        loss_expr,
        processed_gain_expr,
        processed_loss_expr,
        avg_gain_expr,
        avg_loss_expr,
        rsi_expr,
    ))
}
