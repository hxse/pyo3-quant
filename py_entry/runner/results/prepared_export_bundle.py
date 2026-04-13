from __future__ import annotations

import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from py_entry.io import DisplayConfig, SaveConfig, UploadConfig
from py_entry.io import save_backtest_results, upload_backtest_results

if TYPE_CHECKING:
    from IPython.display import HTML
    from marimo._plugins.ui._impl.from_anywidget import anywidget as MarimoAnyWidget

    from py_entry.runner.display.chart_widget import ChartDashboardWidget
    from py_entry.types import ChartConfig


@dataclass(slots=True)
class PreparedExportBundle:
    """正式导出 bundle。"""

    buffers: list[tuple[Path, BytesIO]]
    zip_buffer: bytes
    chart_config: "ChartConfig | None"
    enable_timing: bool = False

    def save(self, config: SaveConfig) -> "PreparedExportBundle":
        """保存 bundle 到本地。"""
        start_time = time.perf_counter() if self.enable_timing else None
        save_backtest_results(buffers=self.buffers, config=config)
        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"PreparedExportBundle.save() 耗时: {elapsed:.4f}秒")
        return self

    def upload(self, config: UploadConfig) -> "PreparedExportBundle":
        """上传 bundle 到远端。"""
        start_time = time.perf_counter() if self.enable_timing else None
        upload_backtest_results(zip_data=self.zip_buffer, config=config)
        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"PreparedExportBundle.upload() 耗时: {elapsed:.4f}秒")
        return self

    def display(
        self, config: DisplayConfig | None = None
    ) -> "HTML | ChartDashboardWidget | MarimoAnyWidget":
        """显示 bundle 对应图表。"""
        from py_entry.runner import display as _display

        return _display.display_dashboard(self, config)
