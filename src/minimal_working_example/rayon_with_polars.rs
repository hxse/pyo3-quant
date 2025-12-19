use polars::error::ErrString;
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use rayon::prelude::*; // 用于线程池和并行迭代
use std::env;

/// 私有函数：处理单个 DataFrame，确保内部 Polars 操作为单线程。
/// 使用 Rayon 单线程池的 install 操作隔离执行。
fn process_single_df(df: &DataFrame) -> PolarsResult<DataFrame> {
    // 创建单线程池
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(1)
        .build()
        .map_err(|e| {
            PolarsError::ComputeError(ErrString::from(format!(
                "Failed to build thread pool: {}",
                e
            )))
        })?;

    // 在单线程上下文中执行 Polars 操作
    let result = pool.install(|| -> PolarsResult<DataFrame> {
        let value_series = df.column("value")?.f64()? * 2.0f64;

        let mut processed_series = value_series;

        processed_series.rename("processed_value".into());

        let mut processed_df = df.clone();

        processed_df.with_column(processed_series)?;

        Ok(processed_df)
    });

    result
}

/// 入口函数：接受 Vec<PyDataFrame>，并发处理每个 DataFrame（全核心并行），
/// 但每个处理内部使用单线程 Polars。
#[pyfunction]
pub fn process_dataframes_vec(pydfs: Vec<PyDataFrame>) -> PyResult<Vec<PyDataFrame>> {
    // ----------------------------------------------------
    // 【强制初始化 Polars/Rayon 全局 POOL】
    // 尝试调用一个简单的、依赖 Polars Core 的函数
    // 注意：这将**不会**改变已经创建的线程池大小，但会创建尚未初始化的线程池。

    // 触发 Polars POOL 初始化的简单操作示例（使用一个不会崩溃的表达式）
    // 理论上，任何 Polars 数据结构的使用都会触发
    let _s = Series::new("initializer".into(), &[1.0, 2.0, 3.0]);

    let dfs: Vec<DataFrame> = pydfs.into_iter().map(|pydf| pydf.into()).collect();

    // 使用 Rayon 并行迭代（默认全核心线程池，实现并发调用）
    let processed_dfs: Vec<DataFrame> = dfs
        .par_iter() // 使用 par_iter() 而非 into_par_iter() 以避免所有权问题
        .map(|df| {
            match process_single_df(df) {
                Ok(processed) => processed,
                Err(_) => {
                    // 错误处理：返回空 DataFrame 或日志（生产中可扩展）
                    DataFrame::empty()
                }
            }
        })
        .collect();

    // 转换为 Vec<PyDataFrame> 返回
    let py_dfs: Vec<PyDataFrame> = processed_dfs
        .into_iter()
        .map(|df| PyDataFrame(df))
        .collect();

    Ok(py_dfs)
}
