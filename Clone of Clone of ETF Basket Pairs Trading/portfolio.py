#region imports
from AlgorithmImports import *
from Portfolio.EqualWeightingPortfolioConstructionModel import EqualWeightingPortfolioConstructionModel
from arch.unitroot.cointegration import engle_granger
from utils import reset_and_warm_up
#endregion

class CointegratedVectorPortfolioConstructionModel(EqualWeightingPortfolioConstructionModel):

    def __init__(self, algorithm, lookback = 252, resolution = Resolution.MINUTE, 
                 rebalance = Expiry.END_OF_WEEK) -> None:
        super().__init__(rebalance, PortfolioBias.LONG_SHORT)
        self.algorithm = algorithm
        self.lookback = lookback
        self.resolution = resolution

    def should_create_target_for_insight(self, insight: Insight) -> bool:
        # Ignore insights if the asset has open position in the same direction
        return self.should_create_new_target(insight.symbol, insight.direction)

    def determine_target_percent(self, active_insights: List[Insight]) -> Dict[Insight, float]:
        # If less than 2 active insights, no valid pair trading can be resulted
        if len(active_insights) < 2:
            self.live_log(self.algorithm, f'PortfolioContructionModel: Less then 2 insights. Create zero-quantity targets')
            return {insight: 0 for insight in active_insights}

        result = {}

        # Get log return for cointegrating vector regression
        logr = pd.DataFrame({symbol: self.returns(self.algorithm.securities[symbol]) 
            for symbol in self.algorithm.securities.keys() if symbol in [x.symbol for x in active_insights]})
        # fill nans with mean, if the whole column is nan, drop it
        logr = logr.fillna(logr.mean()).dropna(axis=1)
        # make sure we have at least 2 columns
        if logr.shape[1] < 2:
            self.live_log(self.algorithm, f'PortfolioContructionModel: Less then 2 insights. Create zero-quantity targets.')
            return {insight: 0 for insight in active_insights}
        # Obtain the cointegrating vector of all signaled assets for statistical arbitrage
        model = engle_granger(logr.iloc[:, 0], logr.iloc[:, 1:], trend='n', lags=0)
        
        # If result not significant, return
        if model.pvalue > 0.05:
            return {insight: 0 for insight in active_insights}
        
        # Normalization for budget constraint
        coint_vector = model.cointegrating_vector
        total_weight = sum(abs(coint_vector))

        for insight, weight in zip(active_insights, coint_vector):
            # we can assume any paired assets' 2 dimensions in coint_vector are in opposite sign
            result[insight] = abs(weight) / total_weight * insight.direction
            
        return result
        
    def on_securities_changed(self, algorithm, changes):
        self.live_log(algorithm, f'PortfolioContructionModel.on_securities_changed: Changes: {changes}')
        super().on_securities_changed(algorithm, changes)
        for added in changes.added_securities:
            self.init_security_data(algorithm, added)
        
        for removed in changes.removed_securities:
            self.dispose_security_data(algorithm, removed)

    def handle_corporate_actions(self, algorithm, slice):
        symbols = set(slice.dividends.keys())
        symbols.update(slice.splits.keys())

        for symbol in symbols:
            self.warm_up_indicator(algorithm.securities[symbol])

    def live_log(self, algorithm, message):
        if algorithm.live_mode:
            algorithm.log(message)

    def init_security_data(self, algorithm, security):
        # To store the historical daily log return
        security['window'] = RollingWindow[IndicatorDataPoint](self.lookback)

        # Use daily log return to predict cointegrating vector
        security['logr'] = LogReturn(1)
        security['logr'].updated += lambda _, updated: security['window'].add(IndicatorDataPoint(updated.end_time, updated.value))
        security['consolidator'] = TradeBarConsolidator(timedelta(1))

        # Subscribe the consolidator and indicator to data for automatic update
        algorithm.register_indicator(security.symbol, security['logr'], security['consolidator'])
        algorithm.subscription_manager.add_consolidator(security.symbol, security['consolidator'])

        self.warm_up_indicator(security)

    def warm_up_indicator(self, security):
        self.reset(security)
        security['consolidator'] = reset_and_warm_up(self.algorithm, security, self.resolution, self.lookback)

    def reset(self, security):
        security['logr'].reset()
        security['window'].reset()

    def dispose_security_data(self, algorithm, security):
        self.reset(security)
        algorithm.subscription_manager.remove_consolidator(security.symbol, security['consolidator'])

    def should_create_new_target(self, symbol, direction):
        quantity = self.algorithm.portfolio[symbol].quantity
        return quantity == 0 or direction != int(np.sign(quantity))

    def returns(self, security):
        return pd.Series(
            data = [x.value for x in security['window']],
            index = [x.end_time for x in security['window']])[::-1]
