# region imports
from AlgorithmImports import *
from datetime import timedelta
from QuantConnect import Chart, Series, SeriesType
# endregion

# Momentum based alphe model
# the Alpha Model's Job - is to simply produce predictions
class MOMAlphaModel(AlphaModel):
    def __init__(self):
        self.mom = []

    def OnSecuritiesChanged(self, algorithm, changes):
        # 1 initialize a 14 - day momentum indicator
        for security in changes.AddedSecurities:
            symbol = security.Symbol
            self.mom.append({"symbol":symbol, 
                            "indicator": algorithm.MOM(symbol, 14, Resolution.DAILY)})

    def Update(self, algorithm, data):
        # 2 sort the list of dictionaries by indicator in descending order
        ordered = sorted(self.mom, key=lambda kv: kv["indicator"].Current.Value, reverse = True)

        # 3 return a group of insights, emitting InsightDirection.Up for the first item of ordered,
        #   and InsightDirection.Flat for the second
        return Insight.group([
            # create a grouped insight
            Insight.price(ordered[0]['symbol'], timedelta(1), InsightDirection.UP),
            Insight.price(ordered[1]['symbol'], timedelta(1), InsightDirection.FLAT)])


# SMA based Alpha Model:
class DualSmaAlphaModel(AlphaModel):
    def __init__(self, fast_period=2, slow_period=48):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.symbol_data = {}

    def Update(self, algorithm, data):
        insights = []

        for symbol, sd in self.symbol_data.items():
            if not sd.IsReady:
                continue
            

            # Plot price every update
            sd.PlotPrice()

            price = algorithm.Securities[symbol].Price
            fast = sd.fast.Current.Value
            slow = sd.slow.Current.Value

            # Entry condition: SMA(5) crosses above SMA(20)
            if not sd.invested and fast > slow and sd.fast.IsReady and sd.slow.IsReady:
                insights.append(Insight.price(symbol, timedelta(days=5), InsightDirection.UP))
                sd.invested = True
                sd.PlotSignal("buy")

            # Exit condition: Price < 90% of SMA(20)
            elif sd.invested and price < 0.9 * slow:
                insights.append(Insight.price(symbol, timedelta(1), InsightDirection.FLAT))
                sd.invested = False
                sd.PlotSignal("sell")

        return insights

    def OnSecuritiesChanged(self, algorithm, changes):
        for security in changes.AddedSecurities:
            symbol = security.Symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = SymbolData(algorithm, symbol, self.fast_period, self.slow_period)
        
        for security in changes.RemovedSecurities:
            symbol = security.Symbol
            if symbol in self.symbol_data:
                self.symbol_data.pop(symbol)

class SymbolData:
    def __init__(self, algorithm, symbol, fast_period, slow_period):
        self.symbol = symbol
        self.fast = algorithm.sma(symbol, fast_period, Resolution.HOUR)
        self.slow = algorithm.sma(symbol, slow_period, Resolution.HOUR)
        self.invested = False
        self.algorithm = algorithm
        self.plot_name = str(symbol)
        algorithm.plot_indicator(self.plot_name, self.fast, self.slow)
        algorithm.Plot(self.plot_name, "Signal", 0)

    @property
    def IsReady(self):
        return self.fast.IsReady and self.slow.IsReady

    def PlotPrice(self):
        price = self.algorithm.Securities[self.symbol].Price
        self.algorithm.Plot(self.plot_name, "Price", price)

    def PlotSignal(self, signal_type):
        price = self.algorithm.Securities[self.symbol].Price
        if signal_type == "buy":
            self.algorithm.Plot(self.plot_name, "Signal", price)
        elif signal_type == "sell":
            self.algorithm.Plot(self.plot_name, "Signal", price)
        else:
            self.algorithm.Plot(self.plot_name, "Signal", None)
        
        

    def plot_marker(self, marker_type):
        price = self.algorithm.securities[self.symbol].price
        if marker_type == "entry":
            self.algorithm.plot(self.plot_name, "EntryMarker", price)
        elif marker_type == "exit":
            self.algorithm.plot(self.plot_name, "ExitMarker", price)



class FrameworkAlgorithm(QCAlgorithmFramework):
    def initialize(self):
        self.set_start_date(2023, 12, 28)
        self.set_cash(100000)

        # manually create a universe:
        symbols =[
            Symbol.create("SPY", SecurityType.EQUITY, Market.USA),
            Symbol.create("NVDA", SecurityType.EQUITY, Market.USA)
            ]
        # self.UniverseSettings.Resolution = Resolution.HOUR
        self.add_universe_selection(ManualUniverseSelectionModel(symbols))

        # 2 set the AlphaModel() NullAlphaModel is an option
        self.set_alpha(DualSmaAlphaModel())

        # 3 set the NullPortfolioConstructionModel()
        # self.SetPortfolioConstruction(NullPortfolioConstructionModel())
        # set the portfolio model into an Equal Weighting Portfolio Construction Model
        self.set_portfolio_construction(EqualWeightingPortfolioConstructionModel())

        # 4 set the NullRiskManagementModel()
        # self.SetRiskManagement(NullRiskManagementModel()) # this is an option
        # set the risk management handler to use a 2% maximum drawdown
        self.set_risk_management(MaximumDrawdownPercentPerSecurity(0.04))

        # 5 set the NullExecutionModel()
        # self.SetExecution(NullExecutionModel())
        self.set_execution(ImmediateExecutionModel())
