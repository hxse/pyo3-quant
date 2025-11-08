use crate::data_conversion::BacktestParams;
use crate::error::backtest_error::BacktestError;

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
            balance: Vec::with_capacity(capacity),
            equity: Vec::with_capacity(capacity),
            cumulative_return: Vec::with_capacity(capacity),
            position: Vec::with_capacity(capacity),
            exit_mode: Vec::with_capacity(capacity),
            entry_price: Vec::with_capacity(capacity),
            exit_price: Vec::with_capacity(capacity),
            pct_return: Vec::with_capacity(capacity),
            fee: Vec::with_capacity(capacity),
            fee_cum: Vec::with_capacity(capacity),

            // 可选列根据参数决定是否初始化
            sl_pct_price: if params.is_sl_pct_enabled() {
                Some(Vec::with_capacity(capacity))
            } else {
                None
            },
            tp_pct_price: if params.is_tp_pct_enabled() {
                Some(Vec::with_capacity(capacity))
            } else {
                None
            },
            tsl_pct_price: if params.is_tsl_pct_enabled() {
                Some(Vec::with_capacity(capacity))
            } else {
                None
            },
            sl_atr_price: if params.is_sl_atr_enabled() {
                Some(Vec::with_capacity(capacity))
            } else {
                None
            },
            tp_atr_price: if params.is_tp_atr_enabled() {
                Some(Vec::with_capacity(capacity))
            } else {
                None
            },
            tsl_atr_price: if params.is_tsl_atr_enabled() {
                Some(Vec::with_capacity(capacity))
            } else {
                None
            },
        }
    }

    /// 给OutputBuffers的每个数组push一个默认值
    pub fn push_default_value(&mut self) {
        // 固定列的默认值
        self.balance.push(0.0);
        self.equity.push(0.0);
        self.cumulative_return.push(0.0);
        self.position.push(0);
        self.exit_mode.push(0);
        self.entry_price.push(0.0);
        self.exit_price.push(0.0);
        self.pct_return.push(0.0);
        self.fee.push(0.0);
        self.fee_cum.push(0.0);

        // 可选列的默认值
        if let Some(ref mut sl_pct_price) = self.sl_pct_price {
            sl_pct_price.push(0.0);
        }
        if let Some(ref mut sl_atr_price) = self.sl_atr_price {
            sl_atr_price.push(0.0);
        }
        if let Some(ref mut tp_pct_price) = self.tp_pct_price {
            tp_pct_price.push(0.0);
        }
        if let Some(ref mut tp_atr_price) = self.tp_atr_price {
            tp_atr_price.push(0.0);
        }
        if let Some(ref mut tsl_pct_price) = self.tsl_pct_price {
            tsl_pct_price.push(0.0);
        }
        if let Some(ref mut tsl_atr_price) = self.tsl_atr_price {
            tsl_atr_price.push(0.0);
        }
    }

    /// 验证所有数组的长度是否相等
    ///
    /// # 返回
    /// 如果所有数组长度相等则返回 Ok(())，否则返回 Err(BacktestError)
    pub fn validate_array_lengths(&self) -> Result<(), BacktestError> {
        // 获取固定列的长度作为基准
        let base_length = self.balance.len();

        // 检查所有固定列的长度
        if self.equity.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "equity".to_string(),
                actual_len: self.equity.len(),
                expected_len: base_length,
            });
        }
        if self.cumulative_return.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "cumulative_return".to_string(),
                actual_len: self.cumulative_return.len(),
                expected_len: base_length,
            });
        }
        if self.position.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "position".to_string(),
                actual_len: self.position.len(),
                expected_len: base_length,
            });
        }
        if self.exit_mode.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "exit_mode".to_string(),
                actual_len: self.exit_mode.len(),
                expected_len: base_length,
            });
        }
        if self.entry_price.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "entry_price".to_string(),
                actual_len: self.entry_price.len(),
                expected_len: base_length,
            });
        }
        if self.exit_price.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "exit_price".to_string(),
                actual_len: self.exit_price.len(),
                expected_len: base_length,
            });
        }
        if self.pct_return.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "pct_return".to_string(),
                actual_len: self.pct_return.len(),
                expected_len: base_length,
            });
        }
        if self.fee.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "fee".to_string(),
                actual_len: self.fee.len(),
                expected_len: base_length,
            });
        }
        if self.fee_cum.len() != base_length {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "fee_cum".to_string(),
                actual_len: self.fee_cum.len(),
                expected_len: base_length,
            });
        }

        // 检查所有可选列的长度
        if let Some(ref sl_pct_price) = self.sl_pct_price {
            if sl_pct_price.len() != base_length {
                return Err(BacktestError::ArrayLengthMismatch {
                    array_name: "sl_pct_price".to_string(),
                    actual_len: sl_pct_price.len(),
                    expected_len: base_length,
                });
            }
        }

        if let Some(ref sl_atr_price) = self.sl_atr_price {
            if sl_atr_price.len() != base_length {
                return Err(BacktestError::ArrayLengthMismatch {
                    array_name: "sl_atr_price".to_string(),
                    actual_len: sl_atr_price.len(),
                    expected_len: base_length,
                });
            }
        }

        if let Some(ref tp_pct_price) = self.tp_pct_price {
            if tp_pct_price.len() != base_length {
                return Err(BacktestError::ArrayLengthMismatch {
                    array_name: "tp_pct_price".to_string(),
                    actual_len: tp_pct_price.len(),
                    expected_len: base_length,
                });
            }
        }

        if let Some(ref tp_atr_price) = self.tp_atr_price {
            if tp_atr_price.len() != base_length {
                return Err(BacktestError::ArrayLengthMismatch {
                    array_name: "tp_atr_price".to_string(),
                    actual_len: tp_atr_price.len(),
                    expected_len: base_length,
                });
            }
        }

        if let Some(ref tsl_pct_price) = self.tsl_pct_price {
            if tsl_pct_price.len() != base_length {
                return Err(BacktestError::ArrayLengthMismatch {
                    array_name: "tsl_pct_price".to_string(),
                    actual_len: tsl_pct_price.len(),
                    expected_len: base_length,
                });
            }
        }

        if let Some(ref tsl_atr_price) = self.tsl_atr_price {
            if tsl_atr_price.len() != base_length {
                return Err(BacktestError::ArrayLengthMismatch {
                    array_name: "tsl_atr_price".to_string(),
                    actual_len: tsl_atr_price.len(),
                    expected_len: base_length,
                });
            }
        }

        Ok(())
    }
}
