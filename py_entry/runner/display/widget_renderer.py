"""
Widget 渲染器 - embed_data=False 模式

使用 anywidget 通过二进制数据传输实现高效的图表显示
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results.run_result import RunResult

from py_entry.io import DisplayConfig
from .chart_widget import ChartDashboardWidget


def render_as_widget(runner: "RunResult", config: DisplayConfig):
    """使用 anywidget 渲染图表仪表盘

    Args:
        runner: RunResult 实例
        config: DisplayConfig 配置对象

    Returns:
        ChartDashboardWidget 实例
    """
    import time
    from loguru import logger

    start_time = time.perf_counter() if runner.enable_timing else None

    # 验证数据存在
    if runner.export_zip_buffer is None:
        raise ValueError(
            "未找到导出的ZIP数据。请先调用 format_results_for_export() 生成数据。"
        )

    # 读取文件内容（如果需要嵌入）
    js_content = ""
    css_content = ""
    if config.embed_files:
        try:
            with open(config.lib_path, "r", encoding="utf-8") as f:
                js_content = f.read()
        except FileNotFoundError:
            logger.error(f"未找到 JavaScript 库文件：{config.lib_path}")

        try:
            with open(config.css_path, "r", encoding="utf-8") as f:
                css_content = f.read()
        except FileNotFoundError:
            logger.error(f"未找到 CSS 文件：{config.css_path}")

    # 创建 widget
    widget = ChartDashboardWidget(
        zip_data=runner.export_zip_buffer,  # 直接传递 bytes，无需 base64 编码
        config=config.override.to_dict() if config.override else {},
        width=config.width,
        aspect_ratio=config.aspect_ratio,
        lib_path=config.lib_path,
        css_path=config.css_path,
        embed_files=config.embed_files,
        js_content=js_content,
        css_content=css_content,
    )

    if runner.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"RunResult.display() [Widget模式] 耗时: {elapsed:.4f}秒")

    return widget
