# region imports
from AlgorithmImports import *
from datetime import timedelta
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
        return Insight.Group([
            # create a grouped insight
            Insight.Price(ordered[0]['symbol'], timedelta(1), InsightDirection.UP),
            Insight.Price(ordered[1]['symbol'], timedelta(1), InsightDirection.FLAT)])


class FrameworkAlgorithm(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2023, 12, 28)
        self.set_cash(100000)


        # 1 set the NullUniverseSelectionModel() and 
        # next change this part to be real universe selection model
        # manually create a universe:
        symbols =[
            Symbol.Create("SPY", SecurityType.Equity, Market.USA),
            Symbol.Create("BND", SecurityType.Equity, Market.USA)
            ]
        self.UniverseSettings.Resolution = Resolution.Daily
        # self.AddUniverseSelection(ManualUniverseSelectionModel(self.symbols))
        self.SetUniverseSelection(ManualUniverseSelectionModel(symbols))

        # 2 set the AlphaModel() NullAlphaModel is an option
        self.SetAlpha(MOMAlphaModel())

        # 3 set the NullPortfolioConstructionModel()
        # self.SetPortfolioConstruction(NullPortfolioConstructionModel())
        # set the portfolio model into an Equal Weighting Portfolio Construction Model
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())

        # 4 set the NullRiskManagementModel()
        # self.SetRiskManagement(NullRiskManagementModel()) # this is an option
        # set the risk management handler to use a 2% maximum drawdown
        self.SetRiskManagement(MaximumDrawdownPercentPerSecurity(0.02))

        # 5 set the NullExecutionModel()
        # self.SetExecution(NullExecutionModel())
        self.SetExecution(ImmediateExecutionModel())
