"""
相关性分析工具

使用 Pearson 相关系数分析两个回测引擎的结果一致性
"""

import numpy as np
from scipy import stats
from dataclasses import dataclass


@dataclass
class CorrelationResult:
    """相关性分析结果"""

    equity_r: float  # equity 的 Pearson 相关系数
    drawdown_r: float  # current_drawdown 的 Pearson 相关系数
    pyo3_total_return_pct: float  # pyo3 的总回报率
    btp_total_return_pct: float  # backtesting.py 的总回报率
    total_return_diff: float  # 总回报率差异（绝对值）
    pyo3_final_equity: float  # pyo3 的最终净值
    btp_final_equity: float  # backtesting.py 的最终净值
    pyo3_max_drawdown: float  # pyo3 的最大回撤
    btp_max_drawdown: float  # backtesting.py 的最大回撤
    max_drawdown_diff: float  # 最大回撤差异（绝对值）
    pyo3_trade_count: int  # pyo3 交易次数
    btp_trade_count: int  # btp 交易次数
    pyo3_win_rate: float  # pyo3 胜率
    btp_win_rate: float  # btp 胜率
    analyzed_bars: int  # 实际分析的 Bar 数（截断后）
    total_bars: int  # 原始 Bar 数

    def __str__(self) -> str:
        truncation_msg = ""
        if self.analyzed_bars < self.total_bars:
            truncation_msg = f"\n  (数据已截断: {self.analyzed_bars}/{self.total_bars} bars, 因检测到净值耗尽)"

        return (
            f"相关性分析结果:{truncation_msg}\n"
            f"  equity   相关系数: {self.equity_r:.6f}\n"
            f"  drawdown 相关系数: {self.drawdown_r:.6f}\n"
            f"  pyo3 总回报率:     {self.pyo3_total_return_pct:.4f}%\n"
            f"  btp  总回报率:     {self.btp_total_return_pct:.4f}%\n"
            f"  总回报率差异:      {self.total_return_diff:.4f}%\n"
            f"  pyo3 最终净值:     {self.pyo3_final_equity:.2f}\n"
            f"  btp  最终净值:     {self.btp_final_equity:.2f}\n"
            f"  pyo3 最大回撤:     {self.pyo3_max_drawdown:.4f}%\n"
            f"  btp  最大回撤:     {self.btp_max_drawdown:.4f}%\n"
            f"  最大回撤差异:      {self.max_drawdown_diff:.4f}%\n"
            f"  pyo3 交易次数:     {self.pyo3_trade_count}\n"
            f"  btp  交易次数:     {self.btp_trade_count}\n"
            f"  pyo3 胜率:         {self.pyo3_win_rate:.2f}%\n"
            f"  btp  胜率:         {self.btp_win_rate:.2f}%"
        )


def analyze_correlation(
    pyo3_equity: np.ndarray,
    pyo3_drawdown: np.ndarray,
    pyo3_total_return_pct: float,
    pyo3_trade_count: int,
    pyo3_win_rate: float,
    btp_equity: np.ndarray,
    btp_drawdown: np.ndarray,
    btp_total_return_pct: float,
    btp_trade_count: int,
    btp_win_rate: float,
    initial_capital: float = 10000.0,
) -> CorrelationResult:
    """
    分析两引擎结果的相关性，自动截断因本金耗尽导致的数据

    Args:
        initial_capital: 初始本金，用于判定破产截断
    """
    # 长度对齐（取最小长度）
    min_len = min(
        len(pyo3_equity),
        len(btp_equity),
        len(pyo3_drawdown),
        len(btp_drawdown),
    )

    # 截取相同长度
    pyo3_equity = pyo3_equity[:min_len]
    pyo3_drawdown = pyo3_drawdown[:min_len]
    btp_equity = btp_equity[:min_len]
    btp_drawdown = btp_drawdown[:min_len]

    # === 智能截断逻辑 ===
    # 阈值：本金的 20% (当亏损超过 80% 时，交易行为可能已严重失真)
    threshold = initial_capital * 0.20

    # 寻找第一个低于阈值的索引
    # np.argmax 返回第一个 True 的索引，如果全为 False 返回 0
    # 我们处理全为 False (没破产) 的情况

    pyo3_bankruptcy_idx = np.argmax(pyo3_equity < threshold)
    btp_bankruptcy_idx = np.argmax(btp_equity < threshold)

    cutoff_index = min_len

    # 如果 argmax 返回 0 且第一个元素不小于阈值，说明没破产
    if pyo3_bankruptcy_idx > 0 or (len(pyo3_equity) > 0 and pyo3_equity[0] < threshold):
        cutoff_index = min(
            cutoff_index, pyo3_bankruptcy_idx if pyo3_bankruptcy_idx > 0 else 1
        )  # 至少保留1个点? 不，如果第一个点就挂了...

    # 更稳健的写法：
    # 找到所有 < threshold 的 indices
    pyo3_bad = np.where(pyo3_equity < threshold)[0]
    btp_bad = np.where(btp_equity < threshold)[0]

    if len(pyo3_bad) > 0:
        cutoff_index = min(cutoff_index, pyo3_bad[0])
    if len(btp_bad) > 0:
        cutoff_index = min(cutoff_index, btp_bad[0])

    # 确保至少有足够的点进行相关性分析 (e.g. > 10)
    # 如果截断后数据太少，可能无法计算 Pearson R
    is_truncated = cutoff_index < min_len

    if cutoff_index < 10:
        # 如果一开始就破产，强制使用全部数据（展示惨状），或者只用前10个
        # 但如果真的是一开始就死，相关性也没意义。
        # 我们这里选择如果数据过少，就不截断（fallback），让用户看到低相关性
        if is_truncated:
            cutoff_index = min_len  # Fallback
            # 或者我们可以仅仅给个警告

    # 应用截断
    equity_analysis_len = cutoff_index

    pyo3_equity_slice = pyo3_equity[:equity_analysis_len]
    btp_equity_slice = btp_equity[:equity_analysis_len]
    pyo3_drawdown_slice = pyo3_drawdown[:equity_analysis_len]
    btp_drawdown_slice = btp_drawdown[:equity_analysis_len]

    # 计算 Pearson 相关系数 (使用截断后的数据)
    if len(pyo3_equity_slice) > 1:
        equity_r, _ = stats.pearsonr(pyo3_equity_slice, btp_equity_slice)
        drawdown_r, _ = stats.pearsonr(pyo3_drawdown_slice, btp_drawdown_slice)
    else:
        equity_r = 0.0
        drawdown_r = 0.0

    # 计算总回报率差异 (仍然使用最终结果，因为这是用户关心的)
    # 或者，我们应该比较截断点的回报率？
    # 不，总回报率是对整个回测的评价。即使截断了相关性分析，总回报率还是应该反映真实亏损。
    total_return_diff = abs(pyo3_total_return_pct - btp_total_return_pct)

    # 计算最终净值及其差异 (使用原始数据的最终值)
    pyo3_final_equity = pyo3_equity[-1]
    btp_final_equity = btp_equity[-1]

    # 计算最大回撤 (使用原始数据)
    pyo3_max_drawdown = np.max(pyo3_drawdown) * 100
    btp_max_drawdown = np.max(btp_drawdown) * 100
    max_drawdown_diff = abs(pyo3_max_drawdown - btp_max_drawdown)

    return CorrelationResult(
        equity_r=equity_r,
        drawdown_r=drawdown_r,
        pyo3_total_return_pct=pyo3_total_return_pct,
        btp_total_return_pct=btp_total_return_pct,
        total_return_diff=total_return_diff,
        pyo3_final_equity=pyo3_final_equity,
        btp_final_equity=btp_final_equity,
        pyo3_max_drawdown=pyo3_max_drawdown,
        btp_max_drawdown=btp_max_drawdown,
        max_drawdown_diff=max_drawdown_diff,
        pyo3_trade_count=pyo3_trade_count,
        btp_trade_count=btp_trade_count,
        pyo3_win_rate=pyo3_win_rate,
        btp_win_rate=btp_win_rate,
        analyzed_bars=int(equity_analysis_len),
        total_bars=min_len,
    )
