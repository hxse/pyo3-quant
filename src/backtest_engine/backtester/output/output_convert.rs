//! 输出缓冲区转换模块
//!
//! 负责将OutputBuffers转换为Polars DataFrame

use super::output_struct::OutputBuffers;
use crate::backtest_engine::utils::column_names::ColumnName;
use crate::error::backtest_error::BacktestError;
use polars::prelude::*;

impl OutputBuffers {
    /// 将 OutputBuffers 转换为 DataFrame，只包含非空的列
    ///
    /// # 返回
    /// 包含所有非空列的 DataFrame
    pub fn to_dataframe(&self) -> Result<DataFrame, BacktestError> {
        let mut columns: Vec<Column> = Vec::new();

        // === 价格列和状态列直接添加 ===

        // 定义固定列的名称和数据
        let fixed_columns = [
            (ColumnName::Balance.as_str(), &self.balance as &[f64]),
            (ColumnName::Equity.as_str(), &self.equity as &[f64]),
            (
                ColumnName::TradePnlPct.as_str(),
                &self.trade_pnl_pct as &[f64],
            ),
            (
                ColumnName::TotalReturnPct.as_str(),
                &self.total_return_pct as &[f64],
            ),
            (
                ColumnName::EntryLongPrice.as_str(),
                &self.entry_long_price as &[f64],
            ),
            (
                ColumnName::EntryShortPrice.as_str(),
                &self.entry_short_price as &[f64],
            ),
            (
                ColumnName::ExitLongPrice.as_str(),
                &self.exit_long_price as &[f64],
            ),
            (
                ColumnName::ExitShortPrice.as_str(),
                &self.exit_short_price as &[f64],
            ),
            (ColumnName::Fee.as_str(), &self.fee as &[f64]),
            (ColumnName::FeeCum.as_str(), &self.fee_cum as &[f64]),
            (
                ColumnName::CurrentDrawdown.as_str(),
                &self.current_drawdown as &[f64],
            ),
        ];

        // 添加固定列
        for (name, data) in fixed_columns.iter() {
            let series = Series::new((*name).into(), data);
            columns.push(series.into());
        }

        let risk_in_bar_direction_series = Int8Chunked::from_slice(
            ColumnName::RiskInBarDirection.as_pl_small_str(),
            &self.risk_in_bar_direction,
        )
        .into_series();
        columns.push(risk_in_bar_direction_series.into());

        let first_entry_side_series = Int8Chunked::from_slice(
            ColumnName::FirstEntrySide.as_pl_small_str(),
            &self.first_entry_side,
        )
        .into_series();
        columns.push(first_entry_side_series.into());

        // 定义可选列的名称和数据
        let optional_columns = [
            (ColumnName::SlPctPriceLong.as_str(), &self.sl_pct_price_long),
            (
                ColumnName::SlPctPriceShort.as_str(),
                &self.sl_pct_price_short,
            ),
            (ColumnName::TpPctPriceLong.as_str(), &self.tp_pct_price_long),
            (
                ColumnName::TpPctPriceShort.as_str(),
                &self.tp_pct_price_short,
            ),
            (
                ColumnName::TslPctPriceLong.as_str(),
                &self.tsl_pct_price_long,
            ),
            (
                ColumnName::TslPctPriceShort.as_str(),
                &self.tsl_pct_price_short,
            ),
            (ColumnName::Atr.as_str(), &self.atr),
            (ColumnName::SlAtrPriceLong.as_str(), &self.sl_atr_price_long),
            (
                ColumnName::SlAtrPriceShort.as_str(),
                &self.sl_atr_price_short,
            ),
            (ColumnName::TpAtrPriceLong.as_str(), &self.tp_atr_price_long),
            (
                ColumnName::TpAtrPriceShort.as_str(),
                &self.tp_atr_price_short,
            ),
            (
                ColumnName::TslAtrPriceLong.as_str(),
                &self.tsl_atr_price_long,
            ),
            (
                ColumnName::TslAtrPriceShort.as_str(),
                &self.tsl_atr_price_short,
            ),
            (
                ColumnName::TslPsarPriceLong.as_str(),
                &self.tsl_psar_price_long,
            ),
            (
                ColumnName::TslPsarPriceShort.as_str(),
                &self.tsl_psar_price_short,
            ),
        ];

        // 添加可选列（仅当它们不为 None 时）
        for (name, data) in optional_columns.iter() {
            if let Some(ref vec_data) = data {
                let series = Series::new((*name).into(), vec_data);
                columns.push(series.into());
            }
        }

        DataFrame::new(columns).map_err(|e| {
            BacktestError::ValidationError(format!("Failed to create DataFrame: {}", e))
        })
    }
}
