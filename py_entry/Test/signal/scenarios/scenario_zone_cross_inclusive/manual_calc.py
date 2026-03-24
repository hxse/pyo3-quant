"""场景: 非法区间穿越 - 手写计算

该场景预期在解析阶段直接报错，因此不应进入手写计算。
"""


def calculate_signals(*args, **kwargs):
    raise AssertionError("invalid scenario 不应进入 manual calculator")
