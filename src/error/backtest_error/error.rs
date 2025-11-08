use thiserror::Error;

#[derive(Error, Debug)]
pub enum BacktestError {
    /// 缺失必需的列
    #[error("缺失必需列 '{column}' (上下文: {context})")]
    MissingColumn { column: String, context: String },

    /// 数据非连续内存
    #[error("列 '{column}' 不是连续内存,请在传入前使用rechunk()处理 (上下文: {context})")]
    NonContiguousData { column: String, context: String },

    /// 无效的参数值
    #[error("无效参数 '{param_name}' = '{value}': {reason}")]
    InvalidParameter {
        param_name: String,
        value: String,
        reason: String,
    },

    /// DataFrame为空
    #[error("DataFrame为空")]
    EmptyDataFrame,

    /// 数据中包含NaN值
    #[error("列 '{column}' 包含NaN值 (上下文: {context})")]
    ContainsNaN { column: String, context: String },

    /// ATR计算失败
    #[error("ATR计算失败: {message}")]
    ATRCalculationError { message: String },

    /// 无法从DataContainer提取OHLCV数据
    #[error("无法从DataContainer提取OHLCV数据")]
    OHLCVNotFound,

    /// 数据验证失败
    #[error("数据验证失败 ({context}): {message}")]
    DataValidationError { message: String, context: String },

    /// 数据源中缺少键
    #[error("数据源中缺少键 '{key}',可用键: [{available_keys:?}]")]
    MissingDataSource {
        key: String,
        available_keys: Vec<String>,
    },

    /// 通用验证错误
    #[error("Validation Error: {0}")]
    ValidationError(String),

    /// 数组长度校验失败
    #[error("数组长度校验失败: {array_name} 长度为 {actual_len}, 期望长度为 {expected_len}")]
    ArrayLengthMismatch {
        array_name: String,
        actual_len: usize,
        expected_len: usize,
    },
}
