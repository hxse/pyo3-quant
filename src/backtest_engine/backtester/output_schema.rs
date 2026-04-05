use crate::backtest_engine::backtester::schedule_contract::BacktestParamSegment;
use polars::prelude::DataType;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OutputColumnSpec {
    pub name: &'static str,
    pub dtype: DataType,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScheduleOutputSchema {
    pub columns: Vec<OutputColumnSpec>,
}

impl ScheduleOutputSchema {
    pub fn column_names(&self) -> Vec<&'static str> {
        self.columns.iter().map(|column| column.name).collect()
    }

    pub fn has_column(&self, name: &str) -> bool {
        self.columns.iter().any(|column| column.name == name)
    }

    pub fn from_single_params(params: &crate::types::BacktestParams) -> Self {
        let schedule = vec![BacktestParamSegment::new(0, 1, params.clone())];
        build_schedule_output_schema(&schedule)
    }
}

const FIXED_COLUMNS: &[(&str, fn() -> DataType)] = &[
    ("balance", || DataType::Float64),
    ("equity", || DataType::Float64),
    ("trade_pnl_pct", || DataType::Float64),
    ("total_return_pct", || DataType::Float64),
    ("entry_long_price", || DataType::Float64),
    ("entry_short_price", || DataType::Float64),
    ("exit_long_price", || DataType::Float64),
    ("exit_short_price", || DataType::Float64),
    ("fee", || DataType::Float64),
    ("fee_cum", || DataType::Float64),
    ("current_drawdown", || DataType::Float64),
    ("risk_in_bar_direction", || DataType::Int8),
    ("first_entry_side", || DataType::Int8),
    ("frame_state", || DataType::UInt8),
];

const OPTIONAL_COLUMNS: &[&str] = &[
    "sl_pct_price_long",
    "sl_pct_price_short",
    "tp_pct_price_long",
    "tp_pct_price_short",
    "tsl_pct_price_long",
    "tsl_pct_price_short",
    "atr",
    "sl_atr_price_long",
    "sl_atr_price_short",
    "tp_atr_price_long",
    "tp_atr_price_short",
    "tsl_atr_price_long",
    "tsl_atr_price_short",
    "tsl_psar_price_long",
    "tsl_psar_price_short",
];

fn column_enabled(params: &crate::types::BacktestParams, column_name: &str) -> bool {
    match column_name {
        "sl_pct_price_long" | "sl_pct_price_short" => params.is_sl_pct_param_valid(),
        "tp_pct_price_long" | "tp_pct_price_short" => params.is_tp_pct_param_valid(),
        "tsl_pct_price_long" | "tsl_pct_price_short" => params.is_tsl_pct_param_valid(),
        "atr" => params.has_any_atr_param(),
        "sl_atr_price_long" | "sl_atr_price_short" => params.is_sl_atr_param_valid(),
        "tp_atr_price_long" | "tp_atr_price_short" => params.is_tp_atr_param_valid(),
        "tsl_atr_price_long" | "tsl_atr_price_short" => params.is_tsl_atr_param_valid(),
        "tsl_psar_price_long" | "tsl_psar_price_short" => params.is_tsl_psar_param_valid(),
        _ => false,
    }
}

pub fn build_schedule_output_schema(schedule: &[BacktestParamSegment]) -> ScheduleOutputSchema {
    let mut columns = FIXED_COLUMNS
        .iter()
        .map(|(name, dtype_fn)| OutputColumnSpec {
            name,
            dtype: dtype_fn(),
        })
        .collect::<Vec<_>>();

    for &column_name in OPTIONAL_COLUMNS {
        if schedule
            .iter()
            .any(|segment| column_enabled(&segment.params, column_name))
        {
            columns.push(OutputColumnSpec {
                name: column_name,
                dtype: DataType::Float64,
            });
        }
    }

    ScheduleOutputSchema { columns }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::{BacktestParams, Param, ParamType};

    fn params() -> BacktestParams {
        BacktestParams::default()
    }

    #[test]
    fn test_build_schedule_output_schema_contract() {
        let mut first = params();
        first.sl_pct = Some(Param::new(
            1.0,
            None,
            None,
            Some(ParamType::Float),
            false,
            false,
            0.01,
        ));

        let mut second = params();
        second.sl_atr = Some(Param::new(
            2.0,
            None,
            None,
            Some(ParamType::Float),
            false,
            false,
            0.01,
        ));
        second.atr_period = Some(Param::new(
            14.0,
            None,
            None,
            Some(ParamType::Integer),
            false,
            false,
            1.0,
        ));

        let schedule = vec![
            BacktestParamSegment::new(0, 2, first),
            BacktestParamSegment::new(2, 4, second),
        ];
        let schema = build_schedule_output_schema(&schedule);
        assert_eq!(
            schema.column_names(),
            vec![
                "balance",
                "equity",
                "trade_pnl_pct",
                "total_return_pct",
                "entry_long_price",
                "entry_short_price",
                "exit_long_price",
                "exit_short_price",
                "fee",
                "fee_cum",
                "current_drawdown",
                "risk_in_bar_direction",
                "first_entry_side",
                "frame_state",
                "sl_pct_price_long",
                "sl_pct_price_short",
                "atr",
                "sl_atr_price_long",
                "sl_atr_price_short",
            ]
        );
        assert_eq!(
            schema.columns.last().expect("末列").dtype,
            DataType::Float64
        );
    }
}
