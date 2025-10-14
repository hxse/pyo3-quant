use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

/// 自定义结构体，直接使用 DataFrame 而非 PyDataFrame
#[derive(Clone)]
pub struct CustomProcessedDataDict {
    pub mapping: DataFrame,
    pub skip_mask: DataFrame,
    pub ohlcv: Vec<DataFrame>, // 直接使用 DataFrame，无需 .0 访问
    pub extra_data: HashMap<String, Vec<DataFrame>>,
}

/// 手动实现 FromPyObject trait
/// 这将自动处理 Python 对象到 Rust 类型的转换
impl<'py> FromPyObject<'py> for CustomProcessedDataDict {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        // 从 Python 对象中提取各个属性
        let mapping_py: PyDataFrame = ob.getattr("mapping")?.extract()?;
        let skip_mask_py: PyDataFrame = ob.getattr("skip_mask")?.extract()?;
        let ohlcv_py: Vec<PyDataFrame> = ob.getattr("ohlcv")?.extract()?;
        let extra_data_py: HashMap<String, Vec<PyDataFrame>> =
            ob.getattr("extra_data")?.extract()?;

        // 将 PyDataFrame 转换为 Rust 原生 DataFrame
        Ok(CustomProcessedDataDict {
            mapping: mapping_py.into(),
            skip_mask: skip_mask_py.into(),
            ohlcv: ohlcv_py.into_iter().map(|df| df.into()).collect(),
            extra_data: extra_data_py
                .into_iter()
                .map(|(k, v)| (k, v.into_iter().map(|df| df.into()).collect()))
                .collect(),
        })
    }
}

/// 测试函数：接收自定义结构体并验证转换
/// 此函数演示如何直接使用 DataFrame，无需 .0 访问
#[pyfunction]
pub fn test_custom_from_py_object(data_dict: CustomProcessedDataDict) -> PyResult<String> {
    // 直接访问 DataFrame，无需使用 .0 访问器
    let ohlcv_count = data_dict.ohlcv.len();
    let mapping_rows = data_dict.mapping.height();
    let skip_mask_cols = data_dict.skip_mask.width();

    // 获取第一个 OHLCV DataFrame 的信息
    let first_df_info = if !data_dict.ohlcv.is_empty() {
        format!(
            "第一个OHLCV: {} 行 × {} 列",
            data_dict.ohlcv[0].height(),
            data_dict.ohlcv[0].width()
        )
    } else {
        "无OHLCV数据".to_string()
    };

    // 获取 extra_data 信息
    let extra_data_info = if data_dict.extra_data.is_empty() {
        "无额外数据".to_string()
    } else {
        format!("额外数据键数: {}", data_dict.extra_data.len())
    };

    Ok(format!(
        "✓ CustomProcessedDataDict 转换成功！\n\
        - OHLCV周期数: {}\n\
        - Mapping行数: {}\n\
        - Skip_mask列数: {}\n\
        - {}\n\
        - {}",
        ohlcv_count, mapping_rows, skip_mask_cols, first_df_info, extra_data_info
    ))
}

#[pyfunction]
pub fn create_dataframe() -> PyResult<PyDataFrame> {
    let df = df![
        PlSmallStr::from_static("column_a") => &[1i64, 2, 5],
        PlSmallStr::from_static("column_b") => &[4i64, 5, 7],
    ]
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(PyDataFrame(df))
}

#[pyfunction]
pub fn process_dataframe(pydf: PyDataFrame) -> PyResult<PyDataFrame> {
    let mut df: DataFrame = pydf.into(); // 转换为 Rust DataFrame

    // 示例处理：添加新列
    df.with_column(Series::new(
        PlSmallStr::from_static("year"),
        vec![2023_i64, 2027],
    ))
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok(PyDataFrame(df)) // 直接返回修改后的 df，无需 clone()
}
