"""场景: 非 base source 上使用交叉运算符 - 手写计算

该场景预期在引擎校验阶段直接报错，因此手写计算函数不应被调用。
"""


def calculate_signals(*args, **kwargs):
    raise AssertionError("invalid scenario 不应进入 manual calculator")
