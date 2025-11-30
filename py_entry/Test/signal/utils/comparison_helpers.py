"""测试工具函数 - 比较计算相关"""

import polars as pl


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
    交叉比较：当前满足条件 AND 前值不满足

    参数：
        left: 左操作数
        right: 右操作数
        op: 基础运算符 (">", "<", ">=", "<=", "==", "!=")

    返回：
        布尔Series，表示交叉发生

    示例：
        x> : 当前 > right AND 前值 <= right
    """
    # 1. 计算当前状态 (保留Null)
    current = compare_series(left, right, op, offset_left=0, fill_null=False)

    # 2. 获取前一状态 (shift 1, 保留Null)
    # 注意：shift(1) 会引入 Null，compare_series(fill_null=False) 会保留这些 Null
    # 这样 ~prev 在 Null 处仍为 Null，current & Null -> Null
    # 从而自动处理了边界情况，无需显式检查 prev_valid
    prev = current.shift(1)

    # 3. 交叉 = 当前满足 & 前值不满足
    # 结果中前 N 行将为 Null (而非 False)，这与 Rust 行为一致
    # 但最终输出需要是布尔值 (Rust 引擎似乎最终输出了 False)
    return (current & ~prev).fill_null(False)


def combine_and(*conditions: pl.Series) -> pl.Series:
    """
    AND逻辑组合多个条件

    参数：
        *conditions: 多个布尔Series

    返回：
        所有条件都满足的布尔Series
    """
    result = conditions[0]
    for cond in conditions[1:]:
        result = result & cond
    return result


def combine_or(*conditions: pl.Series) -> pl.Series:
    """
    OR逻辑组合多个条件

    参数：
        *conditions: 多个布尔Series

    返回：
        任一条件满足的布尔Series
    """
    result = conditions[0]
    for cond in conditions[1:]:
        result = result | cond
    return result
