"""
ChartDashboardWidget - 使用 anywidget 实现的图表仪表盘组件

通过 Jupyter Widgets 协议进行二进制数据传输，无需 base64 编码。
"""

import anywidget
import traitlets
from typing import Dict, Any
from pathlib import Path


class ChartDashboardWidget(anywidget.AnyWidget):
    """图表仪表盘 Widget

    使用 anywidget 实现，支持高效的二进制数据传输。
    数据通过 traitlets.Bytes 传输，无需 base64 编码，性能优于传统方式约 33%。
    """

    # 二进制 ZIP 数据（自动在 Python 和 JavaScript 之间传输）
    zip_data = traitlets.Bytes().tag(sync=True)

    # 仪表盘配置
    config = traitlets.Dict(default_value={}).tag(sync=True)

    # 容器样式配置
    width = traitlets.Unicode(default_value="100%").tag(sync=True)
    aspect_ratio = traitlets.Unicode(default_value="16/9").tag(sync=True)

    # 库和样式路径
    lib_path = traitlets.Unicode(default_value="../lwchart/chart-dashboard.umd.js").tag(
        sync=True
    )
    css_path = traitlets.Unicode(default_value="../lwchart/lwchart_demo3.css").tag(
        sync=True
    )
    embed_files = traitlets.Bool(default_value=True).tag(sync=True)

    # 嵌入的文件内容
    js_content = traitlets.Unicode(default_value="").tag(sync=True)
    css_content = traitlets.Unicode(default_value="").tag(sync=True)

    # JavaScript 模块（ESM）
    _esm = Path(__file__).parent / "chart_widget.js"

    # CSS 样式
    _css = Path(__file__).parent / "chart_widget.css"

    def __init__(
        self,
        *,
        zip_data: bytes,
        config: Dict[str, Any],
        width: str = "100%",
        aspect_ratio: str = "16/9",
        lib_path: str = "",
        css_path: str = "",
        embed_files: bool = True,
        js_content: str = "",
        css_content: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            zip_data=zip_data,
            config=config,
            width=width,
            aspect_ratio=aspect_ratio,
            lib_path=lib_path,
            css_path=css_path,
            embed_files=embed_files,
            js_content=js_content,
            css_content=css_content,
            **kwargs,
        )
