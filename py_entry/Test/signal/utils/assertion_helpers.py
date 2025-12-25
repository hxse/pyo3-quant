"""测试工具函数 - 断言和统计相关"""

import polars as pl


def create_signal_dataframe(
    entry_long: pl.Series,
    exit_long: pl.Series,
    entry_short: pl.Series,
    exit_short: pl.Series,
) -> pl.DataFrame:
    """
    从4个Series创建信号DataFrame

    参数：
        entry_long: 做多入场信号
        exit_long: 做多离场信号
        entry_short: 做空入场信号
        exit_short: 做空离场信号

    返回：
        包含所有信号的DataFrame
    """
    return pl.DataFrame(
        {
            "entry_long": entry_long,
            "exit_long": exit_long,
            "entry_short": entry_short,
            "exit_short": exit_short,
        }
    )


def print_signal_statistics(df: pl.DataFrame, title: str):
    """
    打印信号统计信息

    参数：
        df: 信号DataFrame
        title: 标题
    """
    print(f"\n{title}:")
    for col in ["entry_long", "exit_long", "entry_short", "exit_short"]:
        if col in df.columns:
            count = df[col].sum()
            total = len(df)
            percentage = (count / total * 100) if total > 0 else 0
            print(f"  {col}: {count}/{total} ({percentage:.2f}%)")


def print_comparison_details(
    engine_signals: pl.DataFrame,
    manual_signals: pl.DataFrame,
):
    """
    打印引擎信号和手动信号的对比详情

    参数：
        engine_signals: 引擎生成的信号
        manual_signals: 手动计算的信号
    """
    print("\n=== 信号对比详情 ===")

    for col in ["entry_long", "exit_long", "entry_short", "exit_short"]:
        if col in engine_signals.columns and col in manual_signals.columns:
            engine_col = engine_signals[col]
            manual_col = manual_signals[col]

            # 统计差异
            diff = engine_col != manual_col
            diff_count = diff.sum()

            if diff_count > 0:
                print(f"\n{col} - 发现 {diff_count} 处不一致:")
                diff_indices = diff.arg_true().to_list()
                for idx in diff_indices[:10]:  # 只显示前10个
                    print(
                        f"  索引 {idx}: 引擎={engine_col[idx]}, 手动={manual_col[idx]}"
                    )
                if diff_count > 10:
                    print(f"  ... 还有 {diff_count - 10} 处差异")
            else:
                print(f"{col} - ✓ 完全一致")
