"""
回测数据导出工具函数

提供导出 BacktestSummary 和 DataContainer 数据为 CSV 文件的功能。
"""

from pathlib import Path
import polars as pl
from typing import Optional

from py_entry.data_conversion.types import BacktestSummary, DataContainer


def _add_index_and_export(df: pl.DataFrame, path: Path, description: str) -> None:
    """为DataFrame添加整数索引并导出"""
    # 添加索引列作为第一列
    df_with_index = df.with_columns([pl.Series("index", range(len(df)))]).select(
        ["index"] + [col for col in df.columns]
    )

    df_with_index.write_csv(path)
    print(f"✅ {description}已导出: {path}")


def export_backtest_data_to_csv(
    backtest_summary: BacktestSummary,
    data_container: DataContainer,
    output_dir: Optional[str] = None,
) -> None:
    """
    导出回测数据到CSV文件

    Args:
        backtest_summary: BacktestSummary对象，包含performance、indicators、signals、backtest_result
        data_container: DataContainer对象，包含mapping、skip_mask、skip_mapping、source
        output_dir: 输出目录，默认为当前脚本所在目录下的data文件夹
    """

    # 确定输出目录
    output_path: Path
    if output_dir is None:
        # 获取调用者的文件路径
        frame = None
        try:
            # 尝试获取调用这个函数的文件路径
            import inspect

            frame = inspect.currentframe()
            if frame is not None and frame.f_back is not None:
                caller_file_path = frame.f_back.f_code.co_filename
                caller_dir = Path(caller_file_path).parent
            else:
                # 如果获取失败，使用当前目录
                caller_dir = Path.cwd()
        except Exception:
            # 如果获取失败，使用当前目录
            caller_dir = Path.cwd()
        finally:
            del frame

        output_path = caller_dir / "data"
    else:
        output_path = Path(output_dir)

    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"开始导出数据到目录: {output_dir}")

    # 导出 BacktestSummary 的各个组件
    if backtest_summary.performance:
        # 导出性能指标
        performance_df = pl.DataFrame(
            [{"metric": k, "value": v} for k, v in backtest_summary.performance.items()]
        )
        performance_path = output_path / "performance.csv"
        _add_index_and_export(performance_df, performance_path, "性能指标")

    if backtest_summary.indicators:
        # 导出指标数据
        for timeframe_name, indicator_dfs in backtest_summary.indicators.items():
            for i, indicator_df in enumerate(indicator_dfs):
                if indicator_df is not None and not indicator_df.is_empty():
                    indicator_path = (
                        output_path / f"indicators_{timeframe_name}_{i}.csv"
                    )
                    _add_index_and_export(
                        indicator_df, indicator_path, f"指标数据({timeframe_name}_{i})"
                    )

    if backtest_summary.signals is not None:
        # 导出交易信号
        signals_path = output_path / "signals.csv"
        _add_index_and_export(backtest_summary.signals, signals_path, "交易信号")

    if backtest_summary.backtest_result is not None:
        # 导出回测结果
        backtest_path = output_path / "backtest_result.csv"
        _add_index_and_export(
            backtest_summary.backtest_result, backtest_path, "回测结果"
        )

    # 导出 DataContainer 的各个组件
    # 导出mapping
    mapping_path = output_path / "data_mapping.csv"
    _add_index_and_export(data_container.mapping, mapping_path, "数据映射")

    # 导出skip_mask
    if data_container.skip_mask is not None:
        skip_mask_path = output_path / "skip_mask.csv"
        skip_mask_df = pl.DataFrame({"skip_mask": data_container.skip_mask})
        _add_index_and_export(skip_mask_df, skip_mask_path, "跳过掩码")

    # 导出skip_mapping
    if data_container.skip_mapping:
        skip_mapping_df = pl.DataFrame(
            [{"key": k, "value": v} for k, v in data_container.skip_mapping.items()]
        )
        skip_mapping_path = output_path / "skip_mapping.csv"
        _add_index_and_export(skip_mapping_df, skip_mapping_path, "跳过映射")

    # 导出source数据
    if data_container.source:
        for source_name, source_dfs in data_container.source.items():
            for i, source_df in enumerate(source_dfs):
                if source_df is not None and not source_df.is_empty():
                    source_path = output_path / f"source_{source_name}_{i}.csv"
                    _add_index_and_export(
                        source_df, source_path, f"源数据({source_name}_{i})"
                    )

    print(f"🎉 数据导出完成！所有文件保存在: {output_path}")
