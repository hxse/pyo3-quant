use crate::backtest_engine::utils::column_names::ColumnName;
use crate::error::QuantError;
use polars::prelude::*;
use std::sync::Arc;

/// 预处理信号数据，解决冲突并应用屏蔽规则
///
/// # 规则
///
/// 1. 如果 entry_long 和 entry_short 都为 true，则都设为 false
/// 2. 如果 entry_long 和 exit_long 都为 true，则 entry_long 设为 false
/// 3. 如果 entry_short 和 exit_short 都为 true，则 entry_short 设为 false
/// 4. 如果 skip_mask 为 true，则 entry_long 和 entry_short 设为 false
/// 5. 如果 atr 为 Some 且值为 NaN，则 entry_long 和 entry_short 设为 false
///
/// # 参数
///
/// * `df` - 包含信号列的 DataFrame
/// * `atr_series` - 可选的 ATR Series
/// * `skip_mask` - 可选的 skip_mask DataFrame
///
/// # 返回
///
/// * `Result<DataFrame, QuantError>` - 预处理后的 DataFrame
pub fn preprocess_signals(
    df: DataFrame,
    atr_series: &Option<Series>,
    skip_mask: &Option<DataFrame>,
) -> Result<DataFrame, QuantError> {
    let mut lazy = df.lazy();

    // 规则1: entry_long 和 entry_short 冲突 - 都设为 false
    lazy = lazy.with_columns(vec![
        when(col(ColumnName::EntryLong.as_str()).and(col(ColumnName::EntryShort.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EntryLong.as_str()))
            .alias(ColumnName::EntryLong.as_str()),
        when(col(ColumnName::EntryLong.as_str()).and(col(ColumnName::EntryShort.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EntryShort.as_str()))
            .alias(ColumnName::EntryShort.as_str()),
    ]);

    // 规则2: entry_long 和 exit_long 冲突 - entry_long 设为 false
    lazy = lazy.with_column(
        when(col(ColumnName::EntryLong.as_str()).and(col(ColumnName::ExitLong.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EntryLong.as_str()))
            .alias(ColumnName::EntryLong.as_str()),
    );

    // 规则3: entry_short 和 exit_short 冲突 - entry_short 设为 false
    lazy = lazy.with_column(
        when(col(ColumnName::EntryShort.as_str()).and(col(ColumnName::ExitShort.as_str())))
            .then(lit(false))
            .otherwise(col(ColumnName::EntryShort.as_str()))
            .alias(ColumnName::EntryShort.as_str()),
    );

    // 规则4: skip_mask 屏蔽 - enter 信号设为 false
    if let Some(skip_df) = skip_mask {
        let skip_col = skip_df.column("skip")?;
        let skip_name = "skip_mask_temp";

        // 直接使用 lit(Series) 注入，避免中间 collect()
        lazy = lazy.with_column(lit(skip_col.as_materialized_series().clone()).alias(skip_name));

        lazy = lazy.with_columns(vec![
            when(col(skip_name))
                .then(lit(false))
                .otherwise(col(ColumnName::EntryLong.as_str()))
                .alias(ColumnName::EntryLong.as_str()),
            when(col(skip_name))
                .then(lit(false))
                .otherwise(col(ColumnName::EntryShort.as_str()))
                .alias(ColumnName::EntryShort.as_str()),
        ]);

        lazy = lazy.drop(Selector::ByName {
            names: Arc::new([skip_name.into()]),
            strict: true,
        });
    }

    // 规则5: ATR NaN 屏蔽 - enter 信号设为 false
    if let Some(atr) = atr_series {
        let atr_name = "atr_temp";

        // 直接使用 lit(Series) 注入，避免中间 collect()
        lazy = lazy.with_column(lit(atr.clone()).alias(atr_name));

        lazy = lazy.with_columns(vec![
            when(col(atr_name).is_nan())
                .then(lit(false))
                .otherwise(col(ColumnName::EntryLong.as_str()))
                .alias(ColumnName::EntryLong.as_str()),
            when(col(atr_name).is_nan())
                .then(lit(false))
                .otherwise(col(ColumnName::EntryShort.as_str()))
                .alias(ColumnName::EntryShort.as_str()),
        ]);

        lazy = lazy.drop(Selector::ByName {
            names: Arc::new([atr_name.into()]),
            strict: true,
        });
    }

    lazy.collect().map_err(|e| e.into())
}
