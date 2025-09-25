# region imports
from AlgorithmImports import *
from datetime import datetime
from QuantConnect.Data.UniverseSelection import *
from Selection.FundamentalUniverseSelectionModel import FundamentalUniverseSelectionModel 
# endregion

class LiquidValueStocks(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2023, 12, 28)
        self.set_cash(100000)
        # create an instance of the LiquidValueUniverseSelectionModel and set it to Hourly resolution
        self.UniverseSettings.Resolution = Resolution.HOUR 
        self.AddUniverseSelection(LiquidValueUniverseSelectionModel())
        # self.AddAlpha(NullAlphaModel())
        # create an instance of LongShortEYAlphaModel:
        self.AddAlpha(LongShortEYAlphaModel())

        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())
        self.SetExecution(ImmediateExecutionModel())


# Define The Universe Model Class:
class LiquidValueUniverseSelectionModel(FundamentalUniverseSelectionModel):

    def __init__(self):
        super().__init__(True, None)
        self.lastMonth = -1

    # add an empty SelectCoarse() Method with its parameters 
    # to filter down by the dollar value of the stock or the volume of the stock
    def SelectCoarse(self, algorithm, coarse):
        # if it is not time to update the data - return the previous symbols
        # make sure this process takes place only once a month - since companys do not update fundamentals more
        # often and this is a computationa;y heavy task to bring all the fundamentals data
        # so - update self.lastMonth with current month to make sure we process this only once a month
        if self.lastMonth == algorithm.Time.month:
            return Universe.Unchanged
        self.lastMonth = algorithm.Time.month

        # Sort symbols by Dolar value, and if they have fundamental ded, in descending order:
        sortedByDollarVolume = sorted([x for x in coarse if x.HasFundamentalData],
        key=lambda x: x.DollarVolume, reverse=True)

        return [x.Symbol for x in sortedByDollarVolume[:100]]



    # add an empty SelectFine() Method with its parameters
    def SelectFine(self, algorithm, fine):
        # sort yields per share:
        sortedByYields = sorted(fine, key=lambda f: f.ValuationRatios.EarningYield, reverse = True)

        # take top 10 most profitable stocks, and buttom 10 least profitable stocks
        # save the variable to self.Universe
        self.universe = sortedByYields[:10] + sortedByYields[-10:]

        # return the symbols of these 20 tickers
        return [f.Symbol for f in self.universe]

# Define the LongShortAlphaModel Class:
class LongShortEYAlphaModel(AlphaModel):

    def __init__(self):
        self.lastMonth = -1

    def Update(self, algorithm, data):
        insights = []

        # create if else statement to emit signals once a month
        if self.lastMonth == algorithm.Time.month:
            return insights
        self.lastMonth = algorithm.Time.month




        # create for loop to emit insights with insight directions
        for security in algorithm.ActiveSecurities.Values:
            direction = 1 if security.Fundamentals.ValuationRatios.EarningYield > 0 else -1
            insights.append(Insight.Price(security.Symbol, timedelta(28), direction))



        # based in weather earnings yield is greater or less than zero once a month
        return insights
