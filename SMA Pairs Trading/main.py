# region imports
from AlgorithmImports import *
# endregion

class SMAPairsTrading(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2021, 1, 1)
        self.set_cash(100000)

        # 1 using the manual universe selection model add "PEP" and "KO" for pepsi and Coka Cola
        symbols = [Symbol.create("PEP", SecurityType.EQUITY, Market.USA),
                    Symbol.create("KO", SecurityType.EQUITY, Market.USA)]
        self.add_universe_selection(ManualUniverseSelectionModel(symbols))


        # 2 in the universe settings, set the resolution to one hour
        self.universe_settings.resolution = Resolution.HOUR
        self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW

        self.add_alpha(PairTradingAlphaModel())
        self.set_portfolio_construction(EqualWeightingPortfolioConstructionModel())
        self.set_execution(ImmediateExecutionModel())



class PairTradingAlphaModel(AlphaModel):

    def __init__(self):
        self.pair = []
        # create a 500 Hours Simple Moving Average Indicator monitoring the spread SMA
        self.spreadMean = SimpleMovingAverage(500)
        # create a 500 Hour STDdev Indicator monitoring the spread Std
        self.spreadStd = StandardDeviation(500)
        # set the period to be two hours:
        self.period = timedelta(hours=2)

        


        # Use OnEndOfDay() to log your positions at the close of each trading day
        def OnEndOfDay(self, Symbol):
            self.log("Taking a position of " + str(self.portofolio[Symbol].Quantity) + 
                                        " units of symbol " + str(Symbol))

    def Update(self, algorithm, data):
        # 3 set the price difference calculation to be self.SpreadExecutionModel
        spread = self.pair[1].Price - self.pair[0].Price
        # update the spread mean indicator
        self.spreadMean.Update(algorithm.Time, spread)

        # update the spreadStd indicator
        self.spreadStd.Update(algorithm.Time, spread)

        # save the upperthreshold amd the lower threshold
        upperthreshold = self.spreadMean.Current.Value + self.spreadStd.Current.Value
        lowerthreshold = self.spreadMean.Current.Value - self.spreadStd.Current.Value

        # Emit an Insight.Group() if the spread is greater then the upperthreshold
        if spread>upperthreshold:
            return Insight.Group(
                [
                    Insight.Price(self.pair[0].Symbol, self.period, InsightDirection.UP),
                    Insight.Price(self.pair[1].Symbol, self.period, InsightDirection.DOWN)
                ]
            ) 

        # Emit an Insight.Group() if the spread is smaller then the lowerthreshold
        if spread<lowerthreshold:
            return Insight.Group(
                [
                    Insight.Price(self.pair[0].Symbol, self.period, InsightDirection.DOWN),
                    Insight.Price(self.pair[1].Symbol, self.period, InsightDirection.UP)
                ]
            )

        # if the spread is in between - do not do anything
        return []

    def OnSecuritiesChanged(self, algorithm, changes):
        # 4 set self pair to the changes.AddedSecurities changes
        self.pair = [x for x in changes.AddedSecurities]

        # call for 500 hours of history data for each symbol in the pair and save the variable history
        history = algorithm.History([x.Symbol for x in self.pair], 500)

        # unstack it from the pandas dataframe to reduce it to the history close price:
        history = history.close.unstack(level=0)

        # iterate through the history tuple and updaten the mean and Std with the historical data
        for tuple in history.itertuples():
            self.spreadMean.Update(tuple[0], tuple[2] - tuple[1])
            self.spreadStd.Update(tuple[0], tuple[2] - tuple[1])
