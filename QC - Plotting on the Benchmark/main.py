# region imports
from AlgorithmImports import *
# endregion

from collections import deque

class AdaptableSkyBlueHornet(QCAlgorithm):

    def Initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2021, 1, 1)
        self.set_cash(100000)
        self.spy = self.add_equity("SPY", Resolution.DAILY).Symbol
        
        # self.sma = self.SMA(self.spy, 30, Resolution.Daily)
        
        # History warm up for shortcut helper SMA indicator
        # closing_prices = self.History(self.spy, 30, Resolution.Daily)["close"]
        # for time, price in closing_prices.loc[self.spy].items():
        #    self.sma.Update(time, price)
        
        # # Custom SMA indicator
        self.sma = CustomSimpleMovingAverage("CustomSMA", 30)
        self.register_indicator(self.spy, self.sma, Resolution.DAILY)

    
    def OnData(self, data):
        if not self.sma.is_ready:
            return
        
        # Save high, low, and current price
        hist = self.history(self.spy, timedelta(365), Resolution.DAILY)
        low = min(hist["low"])
        high = max(hist["high"])
        
        price = self.securities[self.spy].Price
        
        # Go long if near high and uptrending
        if price * 1.05 >= high and self.sma.current.value < price:
            if not self.portfolio[self.spy].is_long:
                self.set_holdings(self.spy, 1)
        
        # Go short if near low and downtrending
        elif price * 0.95 <= low and self.sma.current.value > price:  
            if not self.Portfolio[self.spy].IsShort:
                self.SetHoldings(self.spy, -1)
        
        # Otherwise, go flat
        else:
            self.Liquidate()
        
        self.Plot("Benchmark", "52w-High", high)
        self.Plot("Benchmark", "52w-Low", low)
        self.Plot("Benchmark", "SMA", self.sma.current.value)


class CustomSimpleMovingAverage(PythonIndicator):
    
    def __init__(self, name, period):
        self.Name = name
        self.Time = datetime.min
        self.Value = 0
        self.queue = deque(maxlen=period)

    def Update(self, input):
        self.queue.appendleft(input.Close)
        self.Time = input.EndTime
        count = len(self.queue)
        self.Value = sum(self.queue) / count
        # returns true if ready
        return (count == self.queue.maxlen)
