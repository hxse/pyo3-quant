use crate::error::QuantError;
use crate::types::DataContainer;

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

/// 验证时间戳是否为毫秒级 (ms)
///
/// 校验规则：
/// 1. 不小于 1990 年
/// 2. 不大于当前时间 + 10年
///
/// # 参数
/// * `ts` - 时间戳 (i64)
/// * `context` - 上下文错误信息 (如指标名称、字段名称)
pub fn validate_timestamp_ms(ts: i64, context: &str) -> Result<(), QuantError> {
    // 使用纯数值比较，零依赖，零开销，且避免千年虫问题
    // 1. 获取当前系统时间 (ms)
    let now_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64;

    // 2. 设定动态范围
    // 下限: 1990年 (约 6.3e11 ms)。足以排除秒级数据(1.7e9)
    let lower_bound = 630_000_000_000;
    // 上限: 当前时间 + 10年 (约 3.15e11 ms)
    // 10年 ~ 10 * 365 * 24 * 3600 * 1000 = 315,360,000,000
    let upper_bound = now_ms + 316_000_000_000;

    if ts < lower_bound || ts > upper_bound {
        return Err(QuantError::Signal(crate::error::SignalError::InvalidInput(
            format!(
                "{} 时间戳异常: 值 {} 不在合理范围 ({} ~ {}). 期望毫秒级 (ms).",
                context, ts, lower_bound, upper_bound
            ),
        )));
    }
    Ok(())
}
