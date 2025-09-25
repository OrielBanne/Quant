# region imports
from AlgorithmImports import *
# endregion
from AlphaModel import *



"""
total performance statistics : 
_________________________________________________________________________________
| Statistic Key                 | Description                                   |
| ----------------------------- | --------------------------------------------- |
| `Total Trades`                | Number of executed trades                     |
| `Average Win`                 | Average % return of winning trades            |
| `Average Loss`                | Average % return of losing trades             |
| `Compounding Annual Return`   | CAGR over the backtest period                 |
| `Drawdown`                    | Maximum drawdown                              |
| `Expectancy`                  | Win/Loss expectancy                           |
| `Net Profit`                  | Total profit in %                             |
| `Sharpe Ratio`                | Risk-adjusted return                          |
| `Probabilistic Sharpe Ratio`  | Likelihood Sharpe is above a benchmark        |
| `Loss Rate`                   | % of trades that were losses                  |
| `Win Rate`                    | % of trades that were wins                    |
| `Alpha`                       | Excess return vs benchmark                    |
| `Beta`                        | Portfolio volatility vs benchmark             |
| `Annual Standard Deviation`   | Annualized volatility                         |
| `Annual Variance`             | Annualized variance                           |
| `Information Ratio`           | Excess return per unit of tracking error      |
| `Tracking Error`              | Volatility of excess return vs benchmark      |
| `Treynor Ratio`               | Return per unit of systematic risk            |
| `Total Fees`                  | Total fees paid in USD                        |
| `Estimated Strategy Capacity` | Rough estimate of max capital before slippage |
| `Lowest Capacity Asset`       | Asset that limits capacity                    |
| `Portfolio Turnover`          | Total trading as % of portfolio               |
---------------------------------------------------------------------------------
"""


class VerticalTachyonRegulators(QCAlgorithm):
    _statistics = ["Time,Sharpe,Beta,95VaR, Alpha"]

    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2025, 1, 1)
        self.SetCash(100000)

        # Universe selection
        self.month = 0
        self.num_coarse = 500

        self.UniverseSettings.Resolution = Resolution.DAILY
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)
        
        # Alpha Model
        self.AddAlpha(FundamentalFactorAlphaModel())

        # Portfolio construction model
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel(self.IsRebalanceDue))
        
        # Risk model
        self.SetRiskManagement(MaximumDrawdownPercentPerSecurity(0.02))

        # Execution model
        self.SetExecution(ImmediateExecutionModel())

        # warmup:
        self.SetWarmUp(timedelta(days=60))

    # Share the same rebalance function for Universe and PCM for clarity
    def IsRebalanceDue(self, time):
        # Rebalance on the first day of the Quarter
        if time.month == self.month or time.month not in [1, 4, 7, 10]:
            return None
            
        self.month = time.month
        return time

    def CoarseSelectionFunction(self, coarse):
        # If not time to rebalance, keep the same universe
        if not self.IsRebalanceDue(self.Time): 
            return Universe.Unchanged

        # Select only those with fundamental data and a sufficiently large price
        # Sort by top dollar volume: most liquid to least liquid
        selected = sorted([x for x in coarse if x.HasFundamentalData and x.Price > 5],
                            key = lambda x: x.DollarVolume, reverse=True)

        return [x.Symbol for x in selected[:self.num_coarse]]


    def FineSelectionFunction(self, fine):
        # Filter the fine data for equities that IPO'd more than 5 years ago in selected sectors
        
        sectors = [
            MorningstarSectorCode.FinancialServices,
            MorningstarSectorCode.RealEstate,
            MorningstarSectorCode.Healthcare,
            MorningstarSectorCode.Utilities,
            MorningstarSectorCode.Technology]
        
        filtered_fine = [x.Symbol for x in fine if x.SecurityReference.IPODate + timedelta(365*5) < self.Time
                                    and x.AssetClassification.MorningstarSectorCode in sectors
                                    and x.OperationRatios.ROE.Value > 0
                                    and x.OperationRatios.NetMargin.Value > 0
                                    and x.ValuationRatios.PERatio > 0]
                
        return filtered_fine



    def on_end_of_day(self, symbol: Symbol) -> None:
        # Obtain the algorithm statistics interested.
        sharpe = self.statistics.total_performance.portfolio_statistics.sharpe_ratio
        b = self.statistics.total_performance.portfolio_statistics.beta
        var = self.statistics.total_performance.portfolio_statistics.value_at_risk_95
        alpha = self.statistics.total_performance.portfolio_statistics.alpha

        # Plot the statistics.
        self.plot("Statistics", "Sharpe", sharpe)
        self.plot("Statistics", "Beta", b)
        self.plot("Statistics", "Value-at-Risk", var)
        self.plot("Statistics", "Alpha", alpha)

        # Write to save the statistics.
        self._statistics.append(f'{self.time.strftime("%Y%m%d")},{sharpe},{b},{var},{alpha}')

    def on_end_of_algorithm(self) -> None:
        # Save the logged statistics for later access in the object store.
        self.object_store.save(f'{self.project_id}/algorithm-statistics', '\n'.join(self._statistics))
