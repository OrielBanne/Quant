# region imports
from AlgorithmImports import *
import numpy as np
# endregion

import numpy as np


def hurst_exponent(ts, max_lag=None):
    """
    Compute Hurst exponent using R/S method.
    ts: 1D numpy array of prices (or log returns)
    max_lag: maximum lag to consider (should be < len(ts))
    """
    ts = np.asarray(ts)
    n = len(ts)

    if max_lag is None:
        max_lag = max(2, len(ts)//2)  # automatically pick a safe value


    if n < max_lag + 2:
        raise ValueError("Time series too short for the chosen max_lag")

    lags = np.arange(2, min(max_lag, n-1))
    tau = []

    for lag in lags:
        diff = ts[lag:] - ts[:-lag]
        tau.append(np.sqrt(np.std(diff)))

    # Make sure lengths match
    lags = np.array(lags)
    tau = np.array(tau)
    
    # Fit line to log-log
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    H = poly[0]
    return H

def is_trending(ts, threshold=0.5):
    H = hurst_exponent(ts)
    # print(f"Hurst exponent = {H:.3f}")
    return H > threshold

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



class AlligatorStopLossQC(QCAlgorithm):
    def Initialize(self):
        self.set_start_date(2023, 1, 1)
        self.set_cash(100000)
        self.ticker_str = "NVDA"
        self.chosen_symbol = self.add_equity(self.ticker_str, Resolution.DAILY).Symbol
        self.hl2s   = []
        self.highs  = []
        self.lows   = []
        self.closes = []
   
        
        # Set the symbol itself as benchmark
        self.set_benchmark(self.chosen_symbol)

        self.alligator_warm_up = 100
        self.window_size = 40

        # --- Entry Price Filter (toggleable) ---
        self.use_entry_price_filter      = True   # <- set False to disable this whole feature
        self.price_filter_lookback       = 20     # 'vicinity' window (days)
        self.price_filter_k              = 1.5   # z-score threshold (cheap < -k, expensive > +k)

        # runtime state for the 1-day confirmation
        self.wait_peak_check             = False  # set True when we defer a buy
        self.peak_day_close              = None   # yesterday's close when we deferred
        self.allow_entry_at_peak         = False  # if True, allow buy today even if expensive
        self.skip_buy_today_due_to_peak  = False  # if True, block buys today due to confirmed peak
        
        # this is the gate for trend up stability check
        self.check_Hurst_exponent        = False

        # price drop filter
        self.entryPrice = None
        self.highestPrice = None
        self.trailingStopPct = 0.15  # 15%

        # days to check if we are at a peak:
        self.max_peak_days = 3   # wait up to 3 days for reversal confirmation

        
        # Add chart for price, signals, and alligator lines
        
        chart = Chart(f"{self.ticker_str} Price")

        symbol_series  = Series(self.ticker_str,    SeriesType.LINE,   unit="")
        symbol_series.color = Color.BLACK
        chart.add_series(symbol_series)

        jaw_series   = Series("Jaw",   SeriesType.LINE,    unit="")
        jaw_series.color = Color.BLUE
        chart.add_series(jaw_series)

        teeth_series = Series("Teeth", SeriesType.LINE,    unit="")
        teeth_series.color = Color.RED
        chart.add_series(teeth_series)

        lips_series  = Series("Lips",  SeriesType.LINE,    unit="")
        lips_series.color = Color.GREEN
        chart.add_series(lips_series)

        buy_series   = Series("Buy",   SeriesType.SCATTER, unit="")
        buy_series.color = Color.GREEN
        buy_series.scatter_marker_symbol = ScatterMarkerSymbol.TRIANGLE
        buy_series.width = 6
        chart.add_series(buy_series)

        sell_series  = Series("Sell",  SeriesType.SCATTER, unit="")
        sell_series.color = Color.RED
        sell_series.scatter_marker_symbol = ScatterMarkerSymbol.TRIANGLE_DOWN
        sell_series.width = 6
        chart.add_series(sell_series)

        self.add_chart(chart)

        # Add chart for performance comparison

        perf_chart = Chart("Performance")

        perf_series = Series("Strategy", SeriesType.LINE, unit="")
        perf_chart.add_series(perf_series)

        symbol_series  = Series(self.ticker_str,      SeriesType.LINE, unit="")
        perf_chart.add_series(symbol_series)

        self.add_chart(perf_chart)
        
     
        
        # Alligator parameters
        self.jawLength = 20
        self.teethLength = 12
        self.lipsLength = 8
        self.stopLossPct = 0.02  # 2% stop loss

        # New SMMA lines:
        self.jaw   = SMMAIndicator(self.jawLength)
        self.teeth = SMMAIndicator(self.teethLength)
        self.lips  = SMMAIndicator(self.lipsLength)
        

        # Warm up SMMA indicators with historical HL2
        history = self.History(self.chosen_symbol, 
                                timedelta(days =  self.alligator_warm_up), 
                                Resolution.DAILY)
        for bar in history.itertuples():
            hl2 = (bar.high + bar.low) / 2
            self.jaw.Update(hl2)
            self.teeth.Update(hl2)
            self.lips.Update(hl2)


        self.entryPrice = None
        self.startingValue = self.portfolio.total_portfolio_value

    def _entry_price_filter(self, bar, lips_val, teeth_val, jaw_val):
        """
        Returns True if we may execute the buy *now*.
        Returns False if we should defer a few days for peak confirmation.
        """

        if not getattr(self, 'use_entry_price_filter', False):
            return True

        lookback = int(self.price_filter_lookback)
        if len(self.hl2s) < lookback:
            return False

        window = self.hl2s[-lookback:]
        sma = float(np.mean(window))
        std = float(np.std(window))
        if std == 0.0:
            return True

        hl2 = (bar.High + bar.Low) / 2.0
        z = (hl2 - sma) / std
        cheap = z < -self.price_filter_k
        expensive = z > self.price_filter_k

        # Cheap → buy now
        if cheap:
            return True

        # Expensive → start peak-check mode
        if expensive and not getattr(self, 'wait_peak_check', False):
            self.wait_peak_check = True
            self.peak_day_close = hl2
            self.peak_check_days = 0
            self.log(f"{self.time} - Price expensive (z={z:.2f}); waiting up to {self.max_peak_days} days to confirm peak")
            return False

        # Already in peak-check mode
        if getattr(self, 'wait_peak_check', False):
            self.peak_check_days += 1

            # Peak confirmed → price rolled over
            if hl2 < self.peak_day_close:
                self.log(f"{self.time} - Peak confirmed on day {self.peak_check_days} → blocking entry")
                self.wait_peak_check = False
                return False

            # If max days passed without reversal → allow entry
            if self.peak_check_days >= self.max_peak_days:
                self.log(f"{self.time} - No peak confirmed in {self.max_peak_days} days → allowing entry")
                self.wait_peak_check = False
                return True

            # Still waiting
            self.log(f"{self.time} - Day {self.peak_check_days}: still waiting for peak confirmation")
            return False

        # Neutral → allow
        return True


    def OnData(self, data):
        if not data.ContainsKey(self.chosen_symbol):
            return

        if not self.jaw.IsReady or not self.teeth.IsReady or not self.lips.IsReady:
            return
        
        bar = data[self.chosen_symbol]
        if bar is None:
            return

        hl2 = (bar.High + bar.Low) / 2

        # --- Entry Price Filter: daily reset & one-day peak confirmation ---
        self.allow_entry_at_peak = False
        self.skip_buy_today_due_to_peak = False

        if self.wait_peak_check:
            # Evaluate yesterday's 'expensive' deferral
            is_peak = bar.Close < self.peak_day_close
            # Simple "trend down" check: lips not above teeth or lips sloping down
            trend_down = (self.lips.Current <= self.teeth.Current) or (hasattr(self, 'lips_prev') and self.lips.Current < self.lips_prev)

            if is_peak and trend_down:
                self.skip_buy_today_due_to_peak = True
                self.log(f"{self.time} - Peak confirmed & trend down → skip buys today")
            else:
                self.allow_entry_at_peak = True
                self.log(f"{self.time} - Yesterday expensive but no peak confirmed → allowed to buy today if signal")

            # Clear waiting state
            self.wait_peak_check = False
            self.peak_day_close = None


        # Update rolling data
        self.highs.append(bar.High)
        self.lows.append(bar.Low)
        self.closes.append(bar.Close)
        self.hl2s.append(hl2)
        
        if len(self.hl2s) < max(self.jawLength, self.teethLength, self.lipsLength) + 1:
            return

        # Update SMMA with new bar
        jaw_val   = self.jaw.Update(hl2)
        teeth_val = self.teeth.Update(hl2)
        lips_val  = self.lips.Update(hl2)

        # Previous values for cross detection (store them manually)
        if not hasattr(self, 'jaw_prev'):
            self.jaw_prev = jaw_val
            self.teeth_prev = teeth_val
            self.lips_prev = lips_val

        jaw_prev   = self.jaw_prev
        teeth_prev = self.teeth_prev
        lips_prev  = self.lips_prev

        # Plot Alligator lines
        symbol_price = self.securities[self.chosen_symbol].price
        self.plot(f"{self.ticker_str} Price", "Jaw", jaw_val)
        self.plot(f"{self.ticker_str} Price", "Teeth", teeth_val)
        self.plot(f"{self.ticker_str} Price", "Lips", lips_val)
        self.plot(f"{self.ticker_str} Price", self.ticker_str, symbol_price)

        # Check Hurst
        if self.check_Hurst_exponent:
            trend_flag = False
            if len(self.hl2s) >= self.window_size:
                if is_trending(np.array(self.hl2s)):
                    # Trend detected → allow entry
                    trend_flag = True
                else:
                    self.log("cannot by because Hurst exponent does not show trend up is stable")
                    trend_flag = False
        else:
            trend_flag = True
        
        # checking is there a large difference between lips and price point:
        percent_higher = 30
        if lips_val*(1+0.01*percent_higher) < hl2:
            trend_flag = False
            self.log(f"stopped because HL2 is more than {percent_higher}% higher - hl2 {hl2} lips {lips_val}")

        # Entry signals:
        if not self.portfolio.invested and trend_flag:
            if self.skip_buy_today_due_to_peak:
                    self.log(f"{self.time} - Entry signal blocked by peak filter")
            # Normal Entry - Lips cross above Teeth and Hurst Exponent Trend Flag
            elif lips_prev <= teeth_prev and lips_val > teeth_val:
                if self._entry_price_filter(bar, lips_val, teeth_val, jaw_val):
                    self.set_holdings(self.chosen_symbol, 1)
                    self.entryPrice = bar.Close
                    self.highestPrice = bar.Close  # reset highest
                    self.log(f"{self.time} - Entered Long at {self.entryPrice} (cross + filter)")
                    self.plot(f"{self.ticker_str} Price", "Buy", symbol_price)

            # Startup catch-up: already trending & lips above teeth
            elif lips_val > teeth_val and getattr(self, "startup_check", True):
                if self._entry_price_filter(bar, lips_val, teeth_val, jaw_val):
                    self.set_holdings(self.chosen_symbol, 1)
                    self.entryPrice = bar.Close
                    self.log(f"{self.time} - Entered Long at {self.entryPrice} (startup trending condition)")
                    self.plot(f"{self.ticker_str} Price", "Buy", symbol_price)
                # only do this once
                self.startup_check = False

        # While invested: update trailing stop
        elif self.portfolio.invested and self.entryPrice is not None:
            symbol_price = bar.Close
            
            # Track highest price since entry
            if self.highestPrice is None or symbol_price > self.highestPrice:
                self.highestPrice = symbol_price
            
            # Trailing stop: exit if drop ≥ 3% from highest
            if symbol_price <= self.highestPrice * (1 - self.trailingStopPct):
                self.liquidate(self.chosen_symbol)
                self.log(f"{self.time} - Exited Long at {symbol_price} (trailing stop -3% from {self.highestPrice})")
                self.entryPrice = None
                self.highestPrice = None
                exit_price = symbol_price
                self.log(f"{self.time} - Exit: Price Drop {exit_price}")
                self.plot(f"{self.ticker_str} Price", "Sell", exit_price)  # Red dot



        # Exit signals
        elif self.portfolio.invested and self.entryPrice is not None:
            exit_price = None

            # Stop loss
            if symbol_price <= self.entryPrice * (1 - self.stopLossPct):
                exit_price = symbol_price
                self.log(f"{self.time} - Stopped Out at {exit_price}")


            # Lips cross below Teeth - adding some distance between the two before exit
            elif lips_prev >= teeth_prev and 1.05*lips_val < teeth_val:
                exit_price = symbol_price
                self.log(f"{self.time} - Exit: Lips crossed below Teeth at {exit_price}")

            # Lips cross below Jaw
            elif lips_prev >= jaw_prev and lips_val < jaw_val:
                exit_price = symbol_price
                self.log(f"{self.time} - Exit: Lips crossed below Jaw at {exit_price}")

            # Execute exit if any condition met
            if exit_price is not None:
                self.liquidate(self.chosen_symbol)
                self.plot(f"{self.ticker_str} Price", "Sell", exit_price)  # Red dot


        # Plot performance comparison
        strategy_return = (self.portfolio.total_portfolio_value / self.startingValue) * 100
        symbol_return = (bar.Close / self.closes[0]) * 100
        self.plot("Performance", "Strategy", strategy_return)
        self.plot("Performance", self.ticker_str, symbol_return)


        # After processing, update previous values
        self.jaw_prev = jaw_val
        self.teeth_prev = teeth_val
        self.lips_prev = lips_val

