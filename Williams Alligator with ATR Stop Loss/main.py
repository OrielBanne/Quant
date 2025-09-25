from AlgorithmImports import *
from QuantConnect.Indicators import MovingAverageType
import numpy as np


# ----------------------------
# Simple Trend Check
# ----------------------------
# This function checks for a bullish trend using three different time series.
# It ensures that the short-term EMA is above the long-term EMA, and that the
# slope of the short-term EMA is positive and above a defined threshold.
def is_trending_ema(ts1, ts2, ts3, short=5, long=20, slope_threshold=0.01):
    """
    Bullish trend if short EMA > long EMA
    AND slope of short EMA is greater than slope_threshold.
    slope_threshold is relative (% change per bar).
    """
    if len(ts1) < long:
        return False

    def ema(arr, period):
        """Helper function to calculate Exponential Moving Average (EMA)."""
        alpha = 2 / (period + 1)
        out = [arr[0]]
        for price in arr[1:]:
            out.append(alpha * price + (1 - alpha) * out[-1])
        return np.array(out)

    def ema_with_slope(ts, short, long):
        """Helper function to check EMA cross and calculate slope."""
        s = ema(ts[-long:], short)
        l = ema(ts[-long:], long)
        # Calculate the relative slope over the window
        slope = (s[-1] - s[0]) / s[0]
        # Return boolean for cross and the calculated slope
        return s[-1] > l[-1], slope

    # Check for trend on three different data series
    test1, slope1 = ema_with_slope(ts1, short, long)
    test2, slope2 = ema_with_slope(ts2, short, long)
    test3, slope3 = ema_with_slope(ts3, short, long)

    return (
        (test1 and slope1 > slope_threshold) and
        (test2 and slope2 > slope_threshold) and
        (test3 and slope3 > slope_threshold)
    )


# ---------------------------
# Simple SMMA
# ---------------------------
# This is a custom indicator class for the Smoothed Moving Average (SMMA).
# It's an alternative to a standard moving average, providing a more
# smoothed value that can be useful in identifying trends.
class SMMAIndicator:
    def __init__(self, length):
        """Initializes the SMMA indicator with a specific length."""
        self.length = length
        self.current = None
        self.count = 0

    def Update(self, price):
        """Updates the SMMA with a new price point."""
        if self.current is None:
            self.current = price
        else:
            self.current = (self.current * (self.length - 1) + price) / self.length
        self.count += 1
        return self.current

    @property
    def IsReady(self):
        """Checks if the indicator has enough data to be considered 'ready'."""
        return self.count >= self.length

    @property
    def Current(self):
        """Returns the current value of the SMMA."""
        return self.current


# ---------------------------
# Main Algorithm
# ---------------------------
class AlligatorStopLossQC(QCAlgorithm):
    # ---------- Lifecycle ----------
    def Initialize(self):
        """
        This is the main initialization method for the algorithm.
        It sets up the trading environment, indicators, and charts.
        """
        # --- Basics ---
        self.set_start_date(2023, 1, 1)
        self.set_cash(100000)
        self.ticker_str = "AAPL"
        self.chosen_symbol = self.add_equity(self.ticker_str, Resolution.DAILY).Symbol
        self.set_benchmark(self.chosen_symbol)

        # --- Params (tune here) ---
        self.alligator_warm_up = 100
        self.cooldown_days = 1 # Cooldown period after an exit
        
        # Alligator lengths as per Bill Williams
        self.jawLength, self.teethLength, self.lipsLength = 13, 8, 5

        # ATR stop-loss parameters
        self.atr_period = 14
        self.atr_multiplier = 0.2

        # State variables
        self.entryPrice = None
        self.highestPrice = None
        self.startup_check = True  # A flag for the initial buy
        self.cooldown_days_remaining = 0
        self.lips_prev, self.teeth_prev, self.jaw_prev = None, None, None

        # --- Indicators ---
        # The Alligator indicator is a set of three SMMA lines.
        self.jaw = SMMAIndicator(self.jawLength)
        self.teeth = SMMAIndicator(self.teethLength)
        self.lips = SMMAIndicator(self.lipsLength)

        # Built-in ATR indicator for stop-loss
        self.atr_sl = self.atr(self.chosen_symbol,
                               self.atr_period,
                               MovingAverageType.WILDERS,
                               Resolution.DAILY)

        # --- History & Warm-up ---
        # We need to warm up our custom SMMA indicators with historical data.
        history = self.history(self.chosen_symbol, timedelta(days=self.alligator_warm_up), Resolution.DAILY)
        
        # Check if we have history data to warm up with
        if history.empty:
            self.log("No history data found for warm-up period. Cannot proceed.")
            return

        # Initialize lists to store indicator values for the trend check function
        self.hl2s, self.lips_list, self.teeth_list, self.jaws_list = [], [], [], []

        for bar in history.itertuples():
            hl2 = (bar.high + bar.low) / 2.0
            
            # Update custom SMMA indicators
            jaw_val = self.jaw.Update(hl2)
            teeth_val = self.teeth.Update(hl2)
            lips_val = self.lips.Update(hl2)

            # Store the values for the trend check
            self.hl2s.append(hl2)
            self.jaws_list.append(jaw_val)
            self.teeth_list.append(teeth_val)
            self.lips_list.append(lips_val)

        # Set initial 'previous' values for the first bar of the live data
        self.jaw_prev = self.jaw.Current
        self.teeth_prev = self.teeth.Current
        self.lips_prev = self.lips.Current
        
        self.startingValue = self.portfolio.total_portfolio_value

        # --- Charts ---
        self._init_charts()

    # ---------- Charting ----------
    def _init_charts(self):
        """Sets up the custom charts to visualize the strategy."""
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

        perf = Chart("Performance")
        perf.add_series(Series("Strategy", SeriesType.LINE, unit=""))
        perf.add_series(Series(self.ticker_str, SeriesType.LINE, unit=""))
        self.add_chart(perf)

    # ---------- Main Bar Handler ----------
    def OnData(self, data):
        """
        The main event handler called for each new bar of data.
        It updates indicators and checks for entry/exit signals.
        """
        # --- Basic guards ---
        if not data.ContainsKey(self.chosen_symbol):
            return
        bar = data[self.chosen_symbol]
        if bar is None:
            return

        # Ensure all indicators are ready before trading
        if not self.jaw.IsReady or not self.teeth.IsReady or not self.lips.IsReady or not self.atr_sl.IsReady:
            return

        # Update custom SMMA indicators
        hl2 = (bar.High + bar.Low) / 2.0
        jaw = self.jaw.Update(hl2)
        teeth = self.teeth.Update(hl2)
        lips = self.lips.Update(hl2)

        # Store indicator values for trend check and for the next bar's 'previous' values
        self.hl2s.append(hl2)
        self.lips_list.append(lips)
        self.teeth_list.append(teeth)
        self.jaws_list.append(jaw)
        
        # Plot indicators to chart
        self.plot(f"{self.ticker_str} Price", "Jaw", jaw)
        self.plot(f"{self.ticker_str} Price", "Teeth", teeth)
        self.plot(f"{self.ticker_str} Price", "Lips", lips)
        self.plot(f"{self.ticker_str} Price", self.ticker_str, bar.Close)

        # Update performance chart
        self.update_performance(bar)

        # --- Trading Logic ---
        if self.portfolio.invested:
            if self.cooldown_days_remaining == 0:
                self.check_exit(bar, jaw, teeth, lips)
        else:
            if self.cooldown_days_remaining > 0:
                self.cooldown_days_remaining -= 1
            else:
                self.check_entry(bar, jaw, teeth, lips)

        # Update previous values for the next bar
        self.jaw_prev, self.teeth_prev, self.lips_prev = jaw, teeth, lips

    # ---------- Entry / Exit Logic ----------
    def check_entry(self, bar, jaw, teeth, lips):
        """
        Entry logic based on Alligator and trend conditions.
        """
        # Condition 1: Check for trend
        # We need at least 20 bars to perform the trend check
        if len(self.hl2s) < 20:
            return
            
        trend_ok = is_trending_ema(
            np.array(self.hl2s[-20:]),
            np.array(self.lips_list[-20:]),
            np.array(self.teeth_list[-20:])
        )
        if not trend_ok:
            return

        # Condition 2: Check for a Lips cross above Teeth
        lips_cross_up = (self.lips_prev is not None and self.teeth_prev is not None
                         and self.lips_prev <= self.teeth_prev and lips > teeth)

        # Condition 3: A one-time-ever startup entry to catch existing trends
        if self.startup_check:
            if self.portfolio.invested == False:
                 self.buy(bar, "startup trending condition")
                 self.startup_check = False # Ensures this only happens once
            return

        # Combine conditions for a normal entry
        if lips_cross_up:
            self.buy(bar, "Lips cross up")

    def check_exit(self, bar, jaw, teeth, lips):
        """
        Exit logic based on ATR stop-loss and Alligator conditions.
        """
        if self.entryPrice is None:
            return

        price = bar.Close
        atr_value = self.atr_sl.Current.Value

        # Exit Condition 1: ATR-based stop loss
        atr_stop = self.entryPrice - self.atr_multiplier * atr_value
        if price <= atr_stop:
            self.sell(bar, f"ATR stop {self.atr_multiplier}x ATR")
            return

        # Exit Condition 2: Lips cross below Teeth with a buffer
        lips_cross_down_with_buffer = (
            self.lips_prev is not None and self.teeth_prev is not None and
            self.lips_prev >= self.teeth_prev and lips < teeth
        )
        if lips_cross_down_with_buffer:
            self.sell(bar, "Lips crossed below Teeth")
            return

        # Exit Condition 3: Lips cross below Jaw
        lips_below_jaw = (
            self.lips_prev is not None and self.jaw_prev is not None and
            self.lips_prev >= self.jaw_prev and lips < jaw
        )
        if lips_below_jaw:
            self.sell(bar, "Lips crossed below Jaw")
            return

    # ---------- Helper Functions (Actions) ----------
    def buy(self, bar, reason):
        """Places a buy order and updates state."""
        if not self.portfolio.invested:
            self.set_holdings(self.chosen_symbol, 1.0)
            self.entryPrice = bar.Close
            self.highestPrice = bar.Close
            self.cooldown_days_remaining = self.cooldown_days
            self.log(f"{self.time} - BUY: {reason} @ {bar.Close:.2f}")
            self.plot(f"{self.ticker_str} Price", "Buy", bar.Close)

    def sell(self, bar, reason):
        """Liquidates the position and updates state."""
        self.liquidate(self.chosen_symbol)
        self.log(f"{self.time} - SELL: {reason} @ {bar.Close:.2f}")
        self.plot(f"{self.ticker_str} Price", "Sell", bar.Close)
        self.entryPrice = None
        self.highestPrice = None
        self.cooldown_days_remaining = self.cooldown_days


    def update_performance(self, bar):
        """Updates the performance chart."""
        if not hasattr(self, "initial_equity"):
            self.initial_equity = float(self.portfolio.total_portfolio_value)
            self.initial_symbol_price = bar.Close
            return

        normalized_equity = 100.0 * (float(self.portfolio.total_portfolio_value) / self.initial_equity)
        normalized_symbol = 100.0 * (bar.Close / self.initial_symbol_price)

        self.plot("Performance", "Strategy", normalized_equity)
        self.plot("Performance", self.ticker_str, normalized_symbol)
