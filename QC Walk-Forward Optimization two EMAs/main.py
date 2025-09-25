# region imports
from AlgorithmImports import *
import itertools
# endregion


"""
Walk-Forward Optimization (WFO) trading algorithm

The strategy uses two EMAs (Exponential Moving Averages) - a short-term and 
long-term - to generate buy/sell signals, while continuously optimizing the 
EMA periods through walk-forward optimization.

"""


class ParameterizedAlgorithm(QCAlgorithm):
    def initialize(self) -> None:
        self.set_start_date(2020, 1, 1)
        # not setting the end date means this runs until the current date
        self.set_cash(100000)
        # For warming up indicators.
        self.settings.automatic_indicator_warm_up = True
        # Set the warm-up period.
        self.set_warm_up(timedelta(45))

        # Add daily SPY Equity data
        self._security = self.add_equity("SPY", Resolution.DAILY)
        self._symbol = self._security.symbol

        # Initialize members for short and long EMA indicators.
        # short_ema = self.get_parameter("short_ema", None) #trying to make it a global parameter for tuning
        self._short_ema = None
        self._long_ema = None

        # Define an objective function to optimize the algorithm's overall performance.
        objective = self._cumulative_return

        # Schedule the WFO process to run at the start of each month at midnight.
        # To define the optimization schedule, pass self.date_rules and self.time_rules arguments to the train method.
        self.train(
            self.date_rules.week_end(self._symbol),
            self.time_rules.midnight,
            lambda: self._do_wfo(self._optimization_func, max, objective)
        )

        self._parameter_sets = self._generate_parameter_sets(
            {
                'short_ema': (5, 50, 5),  # min, max, step
                'long_ema': (55, 200, 5)
            }
        )


        # ADD GENERAL FUNDAMENTALS
        # Add FRED data
        self.add_data(Fred, "GDP", Resolution.DAILY)
        # Add Nasdaq Data Link dataset
        self.add_data(NasdaqDataLink, "DATASET/CODE", Resolution.DAILY)
        # Add FRED economic data
        self.add_data(Fred, "UNRATE", Resolution.DAILY)  # Unemployment rate



    
    # Define the trading logic.
    """
    Trading Logic (on_data)

        Buy Signal: When short EMA > long EMA and not already long → go 100% long
        Sell Signal: When short EMA < long EMA and not already short → reduce to 20% position
        Only executes after warm-up period
    
    """
    def on_data(self, data):
        if self.is_warming_up:
            return
        # getting the basic mix and ticker prices for our debug
        # this should be displayed in the logs tab
        for symbol in self.portfolio.keys():
            holding = self.portfolio[symbol]
            if holding.invested:
                self.debug("Ticker " + str(symbol) + "  Number of Shares  " + str(holding.quantity)+"  @Price " + str(holding.average_price))
    
        # Case 1: Short EMA is above long EMA --> buy all
        if (self._short_ema > self._long_ema and 
            not self._security.holdings.is_long):
            self.set_holdings(self._symbol, 1)
        # Case 2: Short EMA is below long EMA --> sell some
        elif (self._short_ema < self._long_ema and 
                not self._security.holdings.is_short):
            self.set_holdings(self._symbol, 1)

        
        # Plot the moving averages over the current price so that we can trace the decision making
        for symbol in self.portfolio.keys():
            holding = self.portfolio[symbol]
            self.plot("EMAs and Price", "EMA_short", self._short_ema.current.value)
            self.plot("EMAs and Price", "EMA_long", self._long_ema.current.value)
            self.plot("EMAs and Price", f'Ticker {holding.symbol}',self._security.price )

        # adding fundamentals:
        if data.contains_key("GDP"):
            gdp_value = data["GDP"].value
            self.plot("Economic Indicators", "GDP (Billions $)", data["GDP"].value)

        # Access FRED data
        if "UNRATE" in data:
            unemployment_rate = data["UNRATE"].value
            self.plot("Unemployment Chart", "Unemployment_Rate_USA", unemployment_rate)



    # Define a method to adjust the algorithm's behavior based on the new optimal parameters.
    def _update_algorithm_logic(self, optimal_parameters):
        # Remove the old indicators.
        """
        Algorithm Update (_update_algorithm_logic)

            Removes old EMA indicators
            Creates new EMAs with the optimized periods
        """
        if self._short_ema:
            self.deregister_indicator(self._short_ema)
        if self._long_ema:
            self.deregister_indicator(self._long_ema)
        # Create the new indicators.
        self._short_ema = self.ema(
            self._symbol, optimal_parameters['short_ema'], Resolution.DAILY
        )
        self._long_ema = self.ema(
            self._symbol, optimal_parameters['long_ema'], Resolution.DAILY
        )


    # Evaluate parameter sets with the objective function.
    def _optimization_func(self, data, parameter_set, objective):
        """
        Optimization Function
            This is where each parameter set gets evaluated:

            Calculates EMAs for the given periods on historical data
            Generates exposure signals: +1 when short EMA > long EMA, -1 when opposite
            Calculates strategy returns by multiplying exposure signals by next-day asset returns
            The shift(1) means positions are taken the day after the signal
            Returns the cumulative return for this parameter set
        """
        p1 = parameter_set['short_ema']
        p2 = parameter_set['long_ema']
        short_ema = data['close'].ewm(p1, min_periods=p1).mean()
        long_ema = data['close'].ewm(p2, min_periods=p2).mean()
        exposure = (short_ema - long_ema).dropna().apply(np.sign)\
            .replace(0, pd.NA).ffill().shift(1)
        # ^ shift(1) because we enter the position on the next day.
        asset_daily_returns = data['open'].pct_change().shift(-1) 
        # ^ shift(-1) because we want each entry to be the return from 
        # the current day to the next day.
        strategy_daily_returns = (exposure * asset_daily_returns).dropna()
        return objective(strategy_daily_returns)


    def _do_wfo(self, optimization_func, min_max, objective):
        # Get the historical data you need to calculate the scores.
        """
        Walk-Forward Optimization (_do_wfo)

            Runs monthly, using last 180 days of data
            Tests all parameter combinations using the optimization function
            Finds the parameter set with the maximum cumulative return
            Updates the algorithm to use these optimal parameters
        
        """
        prices = self.history(
            self._symbol, timedelta(122), Resolution.DAILY
        ).loc[self._symbol]

        # Calculate the score of each parameter set.
        scores = [
            optimization_func(prices, parameter_set, objective)
            for parameter_set in self._parameter_sets
        ]
        
        # Find the parameter set that minimizes/maximizes the objective function.
        optimal_parameters = self._parameter_sets[scores.index(min_max(scores))]

        # Adjust the algorithm's logic.
        self._update_algorithm_logic(optimal_parameters)
        

    def _generate_parameter_sets(self, search_space):
        """
        Parameter Generation (_generate_parameter_sets)

            Creates all possible combinations of EMA periods within the defined ranges
            Example: short EMA from 5-50 (step 5), long EMA from 55-200 (step 5)
            Results in hundreds of parameter combinations to test
        """
        # Create ranges for each parameter.
        ranges = {
            parameter_name: np.arange(min_, max_ + step_size, step_size) 
            for parameter_name, (min_, max_, step_size) in search_space.items()
        }
        
        # Calculate the cartesian product and create a list of dictionaries for
        # the parameter sets.
        return [
            dict(zip(ranges.keys(), combination)) 
            for combination in list(itertools.product(*ranges.values()))
        ]

    # Define an objective function to optimize the algorithm's overall performance.
    def _cumulative_return(self, daily_returns):
        # Handle empty input gracefully
        if daily_returns is None or len(daily_returns) == 0:
            return 0.0

        return (daily_returns + 1).cumprod()[-1] - 1

        """
        Method Purpose:
            The _cumulative_return method takes a series of daily returns and computes the total
             return over the entire period.
        
        
        Step-by-step calculation:

            daily_returns + 1 - Converts each daily return from decimal form to a growth factor

            For example: if daily return is 0.02 (2%), this becomes 1.02
            If daily return is -0.01 (-1%), this becomes 0.99


            .cumprod() - Calculates the cumulative product of all these growth factors

            This multiplies each day's growth factor by all previous days
            Essentially compounds the returns day by day


            [-1] - Takes the final value from the cumulative product series

            This gives you the total growth factor over the entire period


            - 1 - Converts back from growth factor to return percentage

            If final growth factor is 1.25, subtracting 1 gives 0.25 (25% total return)



        Example:
            If you have daily returns of [0.01, 0.02, -0.005] (1%, 2%, -0.5%):

            Growth factors: [1.01, 1.02, 0.995]
            Cumulative product: [1.01, 1.0302, 1.024949]
            Final cumulative return: 1.024949 - 1 = 0.024949 (about 2.49% total return)

        This is the standard way to calculate compound returns in quantitative finance, properly 
        accounting for the compounding effect of daily gains and losses.



        """
