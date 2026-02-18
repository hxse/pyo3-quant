import time
from loguru import logger

from py_entry.io import SaveConfig, UploadConfig
from py_entry.runner import Backtest, FormatResultsConfig, RunResult
from py_entry.strategies import get_strategy
from py_entry.strategies.base import StrategyConfig


def get_custom_backtest_config() -> StrategyConfig:
    """
    获取 custom_backtest 示例的完整策略配置。

    说明：
    1. example 层对外提供统一的 StrategyConfig 入口；
    2. notebook/CLI 都应复用该入口，避免策略来源分叉。
    """
    return get_strategy("mtf_bbands_rsi_sma")


def run_custom_backtest(
    *,
    config: StrategyConfig | None = None,
    save_result: bool = False,
    upload_result: bool = False,
) -> RunResult:
    """
    运行 custom_backtest 示例流程。

    说明：
    1. 示例层不再维护策略细节；
    2. 统一从公共策略注册表读取 `mtf_bbands_rsi_sma`。
    """
    start_time = time.perf_counter()
    logger.info("开始执行回测流程")

    # 统一复用 StrategyConfig：未传入时使用默认示例配置。
    cfg = config if config is not None else get_custom_backtest_config()

    bt = Backtest(
        enable_timing=True,
        data_source=cfg.data_config,
        indicators=cfg.indicators_params,
        signal=cfg.signal_params,
        backtest=cfg.backtest_params,
        performance=cfg.performance_params,
        signal_template=cfg.signal_template,
        engine_settings=cfg.engine_settings,
    )

    # 图表展示依赖导出缓存，因此统一先格式化。
    result = bt.run().format_for_export(FormatResultsConfig(dataframe_format="csv"))

    if save_result:
        result.save(SaveConfig(output_dir="my_strategy"))

    # 默认关闭副作用；仅在显式开启时尝试上传。
    if upload_result:
        try:
            from py_entry.io import load_local_config

            request_cfg = load_local_config()
            logger.info("正在上传结果...")
            result.upload(
                UploadConfig(
                    request_config=request_cfg,
                    server_dir="my_strategy",
                    zip_name="results.zip",
                )
            )
        except FileNotFoundError:
            logger.warning("跳过上传：未找到配置文件 config.json")
        except Exception as e:
            logger.error(f"上传失败: {e}")

    if result.summary:
        logger.info(f"performance: {result.summary.performance}")

    logger.info(f"总耗时 {time.perf_counter() - start_time:.4f}秒")
    return result


def format_result_for_ai(result: RunResult, elapsed_seconds: float) -> str:
    """将回测结果整理为便于 AI 读取的纯文本摘要。"""
    lines: list[str] = []
    lines.append("=== CUSTOM_BACKTEST_RESULT ===")
    lines.append(f"elapsed_seconds={elapsed_seconds:.4f}")

    if result.summary is None:
        lines.append("summary=None")
    else:
        lines.append("summary=present")
        lines.append(f"performance={result.summary.performance}")

    return "\n".join(lines)


if __name__ == "__main__":
    # 脚本直跑场景仅用于结果阅读，默认禁用保存/上传副作用。
    main_start_time = time.perf_counter()
    main_cfg = get_custom_backtest_config()
    main_result = run_custom_backtest(
        config=main_cfg,
        save_result=False,
        upload_result=False,
    )
    main_elapsed_seconds = time.perf_counter() - main_start_time
    print(format_result_for_ai(main_result, main_elapsed_seconds))
