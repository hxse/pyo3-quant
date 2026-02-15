pub mod backtest_error;
pub mod indicator_error;
pub mod optimizer_error;
pub mod py_interface;
pub mod quant_error;
pub mod signal_error;

pub use backtest_error::BacktestError;
pub use indicator_error::IndicatorError;
pub use optimizer_error::OptimizerError;
pub use quant_error::QuantError;
pub use signal_error::SignalError;

/// Custom macro to define exceptions with correct PyStubType information.
/// This avoids pyo3-stub-gen's default behavior of treating all exceptions as builtins.
#[macro_export]
macro_rules! define_exception {
    ($module: expr, $name: ident, $base: ty) => {
        $crate::define_exception!($module, $name, $base, "");
    };
    ($module: expr, $name: ident, $base: ty, $doc: expr) => {
        pyo3::create_exception!($module, $name, $base, $doc);

        impl pyo3_stub_gen::PyStubType for $name {
            fn type_output() -> pyo3_stub_gen::TypeInfo {
                use pyo3_stub_gen::{ModuleRef, TypeInfo};
                TypeInfo::locally_defined(stringify!($name), ModuleRef::from(stringify!($module)))
            }
        }

        pyo3_stub_gen::inventory::submit! {
            pyo3_stub_gen::type_info::PyClassInfo {
                pyclass_name: stringify!($name),
                struct_id: std::any::TypeId::of::<$name>,
                getters: &[],
                setters: &[],
                module: Some(stringify!($module)),
                doc: $doc,
                bases: &[|| <$base as pyo3_stub_gen::PyStubType>::type_output()],
                has_eq: false,
                has_ord: false,
                has_hash: false,
                has_str: false,
                subclass: true,
            }
        }
    };
}
