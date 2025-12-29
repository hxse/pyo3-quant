"""测试工具函数 - 比较计算相关"""

import polars as pl
import math


def compare_series(
    left: pl.Series,
    right: pl.Series | float,
    op: str,
    offset_left: int = 0,
    offset_right: int = 0,
    fill_null: bool = True,
) -> pl.Series:
    """
    通用的序列比较函数

    参数：
        left: 左操作数
        right: 右操作数（Series或标量）
        op: 运算符 (">", "<", ">=", "<=", "==", "!=")
        offset_left: 左操作数偏移
        offset_right: 右操作数偏移
        fill_null: 是否将空值填充为False (默认True)

    返回：
        布尔Series，表示比较结果
    """
    # 应用偏移
    if offset_left > 0:
        left = left.shift(offset_left)
    if isinstance(right, pl.Series) and offset_right > 0:
        right = right.shift(offset_right)

    # 计算无效掩码 (NaN 或 Null)
    # 逻辑与Rust一致: (is_nan | is_null) -> True 表示无效

    left_invalid = left.is_nan() | left.is_null()

    if isinstance(right, pl.Series):
        right_invalid = right.is_nan() | right.is_null()
        total_invalid = left_invalid | right_invalid
    else:
        # 标量情况
        if math.isnan(right):
            # 如果标量是NaN，所有结果都视为无效(False)
            return pl.Series([False] * len(left), dtype=pl.Boolean)
        total_invalid = left_invalid

    # 执行比较
    if op == ">":
        res = left > right
    elif op == "<":
        res = left < right
    elif op == ">=":
        res = left >= right
    elif op == "<=":
        res = left <= right
    elif op == "==":
        res = left == right
    elif op == "!=":
        res = left != right
    else:
        raise ValueError(f"Unknown operator: {op}")

    # 过滤无效值
    # 注意: invalid 为 True 的地方，结果强制为 False
    # ~invalid 为 False，res & False -> False
    res = res & (~total_invalid)

    if fill_null:
        return res.fill_null(False)
    return res


def compare_param(
    left: pl.Series,
    param_value: float,
    op: str,
    offset_left: int = 0,
) -> pl.Series:
    """
    与参数值比较的便捷函数

    参数：
        left: 左操作数
        param_value: 参数值
        op: 运算符
        offset_left: 左操作数偏移
    """
    return compare_series(left, param_value, op, offset_left, 0)


def compare_crossover(
    left: pl.Series,
    right: pl.Series | float,
    op: str,
) -> pl.Series:
    """
    交叉比较：当前满足条件 AND 前值有效 AND 前值不满足

    参数：
        left: 左操作数
        right: 右操作数
        op: 基础运算符 (">", "<", ">=", "<=", "==", "!=")

    返回：
        布尔Series，表示交叉发生

    示例：
        x> : 当前 > right AND 前值有效 AND 前值 <= right

    注意：
        如果前一个值是 NaN 或 Null，即使当前值满足条件，也不会触发交叉信号。
        这确保了交叉信号仅在发生真实的状态转换时触发，而不是在数据预热期结束后立即触发。
    """
    # 1. 计算当前状态
    current = compare_series(left, right, op, offset_left=0, fill_null=False)

    # 2. 计算前值状态（通过位移 left 和 right）
    prev_left = left.shift(1)
    if isinstance(right, pl.Series):
        prev_right = right.shift(1)
    else:
        prev_right = right

    prev = compare_series(prev_left, prev_right, op, offset_left=0, fill_null=False)

    # 3. 计算前值的有效性掩码（前值的 left 和 right 都不是 NaN/Null）
    prev_left_invalid = prev_left.is_nan() | prev_left.is_null()
    if isinstance(prev_right, pl.Series):
        prev_right_invalid = prev_right.is_nan() | prev_right.is_null()
        prev_invalid = prev_left_invalid | prev_right_invalid
    else:
        if math.isnan(prev_right):
            prev_invalid = pl.Series([True] * len(left), dtype=pl.Boolean)
        else:
            prev_invalid = prev_left_invalid

    prev_valid = ~prev_invalid

    # 4. 交叉 = 当前满足 & 前值有效 & 前值不满足
    # 只有当前值满足条件、前值有效（非 NaN/Null）且前值不满足条件时才触发
    return (current & prev_valid & ~prev).fill_null(False)


def combine_and(*conditions: pl.Series) -> pl.Series:
    """
    AND逻辑组合多个条件

    参数：
        *conditions: 多个布尔Series

    返回：
        所有条件都满足的布尔Series
    """
    from functools import reduce

    return reduce(lambda a, b: a & b, conditions)


def combine_or(*conditions: pl.Series) -> pl.Series:
    """
    OR逻辑组合多个条件

    参数：
        *conditions: 多个布尔Series

    返回：
        任一条件满足的布尔Series
    """
    from functools import reduce

    return reduce(lambda a, b: a | b, conditions)
