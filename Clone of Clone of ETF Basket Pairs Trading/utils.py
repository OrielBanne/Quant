#region imports
from AlgorithmImports import *
#endregion

def reset_and_warm_up(algorithm, security, resolution, lookback = None):
    indicator = security['logr']
    consolidator = security['consolidator']

    if not lookback:
        lookback = indicator.warm_up_period

    # historical request to update the consolidator that will warm up the indicator
    history = algorithm.history[consolidator.input_type](security.symbol, lookback, resolution,
        data_normalization_mode = DataNormalizationMode.SCALED_RAW)

    indicator.reset()
    
    # Replace the consolidator, since we cannot reset it
    # Not ideal since we don't the consolidator type and period
    algorithm.subscription_manager.remove_consolidator(security.symbol, consolidator)
    consolidator = TradeBarConsolidator(timedelta(1))
    algorithm.register_indicator(security.symbol, indicator, consolidator)
    
    for bar in list(history)[:-1]:
        consolidator.update(bar)

    return consolidator

'''
# In main.py, OnData and call HandleCorporateActions for framework models (if necessary)
    def on_data(self, slice):
        if slice.splits or slice.dividends:
            self.alpha.handle_corporate_actions(self, slice)
            self.pcm.handle_corporate_actions(self, slice)
            self.risk.handle_corporate_actions(self, slice)
            self.execution.handle_corporate_actions(self, slice)

# In the framework models, add
from utils import ResetAndWarmUp

and implement HandleCorporateActions. E.g.:
    def handle_corporate_actions(self, algorithm, slice):
        for security.symbol, data in self.security.symbol_data.items():
            if slice.splits.contains_key(security.symbol) or slice.dividends.contains_key(security.symbol):
                data.warm_up_indicator()

where WarmUpIndicator will call ResetAndWarmUp for each indicator/consolidator pair
'''
