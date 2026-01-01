"""
显示模块 - 统一入口

根据 embed_data 参数路由到不同的渲染实现：
- embed_data=True: HTML 嵌入模式（html_renderer）
- embed_data=False: anywidget 模式（widget_renderer）
"""

from typing import TYPE_CHECKING, Union
from IPython.display import HTML

if TYPE_CHECKING:
    from ..runner import BacktestRunner
    from .chart_widget import ChartDashboardWidget

from py_entry.io import DisplayConfig
from .html_renderer import render_as_html
from .widget_renderer import render_as_widget


def display_dashboard(
    runner: "BacktestRunner", config: DisplayConfig
) -> Union[HTML, "ChartDashboardWidget"]:
    """显示图表仪表盘（支持两种模式）

    Args:
        runner: BacktestRunner 实例
        config: DisplayConfig 配置对象

    Returns:
        HTML 对象（embed_data=True）或 ChartDashboardWidget 对象（embed_data=False）
    """
    if config.embed_data:
        # 模式 1: HTML 嵌入模式
        return render_as_html(runner, config)
    else:
        # 模式 2: anywidget 模式
        return render_as_widget(runner, config)


# 导出所有公开接口
__all__ = ["display_dashboard"]
