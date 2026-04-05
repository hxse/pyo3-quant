"""场景: 无效的语法 - name/source/offset顺序错误

这个场景应该在运行前就报错，不会执行到手动计算
"""

import polars as pl


def calculate_signals(
    signal_params,
    data_pack,
    result_pack,
    mapped_data_pack,
    mapped_result_pack,
) -> pl.DataFrame:
    """
    这个函数不应该被调用，因为应该在解析或运行阶段就报错
    """
    raise RuntimeError("此场景应该在解析或运行阶段就报错，不应该执行到这里")
