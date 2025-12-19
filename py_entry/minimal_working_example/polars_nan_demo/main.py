try:
    from . import basics
    from . import operations
    from . import stats
    from . import dataframe_tests
    from . import scenarios
except ImportError:
    # Allow running as a script directly
    import basics  # type: ignore
    import operations  # type: ignore
    import stats  # type: ignore
    import dataframe_tests  # type: ignore
    import scenarios  # type: ignore


def print_summary_part5():
    # ==================== Part 5: 对比总结 ====================
    print("\n" + "━" * 50)
    print("Part 5: NaN vs null 行为对比总结")
    print("━" * 50 + "\n")

    print("┌─────────────────────┬────────────────┬────────────────┐")
    print("│ 特性                │ NaN            │ null           │")
    print("├─────────────────────┼────────────────┼────────────────┤")
    print("│ null_count()        │ 0 (不算null)   │ 计入统计       │")
    print("│ is_null()           │ false          │ true           │")
    print("│ is_nan()            │ true           │ false          │")
    print("│ 正常值 < 特殊值      │ true (NaN最大) │ null (传播)    │")
    print("│ 特殊值 == 特殊值     │ true           │ null (传播)    │")
    print("│ drop_nulls()        │ ❌ 保留         │ ✅ 删除        │")
    print("│ drop_nans()         │ ✅ 删除         │ ❌ 保留        │")
    print("│ fill_null()         │ ❌ 无效         │ ✅ 有效        │")
    print("│ fill_nan()          │ ✅ 有效         │ ❌ 无效        │")
    print("│ forward_fill()      │ ❌ 无效         │ ✅ 有效        │")
    print("│ interpolate()       │ ❌ 无效         │ ✅ 有效        │")
    print("│ 使用场景            │ 未定义数值结果  │ 真正缺失数据   │")
    print("└─────────────────────┴────────────────┴────────────────┘")
    print()
    print("关键差异:")
    print("  • NaN: Polars将其视为'最大值',比较返回确定的true/false")
    print("  • null: 比较结果传播null,保持'未知'状态")
    print("  • NaN 和 null 有各自独立的检测、删除、填充方法")
    print("  • 要同时处理 NaN 和 null，需要分别调用对应的方法")
    print()
    print("常用处理模式:")
    print("  1. 统一转换：series.fill_nan(None)  # 将 NaN 转为 null")
    print("  2. 分别填充：series.fill_nan(value1).fill_null(value2)")
    print("  3. 全部删除：series.drop_nans().drop_nulls()")
    print("  4. 插值处理：series.fill_nan(None).interpolate()")
    print()
    print("⚠️  这解释了为什么信号生成器会出现问题:")
    print("   当 sma_0 有值而 sma_1 是 NaN 时，")
    print("   比如 100.0 < NaN 会被判断为 true (因为 NaN 被视为最大值)，")
    print("   从而错误地触发了信号！")


def print_summary_part10():
    # ==================== Part 10: 最佳实践总结 ====================
    print("\n" + "━" * 50)
    print("Part 10: 测试总结与最佳实践")
    print("━" * 50 + "\n")

    print("📊 统计方法对比:")
    print("┌──────────────────────┬─────────────────────────────────────┐")
    print("│ 统计目标             │ 推荐方法                            │")
    print("├──────────────────────┼─────────────────────────────────────┤")
    print("│ null 数量            │ series.null_count()                 │")
    print("│ NaN 数量             │ series.is_nan().fill_null(False).sum() │")
    print("│ 有效值数量           │ len(series) - null_count - nan_count│")
    print("│ DataFrame null 统计  │ df.null_count()                     │")
    print("│ DataFrame NaN 统计   │ 遍历列使用 is_nan().fill_null(False)│")
    print("└──────────────────────┴─────────────────────────────────────┘")
    print()

    print("🎯 信号生成最佳实践:")
    print("  1️⃣  总是检测并过滤 NaN 和 null")
    print("  2️⃣  使用 is_nan().fill_null(False) 避免 null 传播")
    print("  3️⃣  比较结果使用 fill_null(False) 处理 null 传播")
    print("  4️⃣  在 DataFrame 中使用表达式，可读性和性能更好")
    print()

    print("🔧 代码模式:")
    print("```python")
    print("# 单列检测特殊值")
    print("has_special = (")
    print("    series.is_nan().fill_null(False) | series.is_null()")
    print(")")
    print()
    print("# 信号生成(双列比较)")
    print("signal = (")
    print("    (left < right).fill_null(False)  # 处理 null 传播")
    print("    & ~(left.is_nan().fill_null(False) | left.is_null())")
    print("    & ~(right.is_nan().fill_null(False) | right.is_null())")
    print(")")
    print("```")
    print()


def main():
    print("=== 测试 Polars 中 NaN 和 null 的比较行为 ===\n")

    basics.run_nan_tests()
    basics.run_null_tests()
    basics.run_mixed_tests()

    operations.run_fill_tests()

    print_summary_part5()

    stats.run_count_tests()

    dataframe_tests.run_dataframe_tests()

    stats.run_edge_case_tests()

    scenarios.run_signal_scenario()

    print_summary_part10()


if __name__ == "__main__":
    main()
