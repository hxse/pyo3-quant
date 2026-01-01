from typing import Self, List, Tuple, Optional
from pathlib import Path
from io import BytesIO


from py_entry.types import (
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
    OptimizerConfig,
    WalkForwardConfig,
    ChartConfig,
)
from py_entry.data_generator import (
    OtherParams,
    DataSourceConfig,
)
from py_entry.io import (
    SaveConfig,
    UploadConfig,
    DisplayConfig,
    ParquetCompression,
)

# 导入拆分后的逻辑模块
from . import config_logic as _config
from . import execution_logic as _exec
from . import result_logic as _result
from . import display as _display
from . import optimization_logic as _opt


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

        # 导出使用的缓存数据
        self.export_buffers: List[Tuple[Path, BytesIO]] | None = None
        self.export_zip_buffer: bytes | None = None

        # 导出时选中的索引（同时用于 result 和 param）
        self.export_index: int | None = None

        # 时间测量开关
        self.enable_timing = enable_timing

        # 图表配置
        self.chart_config: ChartConfig | None = None

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
        _exec.perform_run(self)
        return self

    def format_results_for_export(
        self,
        export_index: int,
        dataframe_format: str = "csv",
        compress_level: int = 1,
        parquet_compression: ParquetCompression = "zstd",
        chart_config: Optional[ChartConfig] = None,
        add_index: bool = True,
        add_time: bool = True,
        add_date: bool = True,
    ) -> Self:
        """
        为导出准备结果数据。
        """
        _result.format_results_for_export(**locals())
        return self

    def optimize(
        self,
        config: Optional[OptimizerConfig] = None,
    ):
        """
        执行参数优化。

        这是对 Optimizer 类的便捷封装，使用当前已配置的数据和模板。
        """
        return _opt.perform_optimize(self, config)

    def walk_forward(
        self,
        config: Optional[WalkForwardConfig] = None,
    ):
        """
        执行向前滚动优化 (Walk Forward Optimization)。
        """
        return _opt.perform_walk_forward(self, config)

    def save_results(
        self,
        config: SaveConfig,
    ) -> Self:
        """保存所有回测数据（包括配置和结果）到本地文件。"""
        _result.save_results(self, config)
        return self

    def upload_results(
        self,
        config: UploadConfig,
    ) -> Self:
        """将所有回测数据（包括配置和结果）打包并上传到服务器。"""
        _result.upload_results(self, config)
        return self

    def display_dashboard(
        self,
        config: DisplayConfig,
    ):
        """
        获取回测结果的 ZIP 压缩包字节数据，并将其加载到 ChartDashboard 组件中。

        Returns:
            HTML 对象（embed_data=True）或 ChartDashboardWidget 对象（embed_data=False）
        """
        return _display.display_dashboard(self, config)

    def diagnose_states(
        self,
        result_index: int = 0,
        print_summary: bool = True,
    ) -> dict:
        """
        诊断回测结果的状态机覆盖情况

        分析回测是否覆盖全部 11 种状态机状态，帮助快速验证策略的健壮性。

        Args:
            result_index: 回测结果索引（多参数集时使用）
            print_summary: 是否打印摘要信息

        Returns:
            dict: 包含状态分布信息的字典：
                - found_states: 找到的状态列表
                - missing_states: 缺失的状态列表
                - distribution: 各状态的计数
                - coverage: 覆盖比例 (found/11)
                - is_complete: 是否覆盖全部 11 种状态

        Example:
            >>> br = BacktestRunner().setup(...).run()
            >>> result = br.diagnose_states()
            >>> if result["is_complete"]:
            ...     print("✅ 全部 11 种状态已覆盖")
        """
        from . import diagnostics as _diag

        if print_summary:
            _diag.print_state_summary(self, result_index)

        return _diag.analyze_state_distribution(self, result_index)
