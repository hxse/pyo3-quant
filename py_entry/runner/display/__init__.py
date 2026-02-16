"""
显示模块 - 统一入口

根据 target 和 embed_data 参数路由到不同的渲染实现：
- target="marimo": Marimo anywidget 模式（marimo_renderer）
- target="jupyter" + embed_data=True: HTML 嵌入模式（html_renderer）
- target="jupyter" + embed_data=False: anywidget 模式（widget_renderer）
"""

from typing import TYPE_CHECKING, Union, Optional
from IPython.display import HTML

from py_entry.io import DisplayConfig

if TYPE_CHECKING:
    from ..results.run_result import RunResult
    from .chart_widget import ChartDashboardWidget
    from marimo._plugins.ui._impl.from_anywidget import anywidget as MarimoAnyWidget
from .html_renderer import render_as_html
from .widget_renderer import render_as_widget


def display_dashboard(
    runner: "RunResult",
    config: Optional[DisplayConfig] = None,
) -> Union[HTML, "ChartDashboardWidget", "MarimoAnyWidget"]:
    """显示图表仪表盘（支持多种模式）

    Args:
        runner: RunResult 实例
        config: DisplayConfig 包含配置对象
    """
    config = config or DisplayConfig()

    if config.target == "marimo":
        from .marimo_renderer import render_as_marimo_widget

        return render_as_marimo_widget(runner, config)

    if config.embed_data:
        # Jupyter 模式 1: HTML 嵌入模式
        return render_as_html(runner, config)
    else:
        # Jupyter 模式 2: anywidget 模式
        return render_as_widget(runner, config)


# 导出所有公开接口
__all__ = ["display_dashboard"]
