# region imports
from AlgorithmImports import *
import numpy as np
# endregion


# ---------------------------
# Math / Trend Utilities
# ---------------------------
def hurst_exponent(ts, max_lag=None):
    """
    Compute Hurst exponent using R/S-style log-log slope on std(diff(ts, lag)).
    - ts: 1D numpy array of prices (or HL2)
    - max_lag: optional cap (will auto-bound by len(ts)//2)
    """
    ts = np.asarray(ts)
    n = len(ts)

    if n < 10:
        # too short to be meaningful; return "neutral"
        return 0.5

    if max_lag is None:
        max_lag = max(2, n // 2)
    max_lag = min(max_lag, n - 2)

    if n < max_lag + 2:
        # auto-shrink max_lag to fit; fall back to small value
        max_lag = max(2, n // 3)
        if n < max_lag + 2:
            return 0.5

    lags = np.arange(2, max_lag)
    tau = []
    for lag in lags:
        diff = ts[lag:] - ts[:-lag]
        tau.append(np.sqrt(np.std(diff)))

    lags = np.array(lags, dtype=float)
    tau = np.array(tau, dtype=float)

    # Guard against zeros
    mask = (lags > 0) & (tau > 0)
    if mask.sum() < 2:
        return 0.5

    poly = np.polyfit(np.log(lags[mask]), np.log(tau[mask]), 1)
    H = float(poly[0])
    return H

def is_trending_ema(ts1, ts2, ts3, short=5, long=20, slope_threshold=0.01):
    """
    Bullish trend if short EMA > long EMA
    AND slope of short EMA is greater than slope_threshold.
    slope_threshold is relative (% change per bar).
    """
    if len(ts1) < long:
        return False

    import numpy as np

    def ema(arr, period):
        alpha = 2/(period+1)
        out = [arr[0]]
        for price in arr[1:]:
            out.append(alpha*price + (1-alpha)*out[-1])
        return np.array(out)

    def ema_with_slope(ts, short, long):
        s = ema(ts[-long:], short)
        l = ema(ts[-long:], long)
        slope = (s[-1] - s[0]) / s[0]  # relative slope over window
        return s[-1] > l[-1], slope

    test1, slope1 = ema_with_slope(ts1, short, long)
    test2, slope2 = ema_with_slope(ts2, short, long)
    test3, slope3 = ema_with_slope(ts3, short, long)

    return (
        (test1 and slope1 > slope_threshold) and
        (test2 and slope2 > slope_threshold) and
        (test3 and slope3 > slope_threshold)
    )


def is_trending(ts, threshold=0.5):
    """Return True if Hurst exponent suggests persistence > threshold."""
    H = hurst_exponent(ts)
    return H > threshold


# ---------------------------
# Simple SMMA
# ---------------------------
class SMMAIndicator:
    def __init__(self, length):
        self.length = length
        self.current = None
        self.count = 0

    def Update(self, price):
        if self.current is None:
            self.current = price
        else:
            self.current = (self.current * (self.length - 1) + price) / self.length
        self.count += 1
        return self.current

    @property
    def IsReady(self):
        return self.count >= self.length

    @property
    def Current(self):
        return self.current


# ---------------------------
# Main Algorithm
# ---------------------------
class AlligatorStopLossQC(QCAlgorithm):

    # ---------- Lifecycle ----------
    def Initialize(self):
        # --- Basics ---
        self.set_start_date(2023, 1, 1)
        self.set_cash(100000)
        self.ticker_str = "AAPL"
        self.chosen_symbol = self.add_equity(self.ticker_str, Resolution.DAILY).Symbol
        self.set_benchmark(self.ticker_str)

        # --- Series buffers ---
        self.hl2s, self.highs, self.lows, self.closes = [], [], [], []
        self.lips_list, self.teeth_list, self.jaws_list = [], [], []

        # --- Params (tune here) ---
        self.alligator_warm_up      = 100
        self.window_size            = 40           # Hurst window length gate
        self.hurst_threshold        = 0.5          # trending threshold
        self.check_Hurst_exponent   = False         # gate on/off

        # Price filter (Z-score) w/ multi-day strict rollover check
        self.use_entry_price_filter = True
        self.price_filter_lookback  = 20
        self.price_filter_k         = 1.5          # z > k => expensive; z < -k => cheap
        self.max_peak_days          = 2            # wait up to N days to confirm reversal
        self.wait_peak_check        = False
        self.peak_day_hl2           = None
        self.peak_check_days        = 0

        # Lips vs HL2 gap filter (blocks if HL2 too far above lips)
        self.lips_price_gap_pct     = 6.00          # percent (e.g., 1.0 => 1%)

        # Cooldown after buying
        self.cooldown_days_remaining = 0   # tracks how many days left to wait
        self.cooldown_days = 3

        # Exits
        self.stopLossPct            = 0.003   # * 100 = %  hard stop from entry
        self.trailingStopPct        = 0.003    # * 100 = % trailing from highest since entry

        # Alligator lengths
        self.jawLength, self.teethLength, self.lipsLength = 20, 12, 8

        # State
        self.entryPrice     = None
        self.highestPrice   = None
        self.startup_check  = True   # allow one startup buy ever (if already trending & lips>teeth)

        # Indicators
        self.jaw   = SMMAIndicator(self.jawLength)
        self.teeth = SMMAIndicator(self.teethLength)
        self.lips  = SMMAIndicator(self.lipsLength)

        self.lips_list.append(self.lips)
        self.teeth_list.append(self.teeth)
        self.jaws_list.append(self.jaw)

        # Warm-up indicators with history
        history = self.history(self.chosen_symbol, timedelta(days=self.alligator_warm_up), Resolution.DAILY)
        for bar in history.itertuples():
            hl2 = (bar.high + bar.low) / 2.0
            jaw_val = self.jaw.Update(hl2)
            teeth_val = self.teeth.Update(hl2)
            lips_val = self.lips.Update(hl2)
            self.lips_list.append(lips_val)
            self.teeth_list.append(teeth_val)
            self.jaws_list.append(jaw_val)

        self.startingValue = self.portfolio.total_portfolio_value

        # Charts
        self._init_charts()

        # Previous values placeholder
        self.jaw_prev = self.jaw.Current
        self.teeth_prev = self.teeth.Current
        self.lips_prev = self.lips.Current


    # ---------- Charting ----------
    def _init_charts(self):
        # Price + Alligator + markers
        chart = Chart(f"{self.ticker_str} Price")

        series_symbol = Series(self.ticker_str, SeriesType.LINE, unit="")
        series_symbol.color = Color.BLACK
        chart.add_series(series_symbol)

        series_jaw = Series("Jaw", SeriesType.LINE, unit="")
        series_jaw.color = Color.BLUE
        chart.add_series(series_jaw)

        series_teeth = Series("Teeth", SeriesType.LINE, unit="")
        series_teeth.color = Color.RED
        chart.add_series(series_teeth)

        series_lips = Series("Lips", SeriesType.LINE, unit="")
        series_lips.color = Color.GREEN
        chart.add_series(series_lips)

        buy_series = Series("Buy", SeriesType.SCATTER, unit="")
        buy_series.color = Color.GREEN
        buy_series.scatter_marker_symbol = ScatterMarkerSymbol.TRIANGLE
        buy_series.width = 6
        chart.add_series(buy_series)

        sell_series = Series("Sell", SeriesType.SCATTER, unit="")
        sell_series.color = Color.RED
        sell_series.scatter_marker_symbol = ScatterMarkerSymbol.TRIANGLE_DOWN
        sell_series.width = 6
        chart.add_series(sell_series)

        self.add_chart(chart)

        # Performance
        perf = Chart("Performance")
        perf.add_series(Series("Strategy", SeriesType.LINE, unit=""))
        perf.add_series(Series(self.ticker_str, SeriesType.LINE, unit=""))
        self.add_chart(perf)


    # ---------- Helpers (actions) ----------
    def buy(self, bar, reason):
        self.set_holdings(self.chosen_symbol, 1)
        self.entryPrice = bar.Close
        self.highestPrice = bar.Close
        self.cooldown_days_remaining = self.cooldown_days
        self.log(f"{self.time} - BUY: {reason} @ {bar.Close}")
        self.plot(f"{self.ticker_str} Price", "Buy", bar.Close)

    def sell(self, bar, reason):
        self.liquidate(self.chosen_symbol)
        self.log(f"{self.time} - SELL: {reason} @ {bar.Close}")
        self.plot(f"{self.ticker_str} Price", "Sell", bar.Close)
        self.entryPrice = None
        self.highestPrice = None

    def update_performance(self, bar):
        # strategy_return = (self.portfolio.total_portfolio_value / self.startingValue) * 100.0
        # symbol_return = (bar.Close / self.closes[0]) * 100.0 if self.closes else 100.0
        # self.plot("Performance", "Strategy", strategy_return)
        # self.plot("Performance", self.ticker_str, symbol_return)

        if not hasattr(self, "initial_equity"):
            self.initial_equity = float(self.Portfolio.TotalPortfolioValue)
            self.initial_symbol_price = bar.Close
            return

        # normalized to 100 at baseline
        normalized_equity = 100.0 * (float(self.portfolio.total_portfolio_value) / self.initial_equity)
        normalized_symbol = 100.0 * (bar.Close / self.initial_symbol_price)

        self.plot("Performance", "StrategyNorm", normalized_equity)
        self.plot("Performance", self.ticker_str+"Norm", normalized_symbol)


    # ---------- Core computations ----------
    def update_indicators(self, bar):
        """Update rolling arrays and SMMA lines. Return (hl2, jaw, teeth, lips) or (None, ... ) if not ready."""
        hl2 = (bar.High + bar.Low) / 2.0

        self.highs.append(bar.High)
        self.lows.append(bar.Low)
        self.closes.append(bar.Close)
        self.hl2s.append(hl2)

        # Need at least one full period of the longest SMMA
        min_len = max(self.jawLength, self.teethLength, self.lipsLength) + 1
        if len(self.hl2s) < min_len:
            return None, None, None, None

        jaw = self.jaw.Update(hl2)
        teeth = self.teeth.Update(hl2)
        lips = self.lips.Update(hl2)

        self.lips_list.append(lips)
        self.teeth_list.append(teeth)
        self.jaws_list.append(jaw)

        return hl2, jaw, teeth, lips

    def compute_trend_flag(self):
        """Simpler trend check if Hurst disabled."""
        if self.check_Hurst_exponent:
            if len(self.hl2s) < self.window_size:
                return False
            return is_trending(np.array(self.hl2s[-self.window_size:]), threshold=self.hurst_threshold)
        else:
            # lightweight trend
            return is_trending_ema(self.hl2s[-20:], self.lips_list[-20:], self.teeth_list[-20:])


    def lips_price_gap_ok(self, lips_val, hl2):
        """Block if HL2 is more than X% above lips."""
        if self.lips_price_gap_pct < 0:  # bypass if negative pct is defined
            return True
        gap = 1.0 + 0.01 * float(self.lips_price_gap_pct)
        ok = not (lips_val * gap < hl2)
        if not ok:
            self.log(f"{self.time} - Blocked: HL2 is more than {self.lips_price_gap_pct:.1f}% above lips "
                     f"(hl2={hl2:.2f}, lips={lips_val:.2f})")
        return ok

    def entry_price_filter(self, bar, hl2):
        """
        Z-score filter with multi-day STRICT rollover confirmation.
        - Cheap (z < -k) => allow now.
        - Expensive (z > +k) => start waiting for up to self.max_peak_days:
            - If any day drops below the initial expensive-day HL2 => reversal confirmed => block.
            - If no drop within max days => allow entry (trend likely continued).
        """
        if not self.use_entry_price_filter:
            return True

        lb = int(self.price_filter_lookback)
        if len(self.hl2s) < lb:
            return False

        window = self.hl2s[-lb:]
        sma = float(np.mean(window))
        std = float(np.std(window))
        if std == 0.0:
            return True

        z = (hl2 - sma) / std
        cheap = z < -self.price_filter_k
        expensive = z > self.price_filter_k

        # Cheap => allow now
        if cheap:
            return True

        # Start peak-check mode on first expensive
        if expensive and not self.wait_peak_check:
            self.wait_peak_check  = True
            self.peak_day_hl2     = hl2
            self.peak_check_days  = 0
            self.log(f"{self.time} - Price expensive (z={z:.2f}); waiting up to {self.max_peak_days} days to confirm peak")
            return False

        # Already waiting: strict rollover check
        if self.wait_peak_check:
            self.peak_check_days += 1

            # Rollover (reversal) confirmed
            if self.peak_day_hl2 is not None and hl2 < self.peak_day_hl2:
                self.log(f"{self.time} - Peak confirmed on day {self.peak_check_days} → blocking entry")
                self.wait_peak_check = False
                self.peak_day_hl2 = None
                self.peak_check_days = 0
                return False

            # If max days pass with no rollover => allow entry
            if self.peak_check_days >= self.max_peak_days:
                self.log(f"{self.time} - No peak confirmed in {self.max_peak_days} days → allowing entry")
                self.wait_peak_check = False
                self.peak_day_hl2 = None
                self.peak_check_days = 0
                return True

            # Still waiting
            self.log(f"{self.time} - Day {self.peak_check_days}: still waiting for peak confirmation")
            return False

        # Neutral
        return True


    # ---------- Entry / Exit ----------
    def check_entry(self, bar, hl2, jaw, teeth, lips):
        """Entry logic including startup buy-on-trend (only once ever)."""
        trend_ok = self.compute_trend_flag()
        if not trend_ok:
            return


        # fixed Startup catch-up (only once ever): only checking trend up
        if self.startup_check and jaw is not None and teeth is not None and lips is not None:
            if not self.portfolio.invested:
                self.buy(bar, "startup trending condition")
                # lets try and find trend all the time, so i am commenting the next command
                # self.startup_check = False  # only once ever
                self.wait_peak_check = False


        # Normal cross entry: Lips cross above Teeth (from below)
        lips_cross_up = (self.lips_prev is not None and self.teeth_prev is not None
                         and self.lips_prev <= self.teeth_prev and lips > teeth)

        if lips_cross_up:
            if self.lips_price_gap_ok(lips, hl2) and self.entry_price_filter(bar, hl2):
                self.buy(bar, "cross + filter")
                self.wait_peak_check = False


    def check_exit(self, bar, jaw, teeth, lips):
        """Unified exit logic: trailing stop, hard stop, and cross exits."""
        if self.entryPrice is None:
            return

        price = bar.Close

        # Trailing high update
        if self.highestPrice is None or price > self.highestPrice:
            self.highestPrice = price

        # 1) Trailing stop
        if price <= self.highestPrice * (1 - self.trailingStopPct):
            self.sell(bar, f"trailing stop {int(self.trailingStopPct*100)}% from {self.highestPrice:.2f}")
            self.wait_peak_check = True
            return

        # 2) Hard stop from entry
        if price <= self.entryPrice * (1 - self.stopLossPct):
            self.sell(bar, f"hard stop {int(self.stopLossPct*100)}% from entry {self.entryPrice:.2f}")
            self.wait_peak_check = True
            return

        # 3) Lips cross below Teeth with buffer (exit on weakness)
        lips_cross_down_with_buffer = (
            self.lips_prev is not None and self.teeth_prev is not None and
            self.lips_prev >= self.teeth_prev and 1.05 * lips < teeth
        )
        if lips_cross_down_with_buffer:
            self.sell(bar, "lips crossed below teeth (buffer)")
            self.wait_peak_check = True
            return

        # 4) Lips cross below Jaw
        lips_below_jaw = (
            self.lips_prev is not None and self.jaw_prev is not None and
            self.lips_prev >= self.jaw_prev and lips < jaw
        )
        if lips_below_jaw:
            self.sell(bar, "lips crossed below jaw")
            self.wait_peak_check = True
            return


    # ---------- Main Bar Handler ----------
    def OnData(self, data):
        # ---------- basic guards ----------
        if not data.ContainsKey(self.chosen_symbol):
            return

        bar = data[self.chosen_symbol]
        if bar is None:
            return

        # ---------- update indicators & rolling series ----------
        hl2, jaw, teeth, lips = self.update_indicators(bar)
        if hl2 is None:
            # still warming up SMMA / buffers
            # self.log(f"{self.time} - Warming up: collected {len(self.hl2s)} hl2 values")
            return
        if len(self.hl2s) == 20: # TODO: plug in here the window size global replacing 20
            self.log(f"{self.time} - Warm up done : collected {len(self.hl2s)} hl2 values")

        # ---------- plot price & alligator lines ----------
        symbol_price = self.securities[self.chosen_symbol].price
        self.plot(f"{self.ticker_str} Price", self.ticker_str, symbol_price)
        self.plot(f"{self.ticker_str} Price", "Jaw",   jaw)
        self.plot(f"{self.ticker_str} Price", "Teeth", teeth)
        self.plot(f"{self.ticker_str} Price", "Lips",  lips)

        # ---------- diagnostic summary (compact) ----------
        # self.log(
        #     f"{self.time} - idx={len(self.hl2s)} wait_peak={getattr(self,'wait_peak_check',False)} "
        #     f"peak_hl2={getattr(self,'peak_day_hl2',None)} peak_days={getattr(self,'peak_check_days',0)} "
        #     f"startup_ok={getattr(self,'startup_check',False)} invested={self.portfolio.invested}"
        # )

        # ---------- show why Hurst might block (if enabled) ----------
        # if getattr(self, "check_Hurst_exponent", False):
        #     enough = len(self.hl2s) >= getattr(self, "window_size", 0)
        #     self.log(f"{self.time} - Hurst check ENABLED (enough_data={enough}, window_size={self.window_size})")
        # else:
        #     self.log(f"{self.time} - Hurst check DISABLED (entries allowed)")

        # ---------- Entry / Exit decision ----------
        if not self.portfolio.invested:
            # Before calling check_entry, print the key filter values so you can see them in logs
            try:
                # z-score diagnostic if enough lookback
                lb = int(getattr(self, "price_filter_lookback", 0))
                if len(self.hl2s) >= lb and lb > 0:
                    window = self.hl2s[-lb:]
                    sma = float(np.mean(window))
                    std = float(np.std(window))
                    hl2_now = hl2
                    z = (hl2_now - sma) / std if std != 0 else float("nan")
                    # self.log(f"{self.time} - Z-score check: z={z:.2f} (k={self.price_filter_k})")
            except Exception as _e:
                # safe guard — don't crash OnData for logging
                pass

            # call your existing entry routine (which enforces startup_once behavior)
            self.check_entry(bar, hl2, jaw, teeth, lips)

        else:
            # invested -> unified exit logic
            if self.cooldown_days_remaining == 0:
                self.check_exit(bar, jaw, teeth, lips)

        # ---------- update performance plot & prev values ----------
        self.update_performance(bar)
        # keep previous alligator values for cross detection
        self.jaw_prev, self.teeth_prev, self.lips_prev = jaw, teeth, lips

        # Decrement cooldown if active
        if self.cooldown_days_remaining > 0:
            self.cooldown_days_remaining -= 1
