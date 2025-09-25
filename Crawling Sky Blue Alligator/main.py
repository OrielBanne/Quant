# region imports
from AlgorithmImports import *
# endregion

class CrawlingSkyBlueAlligator(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 2, 16)
        self.set_cash(100000)
        self.add_equity("SPY", Resolution.MINUTE)
        self.add_equity("BND", Resolution.MINUTE)
        self.add_equity("AAPL", Resolution.MINUTE)

    def on_data(self, data: Slice):
        if not self.portfolio.invested:
            self.set_holdings("SPY", 0.33)
            self.set_holdings("BND", 0.33)
            self.set_holdings("AAPL", 0.33)
