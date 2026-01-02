from typing import Self, List, Tuple
from pathlib import Path
from io import BytesIO


from py_entry.types import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
    BacktestSummary,
    ChartConfig,
    OptimizerConfig,
    WalkForwardConfig,
)
from py_entry.io import SaveConfig, UploadConfig, DisplayConfig
from .params import (
    SetupConfig,
    FormatResultsConfig,
    DiagnoseStatesConfig,
)

# 导入拆分后的逻辑模块
from . import config_logic as _config
from . import execution_logic as _exec
from . import result_logic as _result
from . import display as _display
from . import optimizer_logic as _opt
from . import walk_forward_logic as _wf
from . import diagnostics as _diag


class BacktestRunner:
    """回测配置和执行的主类。

    该类采用了代理模式，内部不包含具体的执行逻辑，而是将逻辑委托给各个独立的工具函数模块。
    每个方法都只接收一个 Pydantic 参数对象，以确保参数校验的严谨性和一致性。
    """

    def __init__(self):
        """初始化 BacktestRunner 实例。"""
        self.data_dict: DataContainer | None = None
        self.param_set: ParamContainer | None = None
        self.template_config: TemplateContainer | None = None
        self.engine_settings: SettingContainer | None = None
        self.results: list[BacktestSummary] | None = None

        # 导出使用的缓存数据
        self.export_buffers: List[Tuple[Path, BytesIO]] | None = None
        self.export_zip_buffer: bytes | None = None

        # 导出时选中的索引（同时用于 result 和 param）
        self.export_index: int | None = None

        # 时间测量开关
        self.enable_timing: bool = False

        # 图表配置
        self.chart_config: ChartConfig | None = None

    def setup(self, config: SetupConfig) -> Self:
        """一次性配置回测所需的所有组件。"""
        _config.perform_setup(self, config)
        return self

    def run(self) -> Self:
        """执行回测。"""
        _exec.perform_run(self)
        return self

    def format_results_for_export(self, config: FormatResultsConfig) -> Self:
        """为导出准备结果数据。"""
        _result.format_results_for_export(self, config)
        return self

    def optimize(self, config: OptimizerConfig | None = None):
        """执行参数优化。"""
        return _opt.perform_optimize(self, config)

    def walk_forward(self, config: WalkForwardConfig | None = None):
        """执行向前滚动优化。"""
        return _wf.perform_walk_forward(self, config)

    def save_results(self, config: SaveConfig) -> Self:
        """保存所有回测数据到本地文件。"""
        _result.save_results(self, config)
        return self

    def upload_results(self, config: UploadConfig) -> Self:
        """将所有回测数据上传到服务器。"""
        _result.upload_results(self, config)
        return self

    def display_dashboard(self, config: DisplayConfig | None = None):
        """显示图表仪表盘。"""
        return _display.display_dashboard(self, config)

    def diagnose_states(self, config: DiagnoseStatesConfig) -> dict:
        """诊断回测结果的状态机覆盖情况。"""
        return _diag.perform_diagnose(self, config)
