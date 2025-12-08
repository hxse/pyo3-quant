from typing import Self, Dict, Any, Optional
from IPython.display import HTML

from py_entry.data_conversion.types import (
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    SignalTemplate,
    BacktestSummary,
)
from py_entry.data_conversion.data_generator import (
    OtherParams,
    DataSourceConfig,
)
from py_entry.data_conversion.file_utils import (
    ResultBuffersCache,
    SaveConfig,
    UploadConfig,
)

# 导入拆分后的逻辑模块
from . import config_logic as _config
from . import execution_logic as _exec
from . import result_logic as _result
from . import display_utils as _display


class BacktestRunner:
    """回测配置和执行的主类。

    该类提供了简洁的配置方式：
    使用 setup() 方法一次性配置所有组件

    配置完成后，调用 run() 方法执行回测。
    """

    def __init__(self, enable_timing: bool = False):
        """初始化 BacktestRunner 实例。

        设置所有内部状态变量为 None，表示尚未进行任何配置。

        Args:
            enable_timing: 是否启用时间测量和日志记录
        """
        self.data_dict: DataContainer | None = None
        self.param_set: ParamContainer | None = None
        self.template_config: TemplateContainer | None = None
        self.engine_settings: SettingContainer | None = None
        self.results: list[BacktestSummary] | None = None
        # 缓存不同格式的转换结果
        self._buffers_cache: ResultBuffersCache = ResultBuffersCache()
        # 时间测量开关
        self.enable_timing = enable_timing

    def setup(
        self,
        data_source: DataSourceConfig | None = None,
        other_params: OtherParams | None = None,
        indicators_params: IndicatorsParams | None = None,
        signal_params: SignalParams | None = None,
        backtest_params: BacktestParams | None = None,
        performance_params: PerformanceParams | None = None,
        signal_template: SignalTemplate | None = None,
        engine_settings: SettingContainer | None = None,
        param_set_size: int = 1,
    ) -> Self:
        """一次性配置回测所需的所有组件"""
        # 使用 **locals() 收集所有参数，'self' 自动匹配 perform_setup 的第一个参数 'self'
        _config.perform_setup(**locals())
        return self

    def run(self) -> Self:
        """执行回测。"""
        _exec.perform_run(**locals())
        return self

    def _ensure_buffers_cache(self, dataframe_format: str) -> None:
        """确保指定格式的buffers已缓存。"""
        _result._ensure_buffers_cache(**locals())

    def save_results(
        self,
        config: SaveConfig,
    ) -> Self:
        """保存所有回测数据（包括配置和结果）到本地文件。"""
        _result.save_results(**locals())
        return self

    def upload_results(
        self,
        config: UploadConfig,
    ) -> Self:
        """将所有回测数据（包括配置和结果）打包并上传到服务器。"""
        _result.upload_results(**locals())
        return self

    def format_results_for_export(
        self,
        add_index: bool = True,
        add_time: bool = True,
        add_date: bool = True,
    ) -> Self:
        """为所有 DataFrame 添加列"""
        _result.format_results_for_export(**locals())
        return self

    def get_zip_buffer(
        self,
        dataframe_format: str = "csv",
        compress_level: int = 1,
    ) -> bytes:
        """获取回测结果的ZIP压缩包字节数据。"""
        return _result.get_zip_buffer(**locals())

    def display_dashboard(
        self,
        config: Dict[str, Any],
        dataframe_format: str = "csv",
        compress_level: int = 1,
        lib_path: str = "../lwchart/chart-dashboard.umd.js",
        css_path: str = "../lwchart/lwchart_demo3.css",
        embed_files: bool = True,
        container_id: Optional[str] = None,
    ) -> HTML:
        """
        获取回测结果的 ZIP 压缩包字节数据，并将其加载到 ChartDashboard 组件中。

        Args:
            config: ChartDashboard 的配置字典。
            dataframe_format: DataFrame格式，"csv" 或 "parquet"。
            compress_level: 压缩级别，0-9。
            lib_path: UMD JavaScript 库文件的路径。
            css_path: CSS 文件的路径。
            embed_files: 是否将 JS/CSS 文件内容读取并嵌入到 HTML 中（自包含）。
            container_id: 可选参数。用于渲染图表的 HTML 容器 ID。

        Returns:
            HTML: IPython.display.HTML 对象，用于在 Jupyter 中渲染图表。
        """
        # 委托给 display_utils 中的 display_dashboard 工具函数
        return _display.display_dashboard(**locals())
