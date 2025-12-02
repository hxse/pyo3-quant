use crate::backtest_engine::utils::column_names::ColumnName;
use crate::{data_conversion::BacktestParams, error::backtest_error::BacktestError};
use polars::prelude::*;

/// 回测输出缓冲区结构体
/// 用于收集每根K线的输出结果，包括固定列和可选列
pub struct OutputBuffers {
    // === 固定列 ===
    /// 账户余额，带复利
    pub balance: Vec<f64>,
    /// 账户净值（含未实现盈亏），带复利
    pub equity: Vec<f64>,
    /// 历史最高净值（用于止损后暂停开仓判断）
    pub peak_equity: Vec<f64>,
    /// 单笔回报率
    pub trade_pnl_pct: Vec<f64>,
    /// 累计回报率，带复利
    pub total_return_pct: Vec<f64>,
    /// 单笔离场结算手续费
    pub fee: Vec<f64>,
    /// 当前历史累计手续费
    pub fee_cum: Vec<f64>,

    // === 价格列（价格驱动状态核心） ===
    /// 多头进场价格
    pub entry_long_price: Vec<f64>,
    /// 空头进场价格
    pub entry_short_price: Vec<f64>,
    /// 多头离场价格
    pub exit_long_price: Vec<f64>,
    /// 空头离场价格
    pub exit_short_price: Vec<f64>,

    // === 可选列 ===
    /// 百分比止损价格（可选）
    pub sl_pct_price: Option<Vec<f64>>,
    /// 百分比止盈价格（可选）
    pub tp_pct_price: Option<Vec<f64>>,
    /// 百分比跟踪止损价格（可选）
    pub tsl_pct_price: Option<Vec<f64>>,

    // === 可选列 ===
    /// ATR指标值（可选）
    pub atr: Option<Vec<f64>>,
    /// ATR止损价格（可选）
    pub sl_atr_price: Option<Vec<f64>>,
    /// ATR止盈价格（可选）
    pub tp_atr_price: Option<Vec<f64>>,
    /// ATR跟踪止损价格（可选）
    pub tsl_atr_price: Option<Vec<f64>>,

    // === Risk State Output ===
    /// Risk多头离场价格
    pub risk_exit_long_price: Vec<f64>,
    /// Risk空头离场价格
    pub risk_exit_short_price: Vec<f64>,
    /// Risk是否In-Bar离场
    pub risk_exit_in_bar: Vec<bool>,
}

impl OutputBuffers {
    /// 创建新的输出缓冲区实例
    ///
    /// # 参数
    /// * `params` - 回测参数，用于决定哪些可选列需要初始化
    /// * `capacity` - 缓冲区初始容量，通常等于K线数量
    ///
    /// # 返回
    /// 初始化完成的 OutputBuffers 实例
    pub fn new(params: &BacktestParams, capacity: usize) -> Self {
        Self {
            // 资金状态
            balance: vec![0.0; capacity],
            equity: vec![0.0; capacity],
            trade_pnl_pct: vec![0.0; capacity],
            total_return_pct: vec![0.0; capacity],
            fee: vec![0.0; capacity],
            fee_cum: vec![0.0; capacity],
            peak_equity: vec![0.0; capacity],

            // 价格列
            entry_long_price: vec![0.0; capacity],
            entry_short_price: vec![0.0; capacity],
            exit_long_price: vec![0.0; capacity],
            exit_short_price: vec![0.0; capacity],

            // 可选列根据参数决定是否初始化
            sl_pct_price: if params.is_sl_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tp_pct_price: if params.is_tp_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_pct_price: if params.is_tsl_pct_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            // ATR相关列 - 不再需要预先分配，将在主循环后直接克隆
            atr: None,
            sl_atr_price: if params.is_sl_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tp_atr_price: if params.is_tp_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },
            tsl_atr_price: if params.is_tsl_atr_param_valid() {
                Some(vec![0.0; capacity])
            } else {
                None
            },

            // Risk State Output
            risk_exit_long_price: vec![0.0; capacity],
            risk_exit_short_price: vec![0.0; capacity],
            risk_exit_in_bar: vec![false; capacity],
        }
    }

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
            (ColumnName::PeakEquity.as_str(), self.peak_equity.len()),
            (
                ColumnName::RiskExitLongPrice.as_str(),
                self.risk_exit_long_price.len(),
            ),
            (
                ColumnName::RiskExitShortPrice.as_str(),
                self.risk_exit_short_price.len(),
            ),
            (
                ColumnName::RiskExitInBar.as_str(),
                self.risk_exit_in_bar.len(),
            ),
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
                ColumnName::SlPctPrice.as_str(),
                self.sl_pct_price.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::SlAtrPrice.as_str(),
                self.sl_atr_price.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TpPctPrice.as_str(),
                self.tp_pct_price.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TpAtrPrice.as_str(),
                self.tp_atr_price.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslPctPrice.as_str(),
                self.tsl_pct_price.as_ref().map(|v| v.len()),
            ),
            (
                ColumnName::TslAtrPrice.as_str(),
                self.tsl_atr_price.as_ref().map(|v| v.len()),
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
            (ColumnName::PeakEquity.as_str(), &self.peak_equity as &[f64]),
            (
                ColumnName::RiskExitLongPrice.as_str(),
                &self.risk_exit_long_price as &[f64],
            ),
            (
                ColumnName::RiskExitShortPrice.as_str(),
                &self.risk_exit_short_price as &[f64],
            ),
        ];

        // 添加固定列
        for (name, data) in fixed_columns.iter() {
            let series = Series::new((*name).into(), data);
            columns.push(series.into());
        }

        // RiskExitInBar is boolean, handle separately or cast? Polars handles bool.
        // But fixed_columns array is typed as &[f64]. I need to handle boolean column separately or change the array structure.
        // The current fixed_columns is inferred as array of tuples (&str, &[f64]).
        // So I cannot put boolean vector there.
        // I will add it separately.

        let risk_exit_in_bar_series = Series::new(
            ColumnName::RiskExitInBar.as_str().into(),
            &self.risk_exit_in_bar,
        );
        columns.push(risk_exit_in_bar_series.into());

        // 定义可选列的名称和数据
        let optional_columns = [
            (ColumnName::SlPctPrice.as_str(), &self.sl_pct_price),
            (ColumnName::TpPctPrice.as_str(), &self.tp_pct_price),
            (ColumnName::TslPctPrice.as_str(), &self.tsl_pct_price),
            (ColumnName::Atr.as_str(), &self.atr),
            (ColumnName::SlAtrPrice.as_str(), &self.sl_atr_price),
            (ColumnName::TpAtrPrice.as_str(), &self.tp_atr_price),
            (ColumnName::TslAtrPrice.as_str(), &self.tsl_atr_price),
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

    /// 将 OutputBuffers 转换为只包含 equity 和 peak_equity 两列的 DataFrame
    ///
    /// # 返回
    /// 只包含 equity 和 peak_equity 列的 DataFrame
    pub fn to_equity_dataframe(&self) -> Result<DataFrame, BacktestError> {
        let equity_series = Series::new(ColumnName::Equity.as_str().into(), &self.equity);
        let peak_equity_series =
            Series::new(ColumnName::PeakEquity.as_str().into(), &self.peak_equity);

        DataFrame::new(vec![equity_series.into(), peak_equity_series.into()]).map_err(|e| {
            BacktestError::ValidationError(format!("Failed to create equity DataFrame: {}", e))
        })
    }
}
