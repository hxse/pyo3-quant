use crate::error::QuantError;
use rayon;

pub fn process_param_in_single_thread<F, R>(f: F) -> Result<R, QuantError>
where
    F: FnOnce() -> Result<R, QuantError> + Send,
    R: Send,
{
    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(1)
        .build()
        .map_err(|e| {
            QuantError::InfrastructureError(format!("Failed to build thread pool: {}", e))
        })?;

    pool.install(|| f())
}
