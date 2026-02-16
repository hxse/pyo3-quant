"""
Marimo 渲染器 - target="marimo" 模式

复用 anywidget 渲染器，外层用 mo.ui.anywidget() 包装。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results.run_result import RunResult
    from marimo._plugins.ui._impl.from_anywidget import anywidget as MarimoAnyWidget

from py_entry.io import DisplayConfig
from .widget_renderer import render_as_widget


def render_as_marimo_widget(
    runner: "RunResult", config: DisplayConfig
) -> "MarimoAnyWidget":
    """使用 marimo anywidget 渲染图表仪表盘

    Args:
        runner: RunResult 实例
        config: DisplayConfig 配置对象

    Returns:
        marimo anywidget 包装后的 widget
    """
    try:
        import marimo as mo
    except ImportError:
        raise ImportError("target='marimo' 需要安装 marimo：pip install marimo")

    widget = render_as_widget(runner, config)
    return mo.ui.anywidget(widget)
