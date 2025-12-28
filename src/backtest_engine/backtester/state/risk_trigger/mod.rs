//! Risk trigger module for handling exit conditions
//!
//! This module contains the logic for determining when to exit positions
//! based on various risk management criteria such as stop loss, take profit,
//! and trailing stop loss.

pub mod gap_check;
pub mod risk_check;
pub mod risk_price_calc;
pub mod risk_state;
pub mod trigger_price_utils;
pub mod tsl_psar;

pub use risk_price_calc::Direction;
