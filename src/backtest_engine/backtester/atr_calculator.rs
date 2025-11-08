use crate::backtest_engine::indicators::atr::{atr_eager, ATRConfig};
use crate::data_conversion::input::param_set::BacktestParams;
use crate::error::backtest_error::BacktestError;
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
    // 检查是否需要 ATR
    if params.sl_atr.value <= 0.0 && params.tp_atr.value <= 0.0 && params.tsl_atr.value <= 0.0 {
        return Ok(None);
    }

    // 创建 ATR 配置
    let atr_config = ATRConfig::new(params.atr_period.value as i64);

    // 计算 ATR
    let atr_series = atr_eager(ohlcv, &atr_config)?;

    Ok(Some(atr_series))
}
