# region imports
from AlgorithmImports import *
# endregion

# Your New Python File
class CustomBollingerBands:
    def __init__(self, algorithm, symbol, period=20, deviations=2):
        self.algorithm = algorithm
        self.symbol = symbol
        self.bbands = algorithm.BB(symbol, period, deviations, MovingAverageType.SIMPLE, Resolution.DAILY)

    def Update(self, data):
        if self.symbol in data and data[self.symbol] is not None:
            self.bbands.Update(data[self.symbol].EndTime, data[self.symbol].Close)

    def HasSignal(self):
        return self.bbands.IsReady


class RSIIndicator:
    def __init__(self, algorithm, symbol, period=14):
        self.algorithm = algorithm
        self.symbol = symbol
        self.rsi = algorithm.RSI(symbol, period, MovingAverageType.SIMPLE, Resolution.DAILY)

    def Update(self, data):
        if self.symbol in data and data[self.symbol] is not None:
            self.rsi.Update(data[self.symbol].EndTime, data[self.symbol].Close)

    def HasSignal(self):
        return self.rsi.IsReady


class HistoricalVolatility:
    def __init__(self, algorithm, symbol, period=20):
        self.algorithm = algorithm
        self.symbol = symbol
        self.returns = RollingWindow[float](period)

    def Update(self, data):
        if self.symbol in data and data[self.symbol] is not None:
            price = data[self.symbol].Close
            if self.returns.count > 0 and self.returns[0] != 0:
                self.returns.add(np.log(price / self.returns[0]))
            else:
                self.returns.add(0)

    def GetVolatility(self):
        if self.returns.is_ready:
            return np.std(list(self.returns))
        return None


class TrendFilter:
    def __init__(self, algorithm, symbol, sma_period=50):
        self.algorithm = algorithm
        self.symbol = symbol
        self.sma = algorithm.SMA(symbol, sma_period, Resolution.DAILY)

    def Update(self, data):
        if self.symbol in data and data[self.symbol] is not None:
            self.sma.Update(data[self.symbol].EndTime, data[self.symbol].Close)

    def IsUptrend(self):
        if self.sma.IsReady:
            price = self.algorithm.Securities[self.symbol].Price
            return price > self.sma.Current.Value
        return False

    def IsDowntrend(self):
        if self.sma.IsReady:
            price = self.algorithm.Securities[self.symbol].Price
            return price < self.sma.Current.Value
        return False
