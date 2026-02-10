//! 输出缓冲区验证模块
//!
//! 负责验证输出缓冲区中所有数组的长度一致性

use super::output_struct::OutputBuffers;
use crate::backtest_engine::utils::column_names::ColumnName;
use crate::error::backtest_error::BacktestError;

impl OutputBuffers {
    /// 验证所有数组的长度是否相等
    ///
    /// # 返回
    /// 如果所有数组长度相等则返回 Ok(())，否则返回 Err(BacktestError)
    pub fn validate_array_lengths(&self) -> Result<(), BacktestError> {
        // 获取固定列的长度作为基准
        let base_length = self.balance.len();

        // 固定列数组名称和长度
        let fixed_arrays = [
            (ColumnName::Balance.as_str(), self.balance.len()),
            (ColumnName::Equity.as_str(), self.equity.len()),
            (ColumnName::TradePnlPct.as_str(), self.trade_pnl_pct.len()),
            (
                ColumnName::TotalReturnPct.as_str(),
                self.total_return_pct.len(),
            ),
            (
                ColumnName::EntryLongPrice.as_str(),
                self.entry_long_price.len(),
            ),
            (
                ColumnName::EntryShortPrice.as_str(),
                self.entry_short_price.len(),
            ),
            (
                ColumnName::ExitLongPrice.as_str(),
                self.exit_long_price.len(),
            ),
            (
                ColumnName::ExitShortPrice.as_str(),
                self.exit_short_price.len(),
            ),
            (ColumnName::Fee.as_str(), self.fee.len()),
            (ColumnName::FeeCum.as_str(), self.fee_cum.len()),
            (
                ColumnName::CurrentDrawdown.as_str(),
                self.current_drawdown.len(),
            ),
            (
                ColumnName::RiskInBarDirection.as_str(),
                self.risk_in_bar_direction.len(),
            ),
            (
                ColumnName::FirstEntrySide.as_str(),
                self.first_entry_side.len(),
            ),
            (ColumnName::FrameEvents.as_str(), self.frame_events.len()),
        ];

        // 检查所有固定列的长度
        for (name, len) in &fixed_arrays {
            if *len != base_length {
                return Err(BacktestError::ArrayLengthMismatch {
                    array_name: name.to_string(),
                    actual_len: *len,
                    expected_len: base_length,
                });
            }
        }

        // 可选列数组名称和长度
        let optional_arrays = [
            (ColumnName::Atr.as_str(), self.atr.as_ref().map(|v| v.len())),
            (
                ColumnName::SlPctPriceLong.as_str(),
                self.sl_pct_price_long.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::SlPctPriceShort.as_str(),
                self.sl_pct_price_short.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::SlAtrPriceLong.as_str(),
                self.sl_atr_price_long.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::SlAtrPriceShort.as_str(),
                self.sl_atr_price_short.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TpPctPriceLong.as_str(),
                self.tp_pct_price_long.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TpPctPriceShort.as_str(),
                self.tp_pct_price_short.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TpAtrPriceLong.as_str(),
                self.tp_atr_price_long.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TpAtrPriceShort.as_str(),
                self.tp_atr_price_short.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslPctPriceLong.as_str(),
                self.tsl_pct_price_long.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslPctPriceShort.as_str(),
                self.tsl_pct_price_short.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslAtrPriceLong.as_str(),
                self.tsl_atr_price_long.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslAtrPriceShort.as_str(),
                self.tsl_atr_price_short.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslPsarPriceLong.as_str(),
                self.tsl_psar_price_long.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslPsarPriceShort.as_str(),
                self.tsl_psar_price_short.as_ref().map(|v| v.len()),
            ),
        ];

        // 检查所有可选列的长度
        for (name, len_opt) in &optional_arrays {
            if let Some(len) = len_opt {
                if *len != base_length {
                    return Err(BacktestError::ArrayLengthMismatch {
                        array_name: name.to_string(),
                        actual_len: *len,
                        expected_len: base_length,
                    });
                }
            }
        }

        Ok(())
    }
}
