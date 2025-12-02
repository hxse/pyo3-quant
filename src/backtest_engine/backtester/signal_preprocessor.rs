use crate::backtest_engine::utils::column_names::ColumnName;
use crate::error::QuantError;
use polars::prelude::*;
use std::sync::Arc;

/// 预处理信号数据，解决冲突并应用屏蔽规则
///
/// # 规则
///
/// 1. 如果 enter_long 和 enter_short 都为 true，则都设为 false
/// 2. 如果 enter_long 和 exit_long 都为 true，则 enter_long 设为 false
/// 3. 如果 enter_short 和 exit_short 都为 true，则 enter_short 设为 false
/// 4. 如果 skip_mask 为 true，则 enter_long 和 enter_short 设为 false
/// 5. 如果 atr 为 Some 且值为 NaN，则 enter_long 和 enter_short 设为 false
///
/// # 参数
///
/// * `df` - 包含信号列的 DataFrame
/// * `atr_series` - 可选的 ATR Series
/// * `skip_mask` - 可选的 skip_mask Series
///
/// # 返回
///
/// * `Result<DataFrame, QuantError>` - 预处理后的 DataFrame
pub fn preprocess_signals(
    df: DataFrame,
    atr_series: &Option<Series>,
    skip_mask: &Option<Series>,
) -> Result<DataFrame, QuantError> {
    let mut lazy = df.lazy();

    // 规则1: enter_long 和 enter_short 冲突 - 都设为 false
    lazy = lazy.with_columns(vec![
        when(col(ColumnName::EnterLong.as_str()).and(col(ColumnName::EnterShort.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EnterLong.as_str()))
            .alias(ColumnName::EnterLong.as_str()),
        when(col(ColumnName::EnterLong.as_str()).and(col(ColumnName::EnterShort.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EnterShort.as_str()))
            .alias(ColumnName::EnterShort.as_str()),
    ]);

    // 规则2: enter_long 和 exit_long 冲突 - enter_long 设为 false
    lazy = lazy.with_column(
        when(col(ColumnName::EnterLong.as_str()).and(col(ColumnName::ExitLong.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EnterLong.as_str()))
            .alias(ColumnName::EnterLong.as_str()),
    );

    // 规则3: enter_short 和 exit_short 冲突 - enter_short 设为 false
    lazy = lazy.with_column(
        when(col(ColumnName::EnterShort.as_str()).and(col(ColumnName::ExitShort.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EnterShort.as_str()))
            .alias(ColumnName::EnterShort.as_str()),
    );

    // 规则4: skip_mask 屏蔽 - enter 信号设为 false
    if let Some(skip_series) = skip_mask {
        let skip_name = "skip_mask_temp";
        let mut df_with_skip = lazy.collect()?;
        df_with_skip.with_column(skip_series.clone().with_name(skip_name.into()))?;

        lazy = df_with_skip.lazy();
        lazy = lazy.with_columns(vec![
            when(col(skip_name))
                .then(lit(false))
                .otherwise(col(ColumnName::EnterLong.as_str()))
                .alias(ColumnName::EnterLong.as_str()),
            when(col(skip_name))
                .then(lit(false))
                .otherwise(col(ColumnName::EnterShort.as_str()))
                .alias(ColumnName::EnterShort.as_str()),
        ]);
        lazy = lazy.drop(Selector::ByName {
            names: Arc::new([skip_name.into()]),
            strict: true,
        });
    }

    // 规则5: ATR NaN 屏蔽 - enter 信号设为 false
    if let Some(atr) = atr_series {
        let atr_name = "atr_temp";
        let mut df_with_atr = lazy.collect()?;
        df_with_atr.with_column(atr.clone().with_name(atr_name.into()))?;

        lazy = df_with_atr.lazy();
        lazy = lazy.with_columns(vec![
            when(col(atr_name).is_nan())
                .then(lit(false))
                .otherwise(col(ColumnName::EnterLong.as_str()))
                .alias(ColumnName::EnterLong.as_str()),
            when(col(atr_name).is_nan())
                .then(lit(false))
                .otherwise(col(ColumnName::EnterShort.as_str()))
                .alias(ColumnName::EnterShort.as_str()),
        ]);
        lazy = lazy.drop(Selector::ByName {
            names: Arc::new([atr_name.into()]),
            strict: true,
        });
    }

    lazy.collect().map_err(|e| e.into())
}
