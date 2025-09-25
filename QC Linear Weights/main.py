# region imports
from AlgorithmImports import *
from datetime import timedelta
from sklearn.preprocessing import MinMaxScaler
import numpy as np
# endregion


def calculate_linear_weights(symbols):
    """
    Optimized linear weighting:
    - Best symbol gets 2x the weight of the worst
    - Linearly interpolated in between
    """
    n = len(symbols)
    if n <= 1:
        return [1.0]

    worst_weight = 2.0 / (3.0 * n)
    best_weight = 2.0 * worst_weight
    step = (best_weight - worst_weight) / (n - 1)
    weights = [best_weight - i * step for i in range(n)]
    total = sum(weights)
    return [w / total for w in weights]


class UniverseSelectionAlgorithm(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2025, 5, 1)
        self.SetCash(100000)
        self.SetBenchmark("SPY")

        # Screening parameters
        self.min_market_cap = 1e9
        self.min_volume = 1e6
        self.min_price = 50.0
        self.pe_ratio_min = 5
        self.debt_to_equity_max = 1.0
        self.roe_min = 0.10
        self.stop_loss = 0.07  # 7% trailing stop loss

        # Tracking state
        self.entryTickets = {}
        self.stopMarketTickets = {}
        self.entryTimes = {}
        self.highestPrices = {}
        self.stopMarketOrderFillTimes = {}

        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)
        self.SetWarmup(timedelta(days=30))

        self.Schedule.On(
            self.DateRules.MonthStart(),
            self.TimeRules.At(9, 30),
            self.Rebalance
        )

    def OnWarmupFinished(self):
        self.Debug("Warmup completed. Trading logic now active.")

    def CoarseSelectionFunction(self, coarse):
        filtered = [x for x in coarse if x.HasFundamentalData and x.Price > self.min_price
                    and x.DollarVolume > self.min_volume and x.Market == Market.USA]
        sorted_by_volume = sorted(filtered, key=lambda x: x.DollarVolume, reverse=True)
        return [x.Symbol for x in sorted_by_volume[:500]]

    def FineSelectionFunction(self, fine):
        filtered = []
        for f in fine:
            if f.MarketCap < self.min_market_cap:
                continue

            pe = f.ValuationRatios.PERatio
            if pe is None or pe <= self.pe_ratio_min:
                continue

            equity = f.FinancialStatements.BalanceSheet.TotalEquity.Value
            debt = f.FinancialStatements.BalanceSheet.TotalDebt.Value
            if equity <= 0:
                continue
            d2e = debt / equity
            if d2e > self.debt_to_equity_max:
                continue

            roe = f.OperationRatios.ROE.OneYear
            if roe is None or roe < self.roe_min:
                continue

            if f.OperationRatios.RevenueGrowth.OneYear < 0:
                continue

            liabilities = f.FinancialStatements.BalanceSheet.CurrentLiabilities.Value
            assets = f.FinancialStatements.BalanceSheet.CurrentAssets.Value
            if liabilities <= 0 or (assets / liabilities) < 1.0:
                continue

            filtered.append(f)

        # Build raw feature matrix
        data = []
        symbols = []
        for f in filtered:
            roe = f.OperationRatios.ROE.OneYear
            pe = f.ValuationRatios.PERatio
            rev_growth = f.OperationRatios.RevenueGrowth.OneYear
            equity = f.FinancialStatements.BalanceSheet.TotalEquity.Value
            debt = f.FinancialStatements.BalanceSheet.TotalDebt.Value
            d2e = debt / equity if equity > 0 else 1

            if None in [roe, pe, rev_growth] or pe <= 0:
                continue

            gross_margin = f.OperationRatios.GrossMargin.Value
            rd_expense = f.FinancialStatements.IncomeStatement.ResearchAndDevelopment.Value
            total_revenue = f.FinancialStatements.IncomeStatement.TotalRevenue.Value
            rd_to_revenue = rd_expense / total_revenue if total_revenue > 0 else 0

            data.append([
                roe,
                rev_growth,
                1 / pe,
                1 / (1 + d2e),
                np.log(f.MarketCap + 1),
                gross_margin,
                rd_to_revenue
            ])

            symbols.append(f.Symbol)

        if not data:
            return []

        # Normalize all features between 0 and 1
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(data)

        # Apply weights to normalized features
        weights = [0.30,   0.30  , 0.05, 0.10     , 0.15     , 0.05, 0.05]
        #         [ROE ,   Growth, 1/PE, 1/(1+D/E), log(MCap), GM  , R&D]


        scores = X_scaled.dot(weights)

        # Rank and select top 10
        ranked = sorted(zip(symbols, scores), key=lambda x: x[1], reverse=True)
        top = [x[0] for x in ranked[:10]]

        if top:
            self.Debug(f"Selected {len(top)} stocks: {[s.Value for s in top]}")
        return top

    def OnSecuritiesChanged(self, changes):
        for security in changes.RemovedSecurities:
            self.Liquidate(security.Symbol)

    def Rebalance(self):
        symbols = list(self.ActiveSecurities.Keys)
        if not symbols:
            return

        # Get the latest slice (market data)
        slice = self.CurrentSlice

        # Filter for symbols that have up-to-date data
        tradable_symbols = [
            s for s in symbols
            if self.Securities[s].HasData and s in slice and slice[s] is not None and slice[s].Price > 0
        ]

        if not tradable_symbols:
            self.Debug("No tradable symbols with current price data.")
            return

        weights = calculate_linear_weights(tradable_symbols)
        for symbol, weight in zip(tradable_symbols, weights):
            self.SetHoldings(symbol, weight)

        self.Debug(f"Rebalanced with {len(tradable_symbols)} tradable stocks.")


    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status != OrderStatus.Filled:
            return

        symbol = orderEvent.Symbol

        if symbol in self.entryTickets and self.entryTickets[symbol].OrderId == orderEvent.OrderId:
            stop_price = (1 - self.stop_loss) * self.entryTickets[symbol].AverageFillPrice
            self.stopMarketTickets[symbol] = self.StopMarketOrder(symbol, -self.entryTickets[symbol].Quantity, stop_price)
            self.highestPrices[symbol] = self.entryTickets[symbol].AverageFillPrice
            del self.entryTickets[symbol]

        elif symbol in self.stopMarketTickets and self.stopMarketTickets[symbol].OrderId == orderEvent.OrderId:
            self.stopMarketOrderFillTimes[symbol] = self.Time
            self.highestPrices[symbol] = 0
            del self.stopMarketTickets[symbol]
            self.Debug(f"Stop loss filled for {symbol}, cooldown started")

    def OnData(self, data):
        if self.IsWarmingUp:
            return

        symbols = list(self.ActiveSecurities.Keys)
        for symbol in symbols:
            if symbol not in data or not data[symbol]:
                continue

            price = data[symbol].Price

            if symbol not in self.stopMarketOrderFillTimes:
                self.stopMarketOrderFillTimes[symbol] = self.Time - timedelta(days=31)

            if (self.Time - self.stopMarketOrderFillTimes[symbol]).days < 30:
                continue

            if (not self.Portfolio[symbol].Invested and
                symbol not in self.entryTickets and
                not self.Transactions.GetOpenOrders(symbol)):

                quantity = int((self.Portfolio.Cash / len(symbols)) / price)
                if quantity > 0:
                    self.entryTickets[symbol] = self.LimitOrder(symbol, quantity, price)
                    self.entryTimes[symbol] = self.Time

            if (symbol in self.entryTickets and
                symbol in self.entryTimes and
                (self.Time - self.entryTimes[symbol]).days > 1 and
                self.entryTickets[symbol].Status != OrderStatus.Filled):

                update = UpdateOrderFields()
                update.LimitPrice = price
                self.entryTickets[symbol].Update(update)
                self.entryTimes[symbol] = self.Time

            if (symbol in self.stopMarketTickets and
                self.Portfolio[symbol].Invested and
                price > self.highestPrices[symbol]):

                self.highestPrices[symbol] = price
                update = UpdateOrderFields()
                update.StopPrice = price * (1 - self.stop_loss)
                self.stopMarketTickets[symbol].Update(update)
