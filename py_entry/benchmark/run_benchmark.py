import statistics
from typing import Any

from datetime import datetime
from pathlib import Path
from loguru import logger

# Try import runners
try:
    from . import pyo3_quant_runner, vectorbt_runner
    from .config import NUM_BARS_LIST, OPT_SAMPLES_LIST, NUM_RUNS, WARMUP_RUNS
    from .data_utils import generate_ohlcv
except ImportError:
    # Handle running as script from root
    import pyo3_quant_runner  # type: ignore
    import vectorbt_runner  # type: ignore
    from config import NUM_BARS_LIST, OPT_SAMPLES_LIST, NUM_RUNS, WARMUP_RUNS  # type: ignore
    from data_utils import generate_ohlcv  # type: ignore


def run_benchmark():
    # Use Any for flexibility in this script context to avoid union attribute errors
    tests: list[dict[str, Any]] = []
    results: dict[str, list[dict[str, Any]] | str] = {
        "timestamp": datetime.now().isoformat(),
        "tests": tests,
    }

    # 策略列表
    strategies = ["A", "B", "C"]

    # 预生成数据
    logger.info("正在生成测试数据...")
    data_cache = {}
    for num_bars in NUM_BARS_LIST:
        pl_df, pd_df = generate_ohlcv(num_bars)
        data_cache[num_bars] = (pl_df, pd_df)

    for strategy in strategies:
        logger.info(f"\n{'=' * 20} 测试策略 {strategy} {'=' * 20}")

        # 1. 单次回测测试
        for num_bars in NUM_BARS_LIST:
            logger.info(f"--- 单次回测: {num_bars} K线 ---")

            pl_df, pd_df = data_cache[num_bars]

            # 预热
            if WARMUP_RUNS > 0:
                logger.info("正在预热...")
                for _ in range(WARMUP_RUNS):
                    pyo3_quant_runner.run_single_backtest(pl_df, strategy)
                    vectorbt_runner.run_single_backtest(pd_df, strategy)

            # 正式测试
            logger.info(f"运行 pyo3-quant ({NUM_RUNS}次)...")
            pyo3_times = []
            for i in range(NUM_RUNS):
                t = pyo3_quant_runner.run_single_backtest(pl_df, strategy)
                pyo3_times.append(t)
                logger.debug(f"  Run {i + 1}: {t:.6f}s")

            logger.info(f"运行 VectorBT ({NUM_RUNS}次)...")
            vbt_times = []
            for i in range(NUM_RUNS):
                t = vectorbt_runner.run_single_backtest(pd_df, strategy)
                vbt_times.append(t)
                logger.debug(f"  Run {i + 1}: {t:.6f}s")

            p_avg = statistics.mean(pyo3_times)
            v_avg = statistics.mean(vbt_times)
            ratio = v_avg / p_avg if p_avg > 0 else 0

            logger.info(
                f"结果: pyo3-quant={p_avg:.4f}s, VectorBT={v_avg:.4f}s, Ratio={ratio:.2f}x"
            )

            tests.append(
                {
                    "type": "backtest",
                    "strategy": strategy,
                    "num_bars": num_bars,
                    "pyo3_quant": {
                        "avg": p_avg,
                        "std": statistics.stdev(pyo3_times)
                        if len(pyo3_times) > 1
                        else 0,
                    },
                    "vectorbt": {
                        "avg": v_avg,
                        "std": statistics.stdev(vbt_times) if len(vbt_times) > 1 else 0,
                    },
                }
            )

        # 2. 优化测试
        for num_bars in NUM_BARS_LIST:
            for samples in OPT_SAMPLES_LIST:
                logger.info(f"--- 优化测试: {num_bars} K线, {samples} 采样 ---")

                pl_df, pd_df = data_cache[num_bars]

                # 预热
                if WARMUP_RUNS > 0:
                    logger.info("正在预热...")
                    for _ in range(WARMUP_RUNS):
                        # 预热只跑少量采样
                        pyo3_quant_runner.run_optimization(pl_df, 10, strategy)
                        vectorbt_runner.run_optimization(pd_df, 10, strategy)

                # 正式测试
                logger.info(f"运行 pyo3-quant ({NUM_RUNS}次)...")
                pyo3_times = []
                for i in range(NUM_RUNS):
                    t = pyo3_quant_runner.run_optimization(pl_df, samples, strategy)
                    pyo3_times.append(t)
                    logger.debug(f"  Run {i + 1}: {t:.6f}s")

                logger.info(f"运行 VectorBT ({NUM_RUNS}次)...")
                vbt_times = []
                for i in range(NUM_RUNS):
                    t = vectorbt_runner.run_optimization(pd_df, samples, strategy)
                    vbt_times.append(t)
                    logger.debug(f"  Run {i + 1}: {t:.6f}s")

                p_avg = statistics.mean(pyo3_times)
                v_avg = statistics.mean(vbt_times)
                ratio = v_avg / p_avg if p_avg > 0 else 0

                logger.info(
                    f"结果: pyo3-quant={p_avg:.4f}s, VectorBT={v_avg:.4f}s, Ratio={ratio:.2f}x"
                )

                tests.append(
                    {
                        "type": "optimization",
                        "strategy": strategy,
                        "num_bars": num_bars,
                        "samples": samples,
                        "pyo3_quant": {
                            "avg": p_avg,
                            "std": statistics.stdev(pyo3_times)
                            if len(pyo3_times) > 1
                            else 0,
                        },
                        "vectorbt": {
                            "avg": v_avg,
                            "std": statistics.stdev(vbt_times)
                            if len(vbt_times) > 1
                            else 0,
                        },
                    }
                )

    # 生成 Markdown
    generate_markdown(results)
    logger.success("基准测试完成！结果已保存到 doc/benchmark/results.md")


def generate_markdown(results: dict):
    """生成 Markdown 总结文档"""
    md_path = Path(__file__).parents[2] / "doc" / "benchmark" / "results.md"

    lines = [
        "# 性能基准测试结果",
        f"\n测试时间: {results['timestamp'][:16].replace('T', ' ')}",
        "\n> **注**: 比率 = VectorBT耗时 / pyo3-quant耗时。数值越大，说明 pyo3-quant 越快。",
        "\n> **注**: 测试前预生成统一数据源，确保数据完全一致",
        "\n## 1. 单次回测耗时 (Single Backtest)\n",
        "| 策略 | K线数 | pyo3-quant (avg) | VectorBT (avg) | 速度倍数 (Speedup) |",
        "|------|-------|------------------|----------------|--------------------|",
    ]

    for t in results["tests"]:
        if t["type"] == "backtest":
            ratio = (
                t["vectorbt"]["avg"] / t["pyo3_quant"]["avg"]
                if t["pyo3_quant"]["avg"] > 0
                else 0
            )
            if t["strategy"] == "A":
                strat_name = "SMA+TSL (A)"
            elif t["strategy"] == "B":
                strat_name = "EMA+RSI+TSL (B)"
            else:
                strat_name = "无指标 (C)"
            lines.append(
                f"| {strat_name} | {t['num_bars']} | {t['pyo3_quant']['avg']:.4f}s | {t['vectorbt']['avg']:.4f}s | **{ratio:.1f}x** |"
            )

    lines.extend(
        [
            "\n## 2. 优化耗时 (Optimization)\n",
            "| 策略 | K线数 | 采样数 | pyo3-quant (avg) | VectorBT (avg) | 速度倍数 (Speedup) |",
            "|------|-------|--------|------------------|----------------|--------------------|",
        ]
    )

    for t in results["tests"]:
        if t["type"] == "optimization":
            ratio = (
                t["vectorbt"]["avg"] / t["pyo3_quant"]["avg"]
                if t["pyo3_quant"]["avg"] > 0
                else 0
            )
            if t["strategy"] == "A":
                strat_name = "SMA+TSL (A)"
            elif t["strategy"] == "B":
                strat_name = "EMA+RSI+TSL (B)"
            else:
                strat_name = "无指标 (C)"
            lines.append(
                f"| {strat_name} | {t['num_bars']} | {t['samples']} | {t['pyo3_quant']['avg']:.2f}s | {t['vectorbt']['avg']:.2f}s | **{ratio:.1f}x** |"
            )

    md_path.write_text("\n".join(lines))


if __name__ == "__main__":
    run_benchmark()
