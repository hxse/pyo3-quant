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

        # Risk State
        self.extremum = None  # To track highest/lowest since entry for TSL

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
        prev_atr = (
            self.atr[-2] if len(self.atr) > 1 else atr
        )  # TSL Update uses prev_bar ATR

        entry_long, entry_short, exit_long, exit_short = self._get_signals()

        # --- Risk Management (TSL Update - Pyo3 Compatible) ---
        if self.trades:
            trade = self.trades[0]
            current_bar_idx = len(self.data) - 1
            is_entry_bar = trade.entry_bar == current_bar_idx

            # 1. Update Extremum & TSL FIRST (Skip on Entry Bar)
            # 使用 prev_bar 的 high/low 避免未来数据泄露
            if not is_entry_bar:
                # Get prev_bar data
                prev_high = self.data.High[-2] if len(self.data) > 1 else high
                prev_low = self.data.Low[-2] if len(self.data) > 1 else low

                # Update Extremum with prev_bar (known at current bar open)
                if self.position.is_long:
                    if self.extremum is None or prev_high > self.extremum:
                        self.extremum = prev_high
                else:
                    if self.extremum is None or prev_low < self.extremum:
                        self.extremum = prev_low

                # Update TSL (Ratchet logic)
                if C.tsl_atr > 0 and self.extremum is not None:
                    for t in self.trades:
                        if t.is_long:
                            tsl_price = self.extremum - prev_atr * C.tsl_atr
                            if t.sl:
                                t.sl = max(t.sl, tsl_price)
                            else:
                                t.sl = tsl_price
                        else:
                            tsl_price = self.extremum + prev_atr * C.tsl_atr
                            if t.sl:
                                t.sl = min(t.sl, tsl_price)

            # 2. In-Bar Check AFTER update (先更新后检查)
            if C.tsl_atr_tight:
                for t in self.trades:
                    if t.is_long:
                        if t.sl and low < t.sl:
                            self.position.close()
                            return
                    else:
                        if t.sl and high > t.sl:
                            self.position.close()
                            return

        # --- Execution Logic ---

        # 1. Exit Signals
        if exit_long and self.position.is_long:
            self.position.close()

        if exit_short and self.position.is_short:
            self.position.close()

        # 2. Entry Signals (Reversal supported: Close then Buy/Sell)

        if entry_long and not self.position.is_long:
            # Reversal: Close short if exists
            if self.position.is_short:
                self.position.close()

            # Calc SL/TP based on Signal Bar (Close[-1])
            sl_fixed = close * (1 - C.sl_pct)
            tp_fixed = close + atr * C.tp_atr

            # Pyo3 Logic: Effective SL is max(Fixed, TSL_Init)
            initial_sl = sl_fixed
            if C.tsl_atr > 0:
                tsl_init = close - atr * C.tsl_atr
                initial_sl = max(sl_fixed, tsl_init)

            # Initialize Extremum (Signal Bar) for Pyo3 Consistency
            if C.tsl_anchor_mode:
                self.extremum = high
            else:
                self.extremum = close

            self.buy(sl=initial_sl, tp=tp_fixed, size=size)

        elif entry_short and not self.position.is_short:
            # Reversal: Close long if exists
            if self.position.is_long:
                self.position.close()

            # Calc SL/TP based on Signal Bar (Close[-1])
            sl_fixed = close * (1 + C.sl_pct)
            tp_fixed = close - atr * C.tp_atr

            # Pyo3 Logic: Effective SL is min(Fixed, TSL_Init)
            initial_sl = sl_fixed
            if C.tsl_atr > 0:
                tsl_init = close + atr * C.tsl_atr
                initial_sl = min(sl_fixed, tsl_init)

            # Initialize Extremum (Signal Bar) for Pyo3 Consistency
            if C.tsl_anchor_mode:
                self.extremum = low
            else:
                self.extremum = close

            self.sell(sl=initial_sl, tp=tp_fixed, size=size)
