use crate::error::QuantError;
use crate::types::{DataPack, IndicatorResults};
use polars::prelude::DataFrame;

pub(super) fn normalize_indicator_results(indicators: IndicatorResults) -> IndicatorResults {
    indicators
        .into_iter()
        .filter(|(_, df)| !(df.width() == 0 && df.height() == 0))
        .collect()
}

pub(super) fn validate_raw_indicators(
    data: &DataPack,
    indicators_raw: &IndicatorResults,
) -> Result<(), QuantError> {
    for (source_key, indicator_df) in indicators_raw {
        if indicator_df
            .get_column_names()
            .iter()
            .any(|name| name.as_str() == "time")
        {
            return Err(QuantError::InvalidParam(format!(
                "PipelineRequest.indicators_raw['{source_key}'] 不允许携带 time 列"
            )));
        }
        let source_df = data.source.get(source_key).ok_or_else(|| {
            QuantError::InvalidParam(format!(
                "PipelineRequest.indicators_raw['{source_key}'] 对应的 source 不存在"
            ))
        })?;
        if indicator_df.height() != source_df.height() {
            return Err(QuantError::InvalidParam(format!(
                "PipelineRequest.indicators_raw['{source_key}'].height()={} 必须等于 data.source['{source_key}'].height()={}",
                indicator_df.height(),
                source_df.height()
            )));
        }
    }
    Ok(())
}

pub(super) fn validate_frame_height(
    data: &DataPack,
    frame: &DataFrame,
    label: &str,
) -> Result<(), QuantError> {
    if frame.height() != data.mapping.height() {
        return Err(QuantError::InvalidParam(format!(
            "{label}.height()={} 必须等于 data.mapping.height()={}",
            frame.height(),
            data.mapping.height()
        )));
    }
    Ok(())
}
