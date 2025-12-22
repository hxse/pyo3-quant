//! Risk trigger module for handling exit conditions
//!
//! This module contains the logic for determining when to exit positions
//! based on various risk management criteria such as stop loss, take profit,
//! and trailing stop loss.

pub mod price_utils;
pub mod risk_check;
pub mod risk_state;
pub mod tsl_psar;
