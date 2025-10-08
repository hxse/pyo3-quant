use polars::error::ErrString;
use polars::prelude::*;
use rayon;

pub fn process_param_in_single_thread<F, R>(f: F) -> PolarsResult<R>
where
    F: FnOnce() -> PolarsResult<R> + Send,
    R: Send,
{
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(1)
        .build()
        .map_err(|e| {
            PolarsError::ComputeError(ErrString::from(format!(
                "Failed to build thread pool: {}",
                e
            )))
        })?;

    pool.install(|| f())
}
