import numpy as np
from typing import Tuple


GLOBAL_RTOL = 1e-5
GLOBAL_ATOL = 1e-8


def _count_leading_nans(arr: np.ndarray) -> int:
    """
    计算 NumPy 数组开头连续 NaN 值的数量。

    Args:
        arr (np.ndarray): 输入的 NumPy 数组。

    Returns:
        int: 开头连续 NaN 值的数量。
    """
    if arr.size == 0:
        return 0

    # 找到所有非 NaN 值的索引
    non_nan_indices = np.where(~np.isnan(arr))[0]

    if non_nan_indices.size == 0:
        # 如果没有非 NaN 值，则所有元素都是 NaN
        return arr.size
    else:
        # 第一个非 NaN 值的索引就是前导 NaN 的数量
        return non_nan_indices[0]


def get_leading_nan_counts_for_two_arrays(
    arr1: np.ndarray, arr2: np.ndarray
) -> Tuple[int, int]:
    """
    计算两个 NumPy 数组开头 NaN 值的数量。

    Args:
        arr1 (np.ndarray): 第一个 NumPy 数组。
        arr2 (np.ndarray): 第二个 NumPy 数组。

    Returns:
        Tuple[int, int]: 一个元组，包含 arr1 和 arr2 开头 NaN 值的数量。
    """
    nan_count_arr1 = _count_leading_nans(arr1)
    nan_count_arr2 = _count_leading_nans(arr2)
    return nan_count_arr1, nan_count_arr2


def assert_indicator_same(
    array1,
    array2,
    indicator_name,
    indicator_info,
    custom_rtol=GLOBAL_RTOL,
    custom_atol=GLOBAL_ATOL,
    is_nested_call=False,  # 新增参数，用于控制日志输出
):
    """
    通用函数，用于比较 array1 和 array2 实现的指标结果。
    """
    # 只有在非嵌套调用时才打印开始标记
    if not is_nested_call:
        print(f"\n--- 测试开始: {indicator_name} 一致性测试 ---")
        print(f"    indicator_info: {indicator_info}")

    assert len(array1) == len(array2), (
        f"    ❌{indicator_name} length mismatch: array1 {len(array1)} array2 {len(array2)}"
    )

    if array1.dtype == bool or array2.dtype == bool:
        np.testing.assert_array_equal(
            array1,
            array2,
            err_msg=f"    ❌{indicator_name} calculation mismatch for {indicator_info}",
        )
    else:
        valid_indices = ~np.isnan(array1) & ~np.isnan(array2)
        array1_nan_count, array2_nan_count = get_leading_nan_counts_for_two_arrays(
            array1, array2
        )
        assert array1_nan_count == array2_nan_count, (
            f"    ❌{indicator_name} leading NaN count mismatch: array1 has {array1_nan_count} (type: {type(array1).__name__}), array2 has {array2_nan_count} (type: {type(array2).__name__})"
        )

        max_diff = (
            np.max(np.abs(array1[valid_indices] - array2[valid_indices]))
            if np.any(valid_indices)
            else 0.0
        )
        print(f"    {indicator_name} Max difference: {max_diff:.4e}")

        np.testing.assert_allclose(
            array1[valid_indices],
            array2[valid_indices],
            rtol=custom_rtol,
            atol=custom_atol,
            err_msg=f"    ❌{indicator_name} calculation mismatch",
        )

    # 只有在非嵌套调用时才打印结束和通过标记
    if not is_nested_call:
        print(f"    ✅ {indicator_name} accuracy test passed.")
        print(f"--- 测试结束: {indicator_name} 一致性测试 ---")


def assert_indicator_different(array1, array2, indicator_name, indicator_info):
    """
    检测两个指标的结果是否不同。
    """
    print(f"\n--- 测试开始: {indicator_name} 差异性测试 ---")
    print(f"    indicator_info: {indicator_info}")
    try:
        # 调用 assert_indicator_same，并传入 is_nested_call=True
        assert_indicator_same(
            array1, array2, indicator_name, indicator_info, is_nested_call=True
        )
        # 如果没有抛出异常，则说明结果相同，测试失败
        raise AssertionError(
            f"    ❌ {indicator_name} array1 和 array2 被判断为相同，但测试期望是不同，测试失败！"
        )
    except AssertionError as e:
        if "被判断为相同" in str(e):
            # 如果是自定义的失败异常，则重新抛出
            raise e
        else:
            # 如果是 assert_indicator_same 内部的断言失败，则表示符合期望
            print(
                f"    ✅ {indicator_name} array1 和 array2 被判断为不同（符合期望）。"
            )
            print(f"    详细信息: {e}".replace("    ❌", ""))
    finally:
        print(f"--- 测试结束: {indicator_name} 差异性测试 ---")
