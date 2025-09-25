# region imports
from AlgorithmImports import *
# endregion

class FormalOrangeLion(QCAlgorithm):

    def initialize(self):
        self.initial_portfolio_investement = 100000
        self.set_start_date(2023, 11, 14)
        self.set_cash(self.initial_portfolio_investement)
        self.spy = self.add_equity("SPY", Resolution.MINUTE).symbol
        self.benchmark_symbol = self.spy
        self.initial_benchmark_price = None
        
    


        self.entryTicket = None
        self.stopMarketTicket = None
        self.entryTime = datetime.min
        self.stopMarketOrderFillTime = datetime.min


        self.highestPrice = 0



    def OnData(self, data):

        # wait the waitting time (here 3 days) after the last exit
        if (self.time - self.stopMarketOrderFillTime).days < 1:
            return

        price  = self.securities[self.spy].price

        # send entry limit order
        if not self.portfolio.invested and not self.transactions.get_open_orders(self.spy):
            quantity = self.calculate_order_quantity(self.spy, 0.4)
            self.entryTicket = self.limit_order(self.spy, quantity, price, "Entry Order")
            self.entryTime = self.time

        # move limit price up if not filled after 1 day
        if (self.time - self.entryTime).days > 1 and self.entryTicket.status != OrderStatus.FILLED:
            self.entryTime = self.time
            updateFields = UpdateOrderFields()
            updateFields.limit_price = price
            self.entryTicket.update(updateFields)


        # move up trailling stop price
        if self.stopMarketTicket is not None and self.portfolio.invested:
            if price > self.highestPrice:
                self.highestPrice = price
                updateFields = UpdateOrderFields()
                updateFields.stop_price = price * 0.97
                self.stopMarketTicket.update(updateFields)


        benchmark_price = data[self.benchmark_symbol].Price
        portfolio_value = self.portfolio.total_portfolio_value

        self.log("benchmark_price", benchmark_price)
        self.log("portfolio_value",portfolio_value)


        self.initial_portfolio_value = self.initial_portfolio_investement
        if self.initial_benchmark_price is None:
            self.initial_benchmark_price = benchmark_price
        if self.initial_portfolio_investement is None:
            self.initial_portfolio_value = portfolio_value
            self.initial_benchmark_price = benchmark_price

        self.log("initial_benchmark_price", self.initial_benchmark_price)
        self.log("initial_portfolio_value", self.initial_portfolio_value)

        

        # Normalize to 100
        normalized_portfolio = 100 * portfolio_value / self.initial_portfolio_investement
        normalized_benchmark = 100 * benchmark_price / self.initial_benchmark_price

        self.plot("Normalized", "Portfolio", normalized_portfolio)
        self.plot("Normalized", "Benchmark", normalized_benchmark)

    def OnOrderEvent(self, orderEvent):
        if orderEvent.status != OrderStatus.FILLED:
            return


        # send stop loss order if entry limit order is filled
        if self.entryTicket is not None and self.entryTicket.order_id == orderEvent.order_id:
            self.stopMarketTicket = self.stop_market_order(self.spy, 
                                                            -self.entryTicket.quantity,
                                                            0.95* self.entryTicket.average_fill_price)


        # save fill time of stop loss order
        if self.stopMarketTicket is not None and self.stopMarketTicket.order_id == orderEvent.order_id:
            self.stopMarketOrderFillTime = self.time
            self.highestPrice = 0

