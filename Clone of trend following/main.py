# region imports
from datetime import datetime
from AlgorithmImports import *
from alpha import custom_alpha

# endregion


class CompetitionAlgorithm(QCAlgorithm):
    
    def Initialize(self):

        # Backtest parameters
        self.SetStartDate(2023, 1, 1)
        # self.SetEndDate(2024, 12, 1)
        self.SetCash(100000)
        

        # Parameters:
        self.final_universe_size = 400
        self.day_to_rebalance = 30

        # Universe selection
        self.rebalanceTime = self.time
        self.universe_type = "equity"

        if self.universe_type == "equity":
            self.Log("adding equitiy universe")
            self.add_universe(self.equity_filter)
            #self.add_universe(CryptoUniverse.coinbase(self._crypto_universe_filter))

        self.universe_settings.Resolution = Resolution.HOUR

        self.set_portfolio_construction(self.MyPCM())
        self.set_alpha(custom_alpha(self))
        self.set_execution(VolumeWeightedAveragePriceExecutionModel())
        self.add_risk_management(NullRiskManagementModel())
 
        # set account type
        #self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage, AccountType.Margin)

        
        self.spy = self.add_equity("SPY", Resolution.MINUTE).Symbol
        self.position_open = False
        self.spy_buffer = 500  # keep $500 uninvested to avoid overcommitting

        # Schedule buy at 3:59 PM (1 min before close)
        self.Schedule.On(
            self.DateRules.EveryDay(self.spy),
            self.TimeRules.At(15, 59),
            self.BuyAtClose
        )

        # Schedule sell at 9:31 AM (1 min after open to avoid price anomalies)
        self.Schedule.On(
            self.DateRules.EveryDay(self.spy),
            self.TimeRules.At(9, 31),
            self.SellAtOpen
        )

        self.SetWarmUp(timedelta(days=30))

    def BuyAtClose(self):
        if self.IsWarmingUp:
            return
        if not self.CurrentSlice.ContainsKey(self.spy):
            return
        if not self.Portfolio[self.spy].Invested:
            price = self.Securities[self.spy].Price
            cash = self.Portfolio.Cash
            cash_to_use = cash - self.spy_buffer
            quantity = int(cash_to_use / price)

            if quantity > 0:
                self.MarketOrder(self.spy, quantity)
                self.Debug(f"BUY {quantity} shares of {self.spy} at close: {self.Time}")
            else:
                self.Debug(f"Not enough cash to buy SPY at {self.Time}")

    def SellAtOpen(self):
        if self.IsWarmingUp:
            return
        if not self.CurrentSlice.ContainsKey(self.spy):
            return
        if self.Portfolio[self.spy].Invested:
            self.Liquidate(self.spy)
            self.Debug(f"SELL {self.spy} at open: {self.Time}")

    def _crypto_universe_filter(self, data):
        if self.Time <= self.rebalanceTime:
            return self.Universe.Unchanged
        self.rebalanceTime = self.Time + timedelta(days=self.day_to_rebalance)
        # Define the universe selection function
        sorted_by_vol = sorted(data, key=lambda x: x.volume_in_usd, reverse=True)[:30]
        first_of_tickers_added = ['']
        new_universe = []
        for cf in sorted_by_vol:
            # remove USD and EUR from string
            sym_string = str(cf.symbol).replace("USDT", "").replace("USDC", "").replace("USD", "")\
                .replace("EUR", "").replace("GBP", "").split(" ")[0]
            self.Log("sym_string: " + sym_string)
            if sym_string not in first_of_tickers_added:
                first_of_tickers_added.append(sym_string)
                new_universe.append(cf)
        sorted_by_vol = sorted(new_universe, key=lambda x: x.volume_in_usd, reverse=True)
        final =  [cf.symbol for cf in sorted_by_vol][:10]
        self.Log("final: ")
        for i in final:
            self.Log(str(i))
        return final

        
    def equity_filter(self, data):
        self.Log("in filter for equities")
        # Rebalancing monthly
        if self.Time <= self.rebalanceTime:
            return self.Universe.Unchanged
        self.rebalanceTime = self.Time + timedelta(days=self.day_to_rebalance)
        
        sortedByDollarVolume = sorted(data, key=lambda x: x.DollarVolume, reverse=True)
        final = [x.Symbol for x in sortedByDollarVolume if x.HasFundamentalData and x.price > 10 and x.MarketCap > 2000000000][:self.final_universe_size]
        self.Log("coming out of course: " + str(len(final)))
        return final
    class MyPCM(InsightWeightingPortfolioConstructionModel): 
        # override to set leverage higher
        def CreateTargets(self, algorithm, insights): 
            targets = super().CreateTargets(algorithm, insights) 
            return [PortfolioTarget(x.Symbol, x.Quantity * 1.85) for x in targets]
        



        
        



    








            

            

     
