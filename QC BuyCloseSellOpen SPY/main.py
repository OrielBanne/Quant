# region imports
from AlgorithmImports import *
# endregion

class BuyCloseSellOpenAlgorithm(QCAlgorithm):
    def Initialize(self):
        self.set_start_date(2023, 1, 1)
        # self.SetEndDate(2023, 12, 31)
        self.set_cash(100000)
        
        self.spy = self.add_equity("SPY", Resolution.MINUTE).Symbol
        self.position_open = False

        # Schedule buy at 3:59 PM (1 min before close)
        self.schedule.on(
            self.date_rules.every_day(self.spy),
            self.time_rules.at(15, 59),
            self.BuyAtClose
        )

        # Schedule sell at 9:31 AM (1 min after open to avoid price anomalies)
        self.schedule.on(
            self.date_rules.every_day(self.spy),
            self.time_rules.at(9, 31),
            self.SellAtOpen
        )

    def BuyAtClose(self):
        if not self.portfolio[self.spy].invested:
            quantity = self.calculate_order_quantity(self.spy, 1.0)
            self.market_order(self.spy, quantity)
            self.debug(f"Buy {self.spy} at close: {self.time}")
            self.position_open = True

    def SellAtOpen(self):
        if self.portfolio[self.spy].invested:
            self.liquidate(self.spy)
            self.debug(f"Sell {self.spy} at open: {self.time}")
            self.position_open = False
