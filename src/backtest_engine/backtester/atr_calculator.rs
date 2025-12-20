use crate::backtest_engine::indicators::atr::{atr_eager, ATRConfig};
use crate::data_conversion::types::param_set::BacktestParams;
use crate::error::QuantError;
use polars::prelude::*;

/// 根据回测参数条件性地计算 ATR 指标
///
/// # 参数
/// * `ohlcv` - 包含 OHLCV 数据的 DataFrame
/// * `params` - 回测参数，包含 ATR 相关配置
///
/// # 返回值
/// * `Ok(Some(Series))` - 当需要 ATR 时返回计算结果
/// * `Ok(None)` - 当不需要 ATR 时返回 None
/// * `Err(QuantError)` - 计算过程中的错误
pub fn calculate_atr_if_needed(
    ohlcv: &DataFrame,
    params: &BacktestParams,
) -> Result<Option<Series>, QuantError> {
    // 使用 param_set.rs 中的 validate_atr_consistency 方法验证 ATR 参数一致性
    let has_atr_params = params.validate_atr_consistency()?;

    if has_atr_params {
        // ATR 参数有效，计算 ATR
        let atr_period = params.atr_period.as_ref().unwrap().value as i64;
        let atr_config = ATRConfig::new(atr_period);
        let atr_series = atr_eager(ohlcv, &atr_config)?;
        Ok(Some(atr_series))
    } else {
        // 没有 ATR 参数，不计算 ATR
        Ok(None)
    }
}
