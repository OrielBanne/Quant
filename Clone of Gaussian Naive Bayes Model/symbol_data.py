from AlgorithmImports import *

class SymbolData:
    """
    This class stores data unique to each security in the universe.
    """

    def __init__(self, security, algorithm, num_days_per_sample=4, num_samples=100):
        """
        Input:
         - security
            Security object for the security
         - algorithm
            The algorithm instance running the backtest
         - num_days_per_sample
            The number of open-close intraday returns for each sample
         - num_samples
            The number of samples to train the model
        """
        self.exchange = security.exchange
        self.hours = self.exchange.hours
        self.symbol = security.symbol
        self.algorithm = algorithm
        self.num_days_per_sample = num_days_per_sample
        self.num_samples = num_samples 
        self.holding_period = 30 # calendar days
        self.model = None
        
        self.set_up_consolidator()
        self.warm_up()
    
    def set_up_consolidator(self):
        self.consolidator = TradeBarConsolidator(timedelta(1))
        self.consolidator.data_consolidated += self.consolidation_handler
        self.algorithm.subscription_manager.add_consolidator(self.symbol, self.consolidator)

    def warm_up(self):
        self.roc_window = np.array([])
        self.previous_opens = pd.Series()
        self.labels_by_day = pd.Series()
        self.features_by_day = pd.DataFrame({f'{self.symbol.id}_(t-{i})' : [] for i in range(1, self.num_days_per_sample + 1)})
        
        lookback = self.num_days_per_sample + self.num_samples + self.holding_period + 1  
        history = self.algorithm.history(self.symbol, int(lookback), Resolution.DAILY, data_normalization_mode=DataNormalizationMode.SCALED_RAW)
        if history.empty or 'close' not in history:
            self.algorithm.log(f"Not enough history for {self.symbol} yet")    
            return
        
        history = history.loc[self.symbol]
        history['open_close_return'] = (history.close - history.open) / history.open
        
        start = history.shift(-1).open
        end = history.shift(-22).open   ### Trading days instead of calendar days
        history['future_return'] = (end - start) / start
        
        for day, row in history.iterrows():
            self.previous_opens[day] = row.open
            
            # Update features
            if not self.update_features(day, row.open_close_return):
                continue

            # Update labels
            if not pd.isnull(row.future_return):
                row = pd.Series([np.sign(row.future_return)], index=[day])
                self.labels_by_day = pd.concat([self.labels_by_day, row])[-self.num_samples:]
        self.previous_opens = self.previous_opens[-self.holding_period:]
    
    def consolidation_handler(self, sender, consolidated):
        """
        Updates the rolling lookback of training data.
        
        Inputs
         - sender
            Function calling the consolidator
         - consolidated
            Tradebar representing the latest completed trading day
        """
        time = consolidated.end_time
        if time in self.features_by_day.index:
            return
        
        _open = consolidated.open
        close = consolidated.close
        
        # Update features
        open_close_return = (close - _open) / _open
        if not self.update_features(time, open_close_return):
            return
        
        # Update labels
        open_days = self.previous_opens[self.previous_opens.index <= time - timedelta(self.holding_period)]
        if len(open_days) == 0:
            return 
        open_day = open_days.index[-1]
        previous_open = self.previous_opens[open_day]
        open_open_return = (_open - previous_open) / previous_open
        self.labels_by_day[open_day] = np.sign(open_open_return)
        self.labels_by_day = self.labels_by_day[-self.num_samples:]
            
        self.previous_opens.loc[time] = _open
        self.previous_opens = self.previous_opens[-self.holding_period:]

    def update_features(self, day, open_close_return):
        """
        Updates the training data features.
        
        Inputs
         - day
            Timestamp of when we're aware of the open_close_return
         - open_close_return
            Open to close intraday return
            
        Returns T/F, showing if the features are in place to start updating the training labels.
        """
        self.roc_window = np.append(open_close_return, self.roc_window)[:self.num_days_per_sample]
        
        if len(self.roc_window) < self.num_days_per_sample: 
            return False
            
        self.features_by_day.loc[day] = self.roc_window
        self.features_by_day = self.features_by_day[-(self.num_samples+self.holding_period+2):]
        return True


    def reset(self):
        self.algorithm.subscription_manager.remove_consolidator(self.symbol, self.consolidator)
        self.set_up_consolidator()
        self.warm_up()

    def dispose(self):
        """
        Removes the consolidator subscription.
        """
        self.algorithm.subscription_manager.remove_consolidator(self.symbol, self.consolidator)
        
    
    @property
    def is_ready(self):
        return self.features_by_day.shape[0] == self.num_samples + self.holding_period + 2
