# region imports
from AlgorithmImports import *
from QuantConnect.Indicators import MovingAverageType
import numpy as np
from collections import deque
# endregion

#----------------------------------------
# State Machine - price coming from below 
# crossing all alligator lines in order:
# jaw->teeth->lips
#----------------------------------------
def _has_prev(*pairs):  # each pair is (cur, prev)
        return all(p is not None for _, p in pairs)

class BuyAlligator:
    def __init__(self, log_method):
        # State machine for the crossover sequence
        self.log_method = log_method # Store the logging method

    def buy_condition(self, price, jaw, teeth, lips):
        if not _has_prev(lips, teeth, jaw): 
            return False
        
        is_trend_up = ((lips[0]> lips[1]) and (teeth[0]>teeth[1]) and (jaw[0]>jaw[1]))
        # is_price_above_all_lines = (price>lips[0] and price>teeth[0] and price>jaw[0])
        is_price_above_all_lines = (price>teeth[0] and price>jaw[0])

        if price>lips[0] and is_price_above_all_lines and is_trend_up:
            return True
        return False


class BelowToLipsCrossover:
    def __init__(self, log_method):
        self.state = "unknown"
        self.log_method = log_method

    def update_state(self, price, jaw, teeth, lips):
        bellow_all = price < lips[0] and price < teeth[0] and price < jaw[0]
        on_the_back = lips[0] < teeth[0] and teeth[0] < jaw[0]
        open_mouth = lips[0] > teeth[0] and teeth[0] > jaw[0]

        # --- normal reset ---
        if bellow_all and on_the_back:
            self.state = "BELOW_ALL"
            return False

        # --- crossover from below all ---
        if self.state in ("BELOW_ALL", "ReArmed") and price > lips[0] and open_mouth:
            self.state = "ABOVE_lips"
            return True

        # --- mouth shut case ---
        if self.state == "ABOVE_lips" and not open_mouth:
            # instead of immediately ReArming, go into MOUTH_SHUT
            self.state = "MOUTH_SHUT"

        # --- mouth reopening without below_all ---
        if self.state == "MOUTH_SHUT" and price > lips[0] and open_mouth:
            self.state = "ABOVE_lips"
            return True

        # --- fallback rearm ---
        if self.state == "MOUTH_SHUT" and not open_mouth and price < lips[0]:
            self.state = "ReArmed"

        return False

    def rearm(self):
        """Force reset after an exit"""
        self.state = "ReArmed"


# ---------------------------
# Simple SMMA
# ---------------------------
class SMMAIndicator:
    def __init__(self, length):
        self.length = length
        self.current = None
        self.prev    = None
        self.count = 0

    def Update(self, price):
        if self.current is None:
            self.current = price

        else:
            self.prev = self.current
            self.current = (self.current * (self.length - 1) + price) / self.length
        self.count += 1
        return self.current, self.prev

    @property
    def IsReady(self):
        return self.count >= self.length

    @property
    def Current(self):
        return self.current

class ShiftedLine:
    def __init__(self, period, shift):
        self.smma = SMMAIndicator(period)
        self.buf  = deque(maxlen=shift+1)  # to emit "shifted" value
        self.shift = shift
    def Update(self, price):
        cur, prev = self.smma.Update(price)
        self.buf.append(cur)
        shifted = self.buf[0] if len(self.buf) == self.buf.maxlen else None
        return (shifted, prev)  # keep (cur,prev) interface but "cur" is shifted
    @property
    def IsReady(self):
        return self.smma.IsReady and len(self.buf) == self.buf.maxlen
# ---------------------------
# Main Algorithm
# ---------------------------
# --- Main Algorithm ---
class AlligatorStopLossQC(QCAlgorithm):
    # ---------- Lifecycle ----------
    def Initialize(self):
        # --- Basics ---
        self.set_start_date(2023, 1, 1)
        self.set_cash(100000)
        self.initial_equity = float(self.portfolio.total_portfolio_value)
        self.ticker_str = "NVDA"
        # self.ticker_str = "TSLA"
        # self.ticker_str = "AAPL"
        # self.ticker_str = "QQQ"
        # self.ticker_str = "INTC"
        self.chosen_symbol = self.add_equity(self.ticker_str, Resolution.DAILY).Symbol
        self.set_benchmark(self.ticker_str)
        self.settings.daily_precise_end_time = False

        # --- Series buffers ---
        self.hl2s, self.highs, self.lows, self.closes = [], [], [], []
        self.lips_list, self.teeth_list, self.jaws_list = [], [], []
        self.atr_upper_list, self.atr_lower_list = [], []

        # --- Params (tune here) ---
        self.warm_up_period = 50
        self.cooldown_days_remaining = 0
        self.cooldown_days = 0
        self.jawLength, self.teethLength, self.lipsLength, self.minLength= 13, 8, 5, 3
        self.atr_period = 14
        self.atr_multiplier = 2.0

        self.start_climb = BelowToLipsCrossover(self.log)

        # --- State ---
        self.entryPrice = None
        self.highestPrice = None
        self.highestLips = None
        self.startup_check = True
        self.price_prev = None

        # New state machine for sequential crossover detection
        self.buy_alligator_detector = BuyAlligator(self.log)

        self.threshold_pct = 0.02 # set alligator opening criterion to 1%

        # --- Indicator Initializations ---
        self.atr_sl_ind = self.atr(self.chosen_symbol, self.atr_period, MovingAverageType.WILDERS, Resolution.DAILY)
        # self.jaw   = SMMAIndicator(self.jawLength)
        # self.teeth = SMMAIndicator(self.teethLength)
        # self.lips  = SMMAIndicator(self.lipsLength)

        self.jaw   = ShiftedLine(13, 8)
        self.teeth = ShiftedLine(8,  5)
        self.lips  = ShiftedLine(5,  3)

        self.initial_symbol_price = None # Set this to None initially

        # Warm up indicators with history
        history = self.history[TradeBar](
            self.chosen_symbol,
            timedelta(days=self.warm_up_period),
            Resolution.DAILY
        )
        for bar in history:
            self.atr_sl_ind.Update(bar)
            hl2 = (bar.high + bar.low) / 2.0
            self.jaw.Update(hl2)
            self.teeth.Update(hl2)
            self.lips.Update(hl2)

        # Charts
        self._init_charts()



    # ---------- Charting ----------
    def _init_charts(self):
        # Price + Alligator + markers
        chart = Chart(f"{self.ticker_str} Alligator")

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
        perf.add_series(Series("StrategyNorm", SeriesType.LINE, unit=""))
        perf.add_series(Series(self.ticker_str+"Norm", SeriesType.LINE, unit=""))
        self.add_chart(perf)

        # Average True Range
        ATRchart = Chart(f"{self.ticker_str} Average True Range from Price")
        
        series_symbol = Series(self.ticker_str, SeriesType.LINE, unit="")
        series_symbol.color = Color.BLACK
        ATRchart.add_series(series_symbol)
        
        ATR_upper = Series("upper_ATR", SeriesType.LINE, unit="")
        ATR_upper.color = Color.BLUE
        ATRchart.add_series(ATR_upper)

        ATR_lower = Series("lower_ATR", SeriesType.LINE, unit="")
        ATR_lower.color = Color.BLUE
        ATRchart.add_series(ATR_lower)

        buy_series = Series("Buy", SeriesType.SCATTER, unit="")
        buy_series.color = Color.GREEN
        buy_series.scatter_marker_symbol = ScatterMarkerSymbol.TRIANGLE
        buy_series.width = 6
        ATRchart.add_series(buy_series)

        sell_series = Series("Sell", SeriesType.SCATTER, unit="")
        sell_series.color = Color.RED
        sell_series.scatter_marker_symbol = ScatterMarkerSymbol.TRIANGLE_DOWN
        sell_series.width = 6
        ATRchart.add_series(sell_series)

        self.add_chart(ATRchart)


    # ---------- Helpers (actions) ----------
    def buy_act(self, bar, reason):
        self.set_holdings(self.chosen_symbol, 1)
        self.entryPrice = bar.close
        self.highestPrice = bar.close
        self.cooldown_days_remaining = self.cooldown_days
        self.log(f"{self.time} - BUY: {reason} @ {bar.close:.2f}")
        self.plot(f"{self.ticker_str} Alligator", "Buy", bar.close)
        self.plot(f"{self.ticker_str} Average True Range from Price", "Buy", bar.close)

    def sell_act(self, bar, reason):
        self.liquidate(self.chosen_symbol)
        self.log(f"{self.time} - SELL: {reason} @ {bar.close:.2f}")
        self.plot(f"{self.ticker_str} Alligator", "Sell", bar.close)
        self.plot(f"{self.ticker_str} Average True Range from Price", "Sell", bar.close)
        self.entryPrice = None
        self.highestPrice = None
        self.highestLips = None

        # explicitly re-arm the BelowToLipsCrossover detector so we can re-enter
        try:
            self.start_climb.rearm()
        except Exception:
            pass

    def update_performance(self, bar):
        # Check if initial_symbol_price has been set, if not, set it on the first trading day.
        if self.initial_symbol_price is None:
            self.initial_symbol_price = bar.close

        # normalized to 100 at baseline
        normalized_equity = 100.0 * (float(self.portfolio.total_portfolio_value) / self.initial_equity)
        
        # Use the pre-calculated initial_symbol_price from Initialize() for normalization.
        normalized_symbol = 100.0 * (bar.close / self.initial_symbol_price)

        self.plot("Performance", "StrategyNorm"         , normalized_equity)
        self.plot("Performance", self.ticker_str+"Norm", normalized_symbol)


    # ---------- Core computations ----------
    
    def update_indicators(self, bar):
        """Update rolling arrays and SMMA lines. Return (hl2, jaw, teeth, lips) or (None, ... ) if not ready."""
        hl2 = (bar.high + bar.low) / 2.0

        self.highs.append(bar.high)
        self.lows.append(bar.low)
        self.closes.append(bar.close)
        self.hl2s.append(hl2)

        # Need at least one full period of the longest SMMA
        min_len = max(self.jawLength, self.teethLength, self.lipsLength) + 1
        if len(self.hl2s) < min_len:
            return None, None, None, None, None, None

        jaw = self.jaw.Update(hl2)
        teeth = self.teeth.Update(hl2)
        lips = self.lips.Update(hl2)


        self.lips_list.append(lips[0])
        self.teeth_list.append(teeth[0])
        self.jaws_list.append(jaw[0])

          # ATR update   ### ATR
        self.atr_sl_ind.Update(bar)
        upper_ATR, lower_ATR = None, None
        if self.atr_sl_ind.IsReady:
            upper_ATR = bar.close + self.atr_multiplier * self.atr_sl_ind.Current.Value
            lower_ATR = bar.close - self.atr_multiplier * self.atr_sl_ind.Current.Value
            self.atr_upper_list.append(upper_ATR)
            self.atr_lower_list.append(lower_ATR)


        return hl2, jaw, teeth, lips, upper_ATR, lower_ATR



    # ---------- Entry / Exit ----------
    def mouth_open(self, bar, lips, teeth, jaw):
        # threshold percentage of the Jaw line.
        distance_threshold = jaw[0] * self.threshold_pct
        
        # Calculate the absolute differences between the three lines.
        jaw_teeth_diff = abs(jaw[0] - teeth[0])
        jaw_lips_diff = abs(jaw[0] - lips[0])
        teeth_lips_diff = abs(teeth[0] - lips[0])

        mouth_open = jaw_teeth_diff > distance_threshold and \
               jaw_lips_diff > distance_threshold and \
               teeth_lips_diff > distance_threshold

        return mouth_open


    def check_entry(self, bar, hl2, jaw, teeth, lips):
        """Entry logic including startup buy-on-trend (only once ever)."""
        # check price trends up two previous points (2 days)
        price_trend = True

        #.......simple startup buy on trend...................
        if len(self.closes) >= 20 and len(self.closes) < self.warm_up_period: # keeps this for the begining only
            if lips[0]>teeth[0] and teeth[0]>jaw[0] and bar.close>lips[0]:
                self.buy_act(bar, "Early trend following entry")
                return True

        if len(self.closes)>=3:
            if bar.close > self.closes[-2] and self.closes[-2]>self.closes[-3]:
                price_trend = True
            else:
                price_trend = False

        mouth_open = self.mouth_open(bar, lips, teeth, jaw)
        
        buy_alligator_detected = self.buy_alligator_detector.buy_condition(bar.close, jaw, teeth, lips)
        
        price_crossing_lips_up = self.start_climb.update_state(bar.close, jaw, teeth, lips)


        min_lips_teeth_distance = lips[0]-teeth[0]>self.atr_sl_ind.current.value

        lips_and_teeth_trending_down = False
        if len(self.lips_list)>3:
            lips_and_teeth_trending_down = self.lips_list[-2]>self.lips_list[-1] or self.lips_list[-3]>self.lips_list[-2]
    

        if buy_alligator_detected and price_trend and mouth_open and min_lips_teeth_distance:
            self.buy_act(bar, "Alligator shows signs of trend up - we buy  ")
            
        elif price_crossing_lips_up and not lips_and_teeth_trending_down:
            self.buy_act(bar, " bullish price crossing lips  ")
        else:
            return False

  

    def check_exit(self, bar, jaw, teeth, lips):
        """Unified exit logic: trailing stop, hard stop, and cross exits."""
        if self.entryPrice is None:
            return

        price = bar.close

        # lips trend exit
        if len(self.lips_list)>4:
            if self.lips_list[-2]>self.lips_list[-1] and self.lips_list[-3]>self.lips_list[-2]: 
                threshold = self.atr_sl_ind.current.value
                if lips[0]-teeth[0]<threshold and self.lips_list[-1] - self.teeth_list[-1]<threshold:
                    self.sell_act(bar, f"lips are trending down and distance between both lines is smaller then atr")
                    return

        # cross exits 
        if price<lips[0]:
            self.sell_act(bar, f"price at close < lips of alligator lines ")
            return

        if price<teeth[0]:
            self.sell_act(bar, f"price at close < teeth of alligator lines ")
            return

        if lips[0]<teeth[0]:
            self.sell_act(bar, f"price at close < mouth closing, lips crossed teeth line ")
            return



        # trailing stops:
        # hard stops:

        

    # ---------- Main Bar Handler ----------
    def OnData(self, data):
        # ---------- basic guards ----------
        if not data.ContainsKey(self.chosen_symbol):
            return

        if not self.atr_sl_ind.IsReady:
            return

        bar = data[self.chosen_symbol]
        if bar is None:
            return

        self.price = bar.close

        # ---------- update indicators & rolling series ----------
        hl2, jaw, teeth, lips, upper_ATR, lower_ATR = self.update_indicators(bar)
        if hl2 is None:
            return
        if self.initial_symbol_price is None:
            self.initial_symbol_price = bar.close # This is the crucial line to add

        if hl2 is not None:
            # ---------- plot price & alligator lines ----------
            symbol_price = self.securities[self.chosen_symbol].price
            self.plot(f"{self.ticker_str} Alligator", self.ticker_str, symbol_price)
            self.plot(f"{self.ticker_str} Alligator", "Jaw",   jaw[0])
            self.plot(f"{self.ticker_str} Alligator", "Teeth", teeth[0])
            self.plot(f"{self.ticker_str} Alligator", "Lips",  lips[0])
            
            self.plot(f"{self.ticker_str} Average True Range from Price", self.ticker_str, symbol_price)
            self.plot(f"{self.ticker_str} Average True Range from Price", "upper_ATR"      , upper_ATR   )
            self.plot(f"{self.ticker_str} Average True Range from Price", "lower_ATR"      , lower_ATR   )


        # ---------- Entry / Exit decision ----------
        if not self.portfolio.invested:
            self.check_entry(bar, hl2, jaw, teeth, lips)

        else:
            if self.cooldown_days_remaining == 0:
                self.check_exit(bar, jaw, teeth, lips)

        # ---------- update performance plot & prev values ----------
        self.update_performance(bar)
        self.price_prev = bar.close

        if self.cooldown_days_remaining > 0:
            self.cooldown_days_remaining -= 1
