use crate::data_conversion::types::DataContainer;
use crate::error::QuantError;

/// 从 DataContainer 中获取基础数据的长度
///
/// 这个函数从 processed_data.source 中获取 base_data_key 对应的 DataFrame 的高度，
/// 而不是从 mapping.height() 获取，这样可以确保获取到的是实际基础数据的长度。
///
/// # 参数
/// * `processed_data` - 包含数据源和映射信息的数据容器
/// * `context` - 上下文信息，通常是调用方的函数名，用于错误报告
///
/// # 返回值
/// * `Result<usize, QuantError>` - 成功时返回数据长度，失败时返回错误
pub fn get_data_length(processed_data: &DataContainer, context: &str) -> Result<usize, QuantError> {
    // 从 source 中获取 base_data_key 对应的 DataFrame
    let base_data = processed_data
        .source
        .get(&processed_data.base_data_key)
        .ok_or_else(|| {
            QuantError::Signal(crate::error::SignalError::InvalidInput(format!(
                "在 {} 中找不到基础数据键: {}",
                context, processed_data.base_data_key
            )))
        })?;

    Ok(base_data.height())
}
