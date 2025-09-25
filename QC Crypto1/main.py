# region imports
from AlgorithmImports import *
# endregion

class CryptoVolatilityBreakout(QCAlgorithm):
    def Initialize(self):
        self.set_start_date(2020, 1, 1)
        # self.SetEndDate(2023, 12, 31)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.MINUTE

        self.crypto_symbols = ["BTCUSD", "ETHUSD", "ADAUSD",
                                 "SOLUSD", "USDTUSD", "XRPUSD", 
                                 "SOLUSD", "DOGEUSD"]
        self.symbol_data = {}

        for ticker in self.crypto_symbols:
            symbol = self.add_crypto(ticker, Resolution.MINUTE, Market.GDAX).Symbol
            self.symbol_data[symbol] = SymbolData(self, symbol)

        self.set_warmup(timedelta(days=30))
        self.last_rebalance = self.time

        self.add_risk_management(MaximumDrawdownPercentPortfolio(0.05))

    def OnData(self, slice):
        if self.is_warming_up:
            return

        for symbol, sd in self.symbol_data.items():
            if not slice.ContainsKey(symbol):
                continue

            if not sd.IsReady:
                continue

            price = slice[symbol].Price

            # Breakout entry signal
            if not self.portfolio[symbol].invested and sd.ShouldEnterLong():

                security = self.securities[symbol]
                price = security.Price

                # Position size = max affordable shares/contracts
                affordable_quantity = int(self.portfolio.margin_remaining / price)

                # Cap to a max target weight (e.g. 40% of portfolio)
                max_quantity = abs(self.calculate_order_quantity(symbol, 0.4))

                # Use the smaller of the two
                final_quantity = min(affordable_quantity, max_quantity)

                if final_quantity > 0:
                    self.market_order(symbol, final_quantity)
                    sd.EntryPrice = price


            # Exit conditions
            elif self.portfolio[symbol].invested:
                if sd.ShouldExit(price):
                    self.liquidate(symbol)


class SymbolData:
    def __init__(self, algo, symbol):
        self.algo = algo
        self.symbol = symbol
        self.bb = algo.BB(symbol, 20, 1, MovingAverageType.TRIPLE_EXPONENTIAL, Resolution.MINUTE)
        self.atr = algo.ATR(symbol, 14, MovingAverageType.SIMPLE, Resolution.MINUTE)
        self.EntryPrice = None

    @property
    def IsReady(self):
        return self.bb.IsReady and self.atr.IsReady

    def ShouldEnterLong(self):
        price = self.algo.Securities[self.symbol].Price
        return price > (self.bb.MiddleBand.Current.Value + 0.3*self.atr.Current.Value) and self.atr.Current.Value > 3

    def ShouldExit(self, price):
        # Exit if price falls below entry - 1.5*ATR or exceeds entry + 3*ATR
        atr = self.atr.Current.Value
        if atr == 0 or self.EntryPrice is None:
            return False

        stop_loss = self.EntryPrice *0.97
        take_profit = self.EntryPrice + 5 * atr

        return price < stop_loss or price > take_profit
