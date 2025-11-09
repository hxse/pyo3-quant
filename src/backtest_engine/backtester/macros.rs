// src/backtest_engine/backtester/macros.rs
/// 校验 PreparedData 中所有切片的长度与 `len_var` 相等。
/// 在 Release 模式下仅保留一次 `len()` 调用，防止编译器把宏整体优化掉。
#[macro_export]
macro_rules! validate_prepared_data {
    ($data:expr, $len_var:ident) => {{
        // 让编译器知道 $len_var 就是 time.len()
        let $len_var = $data.time.len();

        // ---------- Debug 模式：完整断言 ----------
        #[cfg(debug_assertions)]
        {
            ::core::assert_eq!($data.open.len(), $len_var, "open length mismatch");
            ::core::assert_eq!($data.high.len(), $len_var, "high length mismatch");
            ::core::assert_eq!($data.low.len(), $len_var, "low length mismatch");
            ::core::assert_eq!($data.close.len(), $len_var, "close length mismatch");
            ::core::assert_eq!($data.volume.len(), $len_var, "volume length mismatch");
            ::core::assert_eq!(
                $data.enter_long.len(),
                $len_var,
                "enter_long length mismatch"
            );
            ::core::assert_eq!($data.exit_long.len(), $len_var, "exit_long length mismatch");
            ::core::assert_eq!(
                $data.enter_short.len(),
                $len_var,
                "enter_short length mismatch"
            );
            ::core::assert_eq!(
                $data.exit_short.len(),
                $len_var,
                "exit_short length mismatch"
            );
            if let Some(atr) = &$data.atr {
                ::core::assert_eq!(atr.len(), $len_var, "ATR length mismatch");
            }
        }

        // ---------- Release 模式：仅保留一次 len() 调用 ----------
        #[cfg(not(debug_assertions))]
        {
            // 防止编译器把整个宏优化为空
            let _ = $data.time.len();
        }

        $len_var
    }};
}

/// 校验 OutputBuffers 中所有 Vec/Option<Vec> 的长度与 `len_var` 相等。
#[macro_export]
macro_rules! validate_output_buffers {
    ($buf:expr, $len_var:ident) => {{
        // 固定列（必有）
        ::core::assert_eq!($buf.balance.len(), $len_var, "balance length mismatch");
        ::core::assert_eq!($buf.equity.len(), $len_var, "equity length mismatch");
        ::core::assert_eq!(
            $buf.cumulative_return.len(),
            $len_var,
            "cumulative_return length mismatch"
        );
        ::core::assert_eq!($buf.position.len(), $len_var, "position length mismatch");
        ::core::assert_eq!($buf.exit_mode.len(), $len_var, "exit_mode length mismatch");
        ::core::assert_eq!(
            $buf.entry_price.len(),
            $len_var,
            "entry_price length mismatch"
        );
        ::core::assert_eq!(
            $buf.exit_price.len(),
            $len_var,
            "exit_price length mismatch"
        );
        ::core::assert_eq!(
            $buf.pct_return.len(),
            $len_var,
            "pct_return length mismatch"
        );
        ::core::assert_eq!($buf.fee.len(), $len_var, "fee length mismatch");
        ::core::assert_eq!($buf.fee_cum.len(), $len_var, "fee_cum length mismatch");

        // 可选列
        if let Some(v) = &$buf.sl_pct_price {
            ::core::assert_eq!(v.len(), $len_var, "sl_pct_price length mismatch");
        }
        if let Some(v) = &$buf.tp_pct_price {
            ::core::assert_eq!(v.len(), $len_var, "tp_pct_price length mismatch");
        }
        if let Some(v) = &$buf.tsl_pct_price {
            ::core::assert_eq!(v.len(), $len_var, "tsl_pct_price length mismatch");
        }
        if let Some(v) = &$buf.atr {
            ::core::assert_eq!(v.len(), $len_var, "atr length mismatch");
        }
        if let Some(v) = &$buf.sl_atr_price {
            ::core::assert_eq!(v.len(), $len_var, "sl_atr_price length mismatch");
        }
        if let Some(v) = &$buf.tp_atr_price {
            ::core::assert_eq!(v.len(), $len_var, "tp_atr_price length mismatch");
        }
        if let Some(v) = &$buf.tsl_atr_price {
            ::core::assert_eq!(v.len(), $len_var, "tsl_atr_price length mismatch");
        }
    }};
}
