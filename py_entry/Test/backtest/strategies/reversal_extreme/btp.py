from typing import cast, Sequence
from backtesting import Strategy
from backtesting.lib import crossover
import talib
from .config import CONFIG as C

size = 0.99


class ReversalExtremeBtp(Strategy):
    def init(self):
        # Indicators
        self.bbands_upper, self.bbands_middle, self.bbands_lower = self.I(
            talib.BBANDS,
            self.data.Close,
            timeperiod=C.bbands_period,
            nbdevup=C.bbands_std,
            nbdevdn=C.bbands_std,
            matype=0,
        )
        self.atr = self.I(
            talib.ATR,
            self.data.High,
            self.data.Low,
            self.data.Close,
            timeperiod=C.atr_period,
        )

        # Risk State - 独立追踪 TSL，不更新 trade.sl
        self.extremum = None  # To track highest/lowest since entry for TSL
        self.tsl_price = None  # 独立的 TSL 价格，与 Pyo3 一致

    def _get_signals(self):
        # 1. Generate Raw Signals
        # Entry
        entry_long_signal = crossover(
            cast(Sequence, self.data.Close), cast(Sequence, self.bbands_middle)
        )
        entry_short_signal = crossover(
            cast(Sequence, self.bbands_middle), cast(Sequence, self.data.Close)
        )

        # Exit (Signal generation independent of position - Pyo3 compatible)
        # exit_long: x> upper OR x< middle (reversal)
        exit_long_signal = crossover(
            cast(Sequence, self.data.Close), cast(Sequence, self.bbands_upper)
        ) or crossover(
            cast(Sequence, self.bbands_middle), cast(Sequence, self.data.Close)
        )
        # exit_short: x< lower OR x> middle (reversal)
        exit_short_signal = crossover(
            cast(Sequence, self.bbands_lower), cast(Sequence, self.data.Close)
        ) or crossover(
            cast(Sequence, self.data.Close), cast(Sequence, self.bbands_middle)
        )

        # 2. Apply Pyo3 Cleaning Rules (R1-R3)
        # R1: Conflict Entry -> Both False
        if entry_long_signal and entry_short_signal:
            entry_long_signal = False
            entry_short_signal = False

        # R2: Conflicting Entry/Exit (Long) -> Prioritize Exit (Entry=False)
        # Note: Pyo3 prioritizes processing exit first, then entry.
        # If entry and exit trigger on same bar, Pyo3 cleans entry to false.
        if entry_long_signal and exit_long_signal:
            entry_long_signal = False

        # R3: Conflicting Entry/Exit (Short)
        if entry_short_signal and exit_short_signal:
            entry_short_signal = False

        return (
            entry_long_signal,
            entry_short_signal,
            exit_long_signal,
            exit_short_signal,
        )

    def next(self):
        # Current Bar Data (Signal Bar)
        close = self.data.Close[-1]
        high = self.data.High[-1]
        low = self.data.Low[-1]
        atr = self.atr[-1]

        # 根据 tsl_anchor_mode 计算锚点：True=High/Low, False=Close
        anchor_long = high if C.tsl_anchor_mode else close  # 多头锚点
        anchor_short = low if C.tsl_anchor_mode else close  # 空头锚点

        # Prev bar data (用于 TSL 更新)
        has_prev = len(self.data) > 1
        prev_atr = self.atr[-2] if has_prev else atr
        prev_close = self.data.Close[-2] if has_prev else close
        prev_anchor_long = (
            self.data.High[-2] if C.tsl_anchor_mode and has_prev else prev_close
        )
        prev_anchor_short = (
            self.data.Low[-2] if C.tsl_anchor_mode and has_prev else prev_close
        )

        entry_long, entry_short, exit_long, exit_short = self._get_signals()

        # --- Risk Management (TSL Update - Pyo3 Compatible) ---
        # TSL 独立追踪，不更新 trade.sl，与 Pyo3 架构一致
        if self.trades:
            trade = self.trades[0]
            current_bar_idx = len(self.data) - 1
            is_entry_bar = trade.entry_bar == current_bar_idx

            # 1. Update Extremum & TSL FIRST (Skip on Entry Bar)
            if not is_entry_bar:
                # Update Extremum with prev_bar
                if self.position.is_long:
                    if self.extremum is None or prev_anchor_long > self.extremum:
                        self.extremum = prev_anchor_long
                else:
                    if self.extremum is None or prev_anchor_short < self.extremum:
                        self.extremum = prev_anchor_short

                # Update TSL (Ratchet logic)
                if C.tsl_atr > 0 and self.extremum is not None:
                    if self.position.is_long:
                        new_tsl = self.extremum - prev_atr * C.tsl_atr
                        if self.tsl_price is None or new_tsl > self.tsl_price:
                            self.tsl_price = new_tsl
                    else:
                        new_tsl = self.extremum + prev_atr * C.tsl_atr
                        if self.tsl_price is None or new_tsl < self.tsl_price:
                            self.tsl_price = new_tsl

            # 2. TSL Trigger Check
            # 根据 tsl_trigger_mode 选择触发检查价格：True=High/Low, False=Close
            if self.tsl_price is not None:
                if C.tsl_trigger_mode:
                    # 使用 high/low 检查
                    tsl_triggered = (
                        self.position.is_long and low < self.tsl_price
                    ) or (self.position.is_short and high > self.tsl_price)
                else:
                    # 使用 close 检查
                    tsl_triggered = (
                        self.position.is_long and close < self.tsl_price
                    ) or (self.position.is_short and close > self.tsl_price)
                if tsl_triggered:
                    self.position.close()

        # --- Execution Logic ---

        # 1. Exit Signals
        if exit_long and self.position.is_long:
            self.position.close()

        if exit_short and self.position.is_short:
            self.position.close()

        # 2. Entry Signals (Reversal supported)
        if entry_long and not self.position.is_long:
            if self.position.is_short:
                self.position.close()

            sl_fixed = close * (1 - C.sl_pct)
            tp_fixed = close + atr * C.tp_atr
            self.extremum = anchor_long
            self.tsl_price = self.extremum - atr * C.tsl_atr if C.tsl_atr > 0 else None
            self.buy(sl=sl_fixed, tp=tp_fixed, size=size)

        elif entry_short and not self.position.is_short:
            if self.position.is_long:
                self.position.close()

            sl_fixed = close * (1 + C.sl_pct)
            tp_fixed = close - atr * C.tp_atr
            self.extremum = anchor_short
            self.tsl_price = self.extremum + atr * C.tsl_atr if C.tsl_atr > 0 else None
            self.sell(sl=sl_fixed, tp=tp_fixed, size=size)
