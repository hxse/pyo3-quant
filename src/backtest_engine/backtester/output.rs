use crate::data_conversion::BacktestParams;
use crate::error::backtest_error::BacktestError;
use polars::prelude::*;

/// 回测输出缓冲区结构体
/// 用于收集每根K线的输出结果，包括固定列和可选列
pub struct OutputBuffers {
    // === 固定列 ===
    /// 账户余额，带复利
    pub balance: Vec<f64>,
    /// 账户净值（含未实现盈亏），带复利
    pub equity: Vec<f64>,
    /// 累计回报率，带复利
    pub cumulative_return: Vec<f64>,
    /// 仓位状态（i8）
    /// 0=无仓位, 1=进多, 2=持多, 3=平多, 4=平空进多
    /// -1=进空, -2=持空, -3=平空, -4=平多进空
    pub position: Vec<i8>,
    /// 离场模式（u8）
    /// 0=无离场, 1=in_bar离场, 2=next_bar离场
    pub exit_mode: Vec<u8>,
    /// 进场价格
    pub entry_price: Vec<f64>,
    /// 实际离场价格
    pub exit_price: Vec<f64>,
    /// 本笔交易盈亏百分比
    pub pct_return: Vec<f64>,
    /// 单笔离场结算手续费
    pub fee: Vec<f64>,
    /// 当前历史累计手续费
    pub fee_cum: Vec<f64>,

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
            // 固定列总是初始化
            balance: vec![0.0; capacity],
            equity: vec![0.0; capacity],
            cumulative_return: vec![0.0; capacity],
            position: vec![0; capacity],
            exit_mode: vec![0; capacity],
            entry_price: vec![0.0; capacity],
            exit_price: vec![0.0; capacity],
            pct_return: vec![0.0; capacity],
            fee: vec![0.0; capacity],
            fee_cum: vec![0.0; capacity],

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
            // ATR相关列
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
            ("equity", self.equity.len()),
            ("cumulative_return", self.cumulative_return.len()),
            ("position", self.position.len()),
            ("exit_mode", self.exit_mode.len()),
            ("entry_price", self.entry_price.len()),
            ("exit_price", self.exit_price.len()),
            ("pct_return", self.pct_return.len()),
            ("fee", self.fee.len()),
            ("fee_cum", self.fee_cum.len()),
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
            ("sl_pct_price", self.sl_pct_price.as_ref().map(|v| v.len())),
            ("sl_atr_price", self.sl_atr_price.as_ref().map(|v| v.len())),
            ("tp_pct_price", self.tp_pct_price.as_ref().map(|v| v.len())),
            ("tp_atr_price", self.tp_atr_price.as_ref().map(|v| v.len())),
            (
                "tsl_pct_price",
                self.tsl_pct_price.as_ref().map(|v| v.len()),
            ),
            (
                "tsl_atr_price",
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

        // 添加固定列
        let balance_series = Series::new("balance".into(), self.balance.as_slice()).into();
        columns.push(balance_series);

        let equity_series = Series::new("equity".into(), self.equity.as_slice()).into();
        columns.push(equity_series);

        let cumulative_return_series = Series::new(
            "cumulative_return".into(),
            self.cumulative_return.as_slice(),
        )
        .into();
        columns.push(cumulative_return_series);

        // 简化position：Vec<i8> → Vec<i32> → Series<Int8>
        let position_series = Series::new(
            "position".into(),
            &self.position.iter().map(|&x| x as i32).collect::<Vec<_>>(),
        )
        .cast(&DataType::Int8)
        .map_err(|e| BacktestError::ValidationError(format!("Failed to cast position to Int8: {}", e)))?;
        columns.push(position_series.into());

        // 简化exit_mode：Vec<u8> → Vec<u32> → Series<UInt8>
        let exit_mode_series = Series::new(
            "exit_mode".into(),
            &self.exit_mode.iter().map(|&x| x as u32).collect::<Vec<_>>(),
        )
        .cast(&DataType::UInt8)
        .map_err(|e| BacktestError::ValidationError(format!("Failed to cast exit_mode to UInt8: {}", e)))?;
        columns.push(exit_mode_series.into());

        let entry_price_series =
            Series::new("entry_price".into(), self.entry_price.as_slice()).into();
        columns.push(entry_price_series);

        let exit_price_series = Series::new("exit_price".into(), self.exit_price.as_slice()).into();
        columns.push(exit_price_series);

        let pct_return_series = Series::new("pct_return".into(), self.pct_return.as_slice()).into();
        columns.push(pct_return_series);

        let fee_series = Series::new("fee".into(), self.fee.as_slice()).into();
        columns.push(fee_series);

        let fee_cum_series = Series::new("fee_cum".into(), self.fee_cum.as_slice()).into();
        columns.push(fee_cum_series);

        // 添加可选列（仅当它们不为 None 时）
        if let Some(ref sl_pct_price) = self.sl_pct_price {
            let sl_pct_price_series =
                Series::new("sl_pct_price".into(), sl_pct_price.as_slice()).into();
            columns.push(sl_pct_price_series);
        }
        if let Some(ref tp_pct_price) = self.tp_pct_price {
            let tp_pct_price_series =
                Series::new("tp_pct_price".into(), tp_pct_price.as_slice()).into();
            columns.push(tp_pct_price_series);
        }
        if let Some(ref tsl_pct_price) = self.tsl_pct_price {
            let tsl_pct_price_series =
                Series::new("tsl_pct_price".into(), tsl_pct_price.as_slice()).into();
            columns.push(tsl_pct_price_series);
        }
        if let Some(ref atr) = self.atr {
            let atr_series = Series::new("atr".into(), atr.as_slice()).into();
            columns.push(atr_series);
        }
        if let Some(ref sl_atr_price) = self.sl_atr_price {
            let sl_atr_price_series =
                Series::new("sl_atr_price".into(), sl_atr_price.as_slice()).into();
            columns.push(sl_atr_price_series);
        }
        if let Some(ref tp_atr_price) = self.tp_atr_price {
            let tp_atr_price_series =
                Series::new("tp_atr_price".into(), tp_atr_price.as_slice()).into();
            columns.push(tp_atr_price_series);
        }
        if let Some(ref tsl_atr_price) = self.tsl_atr_price {
            let tsl_atr_price_series =
                Series::new("tsl_atr_price".into(), tsl_atr_price.as_slice()).into();
            columns.push(tsl_atr_price_series);
        }

        DataFrame::new(columns).map_err(|e| {
            BacktestError::ValidationError(format!("Failed to create DataFrame: {}", e))
        })
    }
}
