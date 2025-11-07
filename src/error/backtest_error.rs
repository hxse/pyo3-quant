use polars::prelude::PolarsError;
use std::fmt::{self, Display};

#[derive(Debug, Clone)]
pub enum BacktestError {
    // === 已存在的错误(保留不修改) ===
    /// 缺失必需的列
    MissingColumn {
        column: String,
        context: String,
    },
    /// 数据非连续内存
    NonContiguousData {
        column: String,
        context: String,
    },
    /// 无效的参数值
    InvalidParameter {
        param_name: String,
        value: String,
        reason: String,
    },
    /// DataFrame为空
    EmptyDataFrame,
    /// 数据中包含NaN值
    ContainsNaN {
        column: String,
        context: String,
    },
    /// ATR计算失败
    ATRCalculationError {
        message: String,
    },
    /// 无法从DataContainer提取OHLCV数据
    OHLCVNotFound,
    /// Polars DataFrame/Series操作失败
    PolarsError {
        operation: String,
        message: String,
    },

    // === 新增:数据验证错误 ===
    /// 数据验证失败
    DataValidationError {
        message: String,
        context: String,
    },
    /// 数据源中缺少键
    MissingDataSource {
        key: String,
        available_keys: Vec<String>,
    },
    ValidationError(String),
}

impl Display for BacktestError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            // === 已存在的Display实现 (修改为新结构) ===
            Self::MissingColumn { column, context } => {
                write!(f, "缺失必需列 '{}' (上下文: {})", column, context)
            }
            Self::NonContiguousData { column, context } => {
                write!(
                    f,
                    "列 '{}' 不是连续内存,请在传入前使用rechunk()处理 (上下文: {})",
                    column, context
                )
            }
            Self::InvalidParameter {
                param_name,
                value,
                reason,
            } => {
                write!(f, "无效参数 '{}' = '{}': {}", param_name, value, reason)
            }
            Self::EmptyDataFrame => write!(f, "DataFrame为空"),
            Self::ContainsNaN { column, context } => {
                write!(f, "列 '{}' 包含NaN值 (上下文: {})", column, context)
            }
            Self::ATRCalculationError { message } => {
                write!(f, "ATR计算失败: {}", message)
            }
            Self::OHLCVNotFound => write!(f, "无法从DataContainer提取OHLCV数据"),
            Self::PolarsError { operation, message } => {
                write!(f, "Polars操作 '{}' 失败: {}", operation, message)
            }

            // === 新增:数据验证错误Display实现 ===
            Self::DataValidationError { message, context } => {
                write!(f, "数据验证失败 ({}): {}", context, message)
            }
            Self::MissingDataSource {
                key,
                available_keys,
            } => {
                write!(
                    f,
                    "数据源中缺少键 '{}',可用键: [{}]",
                    key,
                    available_keys.join(", ")
                )
            }
            Self::ValidationError(msg) => write!(f, "Validation Error: {}", msg),
        }
    }
}

impl std::error::Error for BacktestError {}

impl From<PolarsError> for BacktestError {
    fn from(err: PolarsError) -> Self {
        Self::PolarsError {
            operation: "未知操作".to_string(),
            message: err.to_string(),
        }
    }
}
