"""
指标测试模块

此模块自动加载 monkey_patch 来解决 pandas_ta 访问器冲突问题。
"""

# 自动加载 monkey_patch，确保 pandas_ta 访问器正常工作
from . import monkey_patch
