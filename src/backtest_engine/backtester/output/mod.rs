//! 输出缓冲区模块
//!
//! 将输出缓冲区相关的代码模块化组织：
//! - `output_struct`: 结构体定义
//! - `output_init`: 初始化逻辑
//! - `output_validate`: 数组长度验证
//! - `output_convert`: DataFrame 转换

mod output_convert;
mod output_init;
mod output_struct;
mod output_validate;

// 重新导出主结构
pub use output_struct::OutputBuffers;
