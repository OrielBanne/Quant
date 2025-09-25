#region imports
from AlgorithmImports import *

import numpy as np
#endregion


class BetaAlgorithm(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2016, 1, 1)   # Set Start Date
        self.set_end_date(2024, 4, 1)     # Set End Date
        self.set_cash(10000)             # Set Strategy Cash
        self.set_security_initializer(
            BrokerageModelSecurityInitializer(self.brokerage_model, FuncSecuritySeeder(self.get_last_known_prices))
        )
        
        # Dow 30 companies. 
        self._symbols = [self.add_equity(ticker).symbol
            for ticker in ['AAPL', 'AXP', 'BA', 'CAT', 'CSCO', 'CVX', 'DD',
                           'DIS', 'GE', 'GS', 'HD', 'IBM', 'INTC', 'JPM',
                           'KO', 'MCD', 'MMM', 'MRK', 'MSFT', 'NKE', 'PFE',
                           'PG', 'TRV', 'UNH', 'UTX', 'V', 'VZ', 'WMT', 'XOM'] ]  

        # Benchmark
        self._benchmark = Symbol.create('SPY', SecurityType.EQUITY, Market.USA)

        # Set number days to trace back
        self._lookback = 21

        # Schedule Event: trigger the event at the begining of each month.
        self.schedule.on(self.date_rules.month_start(self._symbols[0]),
                         self.time_rules.after_market_open(self._symbols[0]),
                         self._rebalance)

    def _rebalance(self):

        # Fetch the historical data to perform the linear regression
        history = self.history(
            self._symbols + [self._benchmark], 
            self._lookback,
            Resolution.DAILY).close.unstack(level=0)
            
        symbols = self._select_symbols(history)

        # Liquidate positions that are not held by selected symbols
        for symbol, holdings in self.portfolio.items():
            if symbol not in symbols and holdings.invested:
                self.liquidate(symbol)

        # Invest 100% in the selected symbols
        for symbol in symbols:
            self.set_holdings(symbol, 0.5)

    def _select_symbols(self, history):
        alphas = dict()

        # Get the benchmark returns
        benchmark = history[self._benchmark].pct_change().dropna()

        # Conducts linear regression for each symbol and save the intercept/alpha
        for symbol in self._symbols:
            
            # Get the security returns
            returns = history[symbol].pct_change().dropna()
            bla = np.vstack([benchmark, np.ones(len(returns))]).T

            # Simple linear regression function in Numpy
            result = np.linalg.lstsq(bla , returns)
            alphas[symbol] = result[0][1]

        # Select symbols with the highest intercept/alpha to the benchmark
        selected = sorted(alphas.items(), key=lambda x: x[1], reverse=True)[:2]
        return [x[0] for x in selected]
