from AlgorithmImports import *

class EmaLipsVsBuyHold(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2023, 1, 1)
        self.SetCash(100000)

        self.symbol = self.AddEquity("AAPL", Resolution.Daily).Symbol

        # --- Strategy indicators ---
        self.ema8 = self.EMA(self.symbol, 8, Resolution.Daily)
        self.ema14 = self.EMA(self.symbol, 14, Resolution.Daily)
        self.lips = self.EMA(self.symbol, 8, Resolution.Daily)  # Simplified lips

        # Track entry state
        self.inPosition = False

        # --- Buy & hold portfolio ---
        self.holdings = 0
        self.initial_price = None
        self.hold_cash = 100000

        # --- Chart setup ---
        chart = Chart("Equity Comparison")
        chart.AddSeries(Series("Strategy", SeriesType.Line, 0))
        chart.AddSeries(Series("BuyHold", SeriesType.Line, 0))
        self.AddChart(chart)

    def OnData(self, data: Slice):
        # Avoid NoneType error
        if not data.ContainsKey(self.symbol):
            return

        if not (self.ema8.IsReady and self.ema14.IsReady and self.lips.IsReady):
            return

        if self.symbol in data:  # make sure there is a bar for this symbol
            bar = data[self.symbol]  # this is a TradeBar
            price = bar.Close

        # --- Strategy logic ---
        if not self.inPosition:
            if self.ema8.Current.Value > self.ema14.Current.Value and price > self.lips.Current.Value:
                self.SetHoldings(self.symbol, 1)
                self.inPosition = True
        else:
            if price < self.ema14.Current.Value or price < self.lips.Current.Value:
                self.Liquidate(self.symbol)
                self.inPosition = False

        # --- Buy & Hold simulation ---
        if self.initial_price is None:
            self.initial_price = price
            self.holdings = self.hold_cash / price

        hold_equity = self.holdings * price
        strat_equity = self.Portfolio.TotalPortfolioValue

        # --- Plot comparison ---
        self.Plot("Equity Comparison", "Strategy", strat_equity)
        self.Plot("Equity Comparison", "BuyHold", hold_equity)
