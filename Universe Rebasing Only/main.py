# region imports
from AlgorithmImports import *
from datetime import timedelta
# endregion

class UniverseRebasingOnly(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2019, 1, 1)
        # self.SetEndDate(2021, 1, 1)
        self.SetCash(100000)
        self.rebalanceTime = datetime.min
        self.activeStocks = set()
        self.next_universe_refresh = self.time

        # self.AddUniverse(self.CoarseFilter, self.FineFilter)
        self.AddUniverse(self.CoarseFilter)
        self.UniverseSettings.Resolution = Resolution.HOUR
        
        self.portfolioTargets = []

    def CoarseFilter(self, coarse):
        if self.time <= self.next_universe_refresh:
            return Universe.UNCHANGED
        self.next_universe_refresh = self.time + timedelta(days=30)

        filtered = [c for c in coarse
                    if c.HasFundamentalData
                    and c.Price > 5 # price > $5
                    and c.MarketCap > 2000000000 # market cap > $2B
                    # ---- skip symbols younger than N calendar days ----
                    and (self.time - c.Symbol.ID.Date).days >= 180]  # 180 days since IPO

        selected = sorted(filtered,
                        key=lambda c: c.DollarVolume,
                        reverse=True)[:35] # 35 equities is the final filter size
        return [c.Symbol for c in selected]

    def FineFilter(self, fine):
        sortedByPE = sorted(fine, key=lambda x: x.MarketCap)
        return [x.Symbol for x in sortedByPE if x.MarketCap > 0][:10]

    def OnSecuritiesChanged(self, changes):
        # close positions in removed securities
        for x in changes.RemovedSecurities:
            self.Liquidate(x.Symbol)
            self.activeStocks.remove(x.Symbol)
        
        # can't open positions here since data might not be added correctly yet
        for x in changes.AddedSecurities:
            self.activeStocks.add(x.Symbol)   

        # adjust targets if universe has changed
        self.portfolioTargets = [PortfolioTarget(symbol, 1/len(self.activeStocks)) 
                            for symbol in self.activeStocks]

    def OnData(self, data):

        if self.portfolioTargets == []:
            return
        
        for symbol in self.activeStocks:
            if symbol not in data:
                return
        
        self.SetHoldings(self.portfolioTargets)
        
        self.portfolioTargets = []
