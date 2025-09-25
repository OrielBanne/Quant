# region imports
from AlgorithmImports import *
# from qcalgostubs import QCAlgorithm as QCAL # only for local autocomplete 
# endregion


class SmoothYellowGreenBull(QCAlgorithm):

    def Initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_cash(100000)
        spy = self.AddEquity("SPY", Resolution.DAILY)
        # self.AddEquity("BND", Resolution.MINUTE)
        # self.AddEquity("AAPL", Resolution.MINUTE)
        self.spy = spy.symbol
        self.set_benchmark("SPY")
        self.set_brokerage_model(BrokerageName.ALPACA, AccountType.MARGIN)
        self.entryPrice = 0
        self.period = timedelta(1)
        self.nextEntryTime = self.Time
 
    def OnData(self, data):
        if not data.ContainsKey(self.spy) or data[self.spy] is None:
            return

        
        price = data[self.spy].Close

        if not self.portfolio.Invested:
            if self.nextEntryTime <= self.Time:
                # self.MarketOrder(self.spy, int(self.Portofolio.cash / price))
                self.SetHoldings(self.spy, 1.00) #invest 33% of protfolio in spy
                # self.set_holdings("BND", 0.33)
                # self.set_holdings("AAPL", 0.33)
                self.Log("BUY SPY @" + str(price))
                self.entryPrice = price
        elif self.entryPrice * 1.15 < price or self.entryPrice * 0.93 > price:
            self.Liquidate(self.spy)
            self.Log("SELL SPY @" + str(price))
            self.nextEntryTime = self.Time + self.period
