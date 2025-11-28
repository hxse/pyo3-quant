import sys
import pandas as pd
from pandas.api.extensions import register_dataframe_accessor
from types import ModuleType

# 检查是否已经执行过 monkey patch
if hasattr(pd.DataFrame, "_monkey_patch_applied"):
    print("✅ Monkey patch 已应用，跳过重复执行。")
else:
    # 标记 monkey patch 已应用
    setattr(pd.DataFrame, "_monkey_patch_applied", True)

    # 1. 临时禁用 Accessor 注册：
    # 我们创建一个假的 pandas.api.extensions 模块
    # 它的 register_dataframe_accessor 函数什么也不做。
    class FakeRegister:
        def __init__(self, name):
            # 注册时记录 Accessor 的目标名称，但不执行注册
            self.accessor_name = name

        def __call__(self, cls):
            # 装饰器函数返回原始类，但现在我们知道它的目标注册名了
            return cls

    # 2. 核心：在 sys.modules 中，用我们的 FakeRegister 替换掉原始的 register_dataframe_accessor
    if "pandas_ta_classic" not in sys.modules:
        # 替换 Accessor 机制

        # 查找原始 Accessor 函数
        original_accessor_func = getattr(
            pd.api.extensions, "register_dataframe_accessor"
        )

        # 临时禁用并存储原始函数
        setattr(
            pd.api.extensions,
            "register_dataframe_accessor_ORIGINAL",
            original_accessor_func,
        )
        setattr(pd.api.extensions, "register_dataframe_accessor", FakeRegister)

        try:
            # 导入 AnalysisIndicators 类
            import pandas_ta_classic
            from pandas_ta_classic.core import AnalysisIndicators as TaClassicAccessor

            # 恢复原始 Accessor 机制
            if hasattr(pd.api.extensions, "register_dataframe_accessor_ORIGINAL"):
                setattr(
                    pd.api.extensions,
                    "register_dataframe_accessor",
                    getattr(pd.api.extensions, "register_dataframe_accessor_ORIGINAL"),
                )
                delattr(pd.api.extensions, "register_dataframe_accessor_ORIGINAL")

            print("✅ pandas_ta_classic 模块已加载，Accessors 注册已禁用。")
        except ImportError as e:
            # 如果导入失败，恢复原始机制
            if hasattr(pd.api.extensions, "register_dataframe_accessor_ORIGINAL"):
                setattr(
                    pd.api.extensions,
                    "register_dataframe_accessor",
                    getattr(pd.api.extensions, "register_dataframe_accessor_ORIGINAL"),
                )
                delattr(pd.api.extensions, "register_dataframe_accessor_ORIGINAL")
            print(f"⚠️ 导入 pandas_ta_classic 失败: {e}")
            raise
    else:
        # 模块已经加载，无法阻止注册，只能继续使用继承注册法
        print("⚠️ pandas_ta_classic 模块已在补丁前加载，继续使用继承注册法。")

    # 5. 显式注册 Accessor
    # 无论是否成功阻止了自动注册，我们都使用继承法来显式注册 df.tac

    # 检查是否已经导入过 TaClassicAccessor
    if "TaClassicAccessor" not in locals():
        from pandas_ta_classic.core import AnalysisIndicators as TaClassicAccessor

    # 检查是否已经存在 tac 访问器，避免重复注册
    if not hasattr(pd.DataFrame, "tac"):
        # 显式注册 df.tac
        @register_dataframe_accessor("tac")
        class TacAccessor(TaClassicAccessor):
            pass

    # 6. 正常导入 pandas_ta (旧库)
    # 先检查是否已经存在 ta 访问器，如果存在则先删除
    if hasattr(pd.DataFrame, "ta"):
        delattr(pd.DataFrame, "ta")

    import pandas_ta  # 旧库，它会正常注册 df.ta

    print("✅ df.tac 访问器已创建，df.ta 指向 pandas_ta。")
