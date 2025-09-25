from AlgorithmImports import *

class RisingSectorFundamentalUniverse(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 8, 1)
        self.set_cash(100000)
        
        # Set SPY as benchmark (built into QuantConnect)
        self.set_benchmark("SPY")
        
        # We need a benchmark to compare against
        self.spy = self.add_equity("SPY", Resolution.DAILY).Symbol
        
        self.lookback_days = 60
        self.num_stocks = 10
        self.num_sectors = 3
        self.sector_returns = {}
        
        # CORRECTED: Updated sector ETF mapping with proper GICS names
        self.sector_etf_map = {
            "Information Technology": self.add_equity("XLK", Resolution.DAILY).Symbol,
            "Communication Services": self.add_equity("XLC", Resolution.DAILY).Symbol,
            "Consumer Discretionary": self.add_equity("XLY", Resolution.DAILY).Symbol,
            "Financials": self.add_equity("XLF", Resolution.DAILY).Symbol,
            "Health Care": self.add_equity("XLV", Resolution.DAILY).Symbol,
            "Industrials": self.add_equity("XLI", Resolution.DAILY).Symbol,
            "Consumer Staples": self.add_equity("XLP", Resolution.DAILY).Symbol,
            "Energy": self.add_equity("XLE", Resolution.DAILY).Symbol,
            "Materials": self.add_equity("XLB", Resolution.DAILY).Symbol,
            "Real Estate": self.add_equity("XLRE", Resolution.DAILY).Symbol,
            "Utilities": self.add_equity("XLU", Resolution.DAILY).Symbol
        }

        # RESTORED: Your original sector stocks dictionary with corrected GICS names
        self.sector_stocks_map = {
            "Information Technology": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "AMD", "INTC"],
            "Communication Services": ["GOOG", "GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR"],
            "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
            "Financials": ["BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "AXP"],
            "Health Care": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "PFE", "TMO", "ABT", "DHR", "BMY"],
            "Industrials": ["CAT", "GE", "HON", "UPS", "FDX", "MMM", "RTX", "LMT", "DE", "BA"],
            "Consumer Staples": ["WMT", "PG", "COST", "KO", "PEP", "CL", "KMB", "GIS", "K", "CPB"],
            "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "PXD", "KMI", "WMB", "MPC", "VLO"],
            "Materials": ["LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF"],
            "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR", "MAA", "SPG"],
            "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "WEC"]
        }

        # Schedule the universe selection and sector return calculation
        self.schedule.on(self.date_rules.every_day(), self.time_rules.after_market_open(self.spy, 30), self.UpdateUniverse)
        
        # ENHANCED: More frequent stop loss checks for drawdown protection
        self.schedule.on(self.date_rules.every_day(), self.time_rules.every(timedelta(minutes=30)), self.check_stop_losses)
        
        # ENHANCED: Portfolio-level stop loss check
        self.schedule.on(self.date_rules.every_day(), self.time_rules.every(timedelta(hours=1)), self.check_portfolio_stop_loss)
        
        # We'll use a single variable to store the universe of symbols.
        self.universe_symbols = []
        
        # Store the selected sectors for use in universe selection
        self.selected_sectors = []
        
        # Add universe selection with proper coarse and fine filters
        self.add_universe(self.coarse_selection_function, self.fine_selection_function)
        
        # Add rebalancing controls
        self.last_rebalance = datetime.min
        self.rebalance_frequency = 30  # Rebalance every 30 days, not daily
        
        # ENHANCED: Tighter stop loss controls for drawdown protection
        self.stop_loss_percentage = 0.02  # 2% stop loss (tighter)
        self.trailing_stop_percentage = 0.03  # 3% trailing stop (tighter)
        self.portfolio_stop_loss = 0.06  # 15% portfolio-level stop loss
        self.highest_prices = {}  # Track highest prices for trailing stops
        self.highest_portfolio_value = 0  # Track highest portfolio value
        
        # ENHANCED: Position sizing for risk control
        self.max_position_size = 0.15  # Maximum 15% per position
        
        # NEW: Stop loss rebalancing controls
        self.stop_loss_triggered = False
        self.need_rebalance_after_stop_loss = False
        self.blacklisted_stocks = set()  # Stocks that hit stop loss recently
        self.blacklist_duration = 7  # Days to blacklist a stock after stop loss
        self.stock_blacklist_dates = {}  # Track when stocks were blacklisted
        
        # Warmup period to ensure we have enough data
        self.warmup_period = 50  # days of warmup
        self.is_warmed_up = False
        self.start_time = self.time  # Track when algorithm started
        
        # ENHANCED: Emergency liquidation flag
        self.emergency_liquidation = False
        
        # Warm up with historical data
        self.warm_up_historical_data()

    def warm_up_historical_data(self):
        """Warm up with historical data for sector ETFs"""
        try:
            etf_symbols = list(self.sector_etf_map.values())
            
            # Get historical data for sector ETFs
            history = self.history(etf_symbols, self.warmup_period, Resolution.DAILY)
            
            if history is not None and not history.empty:
                self.log(f"Warmed up with {len(history)} historical data points")
                
                # Calculate initial sector returns
                temp_sector_returns = {}
                for symbol, df in history.groupby(level=0):
                    if len(df) >= 2:
                        start_price = df.iloc[0]['close']
                        end_price = df.iloc[-1]['close']
                        
                        if start_price > 0:
                            ret = (end_price / start_price) - 1
                            sector_code = next((k for k, v in self.sector_etf_map.items() if v == symbol), None)
                            if sector_code:
                                temp_sector_returns[sector_code] = ret
                
                self.sector_returns = temp_sector_returns
                self.log(f"Initial sector returns calculated: {self.sector_returns}")
            else:
                self.log("Warning: Could not get historical data for warmup")
                
        except Exception as e:
            self.log(f"Error during warmup: {str(e)}")

    def OnData(self, data):
        # ENHANCED: Immediate stop loss check on every data update
        self.immediate_stop_loss_check(data)
        
        # NEW: Handle rebalancing after stop loss
        if self.need_rebalance_after_stop_loss:
            self.rebalance_after_stop_loss(data)
            return
        
        # Check if we're still in warmup period
        if not self.is_warmed_up:
            if self.time < self.start_time + timedelta(days=self.warmup_period):
                return
            else:
                self.is_warmed_up = True
                self.log(f"Warmup period completed at {self.time}")
                # Initialize highest portfolio value
                self.highest_portfolio_value = self.portfolio.total_portfolio_value
        
        # ENHANCED: Skip trading if in emergency liquidation mode
        if self.emergency_liquidation:
            return
        
        # Check if we should rebalance (every 30 days, not daily)
        if (self.time - self.last_rebalance).days < self.rebalance_frequency:
            return
            
        # If no universe symbols, liquidate all positions
        if not self.universe_symbols:
            if self.portfolio.invested:
                self.log("No universe symbols available - liquidating all positions")
                self.liquidate()
            return
            
        # Check if we have enough cash
        if self.portfolio.cash <= 1000:  # Minimum cash threshold
            self.log(f"Low cash warning: ${self.portfolio.cash:.2f}")
            return
            
        # ENHANCED: Risk-adjusted position sizing
        weight = min(1.0 / len(self.universe_symbols), self.max_position_size) if self.universe_symbols else 0
        
        # Only rebalance if we have valid data for all symbols
        valid_symbols = []
        for symbol in self.universe_symbols:
            if self.securities.contains_key(symbol) and data.contains_key(symbol):
                valid_symbols.append(symbol)
        
        if len(valid_symbols) != len(self.universe_symbols):
            self.log(f"Warning: Only {len(valid_symbols)}/{len(self.universe_symbols)} symbols have valid data")
            
        # If no valid symbols, liquidate
        if not valid_symbols:
            if self.portfolio.invested:
                self.log("No valid symbols - liquidating all positions")
                self.liquidate()
            return
            
        # RESTORED: Your original trading logic - rebalance valid symbols
        for symbol in valid_symbols:
            self.set_holdings(symbol, weight)
            
        self.last_rebalance = self.time
        self.log(f"Rebalanced portfolio with {len(valid_symbols)} symbols at {self.time}")
        
        # Update highest portfolio value
        if self.portfolio.total_portfolio_value > self.highest_portfolio_value:
            self.highest_portfolio_value = self.portfolio.total_portfolio_value

    # NEW: Rebalance immediately after stop loss
    def rebalance_after_stop_loss(self, data):
        """Immediately rebalance portfolio after stop loss execution"""
        self.log("=== REBALANCING AFTER STOP LOSS ===")
        
        # Clean up blacklist (remove old entries)
        self.clean_blacklist()
        
        # Get fresh stock selection excluding blacklisted stocks
        new_universe = self.select_replacement_stocks()
        
        if not new_universe:
            self.log("No replacement stocks available - staying in cash")
            self.need_rebalance_after_stop_loss = False
            return
        
        # Calculate equal weight for remaining cash
        available_cash = self.portfolio.cash
        total_portfolio_value = self.portfolio.total_portfolio_value
        
        # Only invest available cash, don't disturb existing positions
        if available_cash > 1000:  # Minimum threshold
            weight_per_stock = min(available_cash / total_portfolio_value / len(new_universe), self.max_position_size)
            
            self.log(f"Investing available cash (${available_cash:.2f}) in {len(new_universe)} replacement stocks")
            
            for symbol in new_universe:
                if data.contains_key(symbol) and self.securities.contains_key(symbol):
                    current_weight = self.portfolio[symbol].holdings_value / total_portfolio_value
                    target_weight = current_weight + weight_per_stock
                    
                    # Don't exceed max position size
                    target_weight = min(target_weight, self.max_position_size)
                    
                    self.set_holdings(symbol, target_weight)
                    self.log(f"Added/increased position in {symbol}: {target_weight:.2%}")
        
        # Reset flags
        self.need_rebalance_after_stop_loss = False
        self.stop_loss_triggered = False
        self.last_rebalance = self.time
        
        self.log("=== STOP LOSS REBALANCING COMPLETE ===")

    # NEW: Select replacement stocks after stop loss
    def select_replacement_stocks(self):
        """Select new stocks to replace those that hit stop loss"""
        if not self.selected_sectors:
            return []
        
        # Get all available stocks from selected sectors
        available_stocks = []
        for sector in self.selected_sectors:
            if sector in self.sector_stocks_map:
                sector_stocks = self.sector_stocks_map[sector]
                for stock in sector_stocks:
                    # Skip blacklisted stocks
                    if stock not in self.blacklisted_stocks:
                        available_stocks.append(stock)
        
        # Remove stocks we already own
        current_holdings = [str(symbol).split()[0] for symbol in self.portfolio.keys() if self.portfolio[symbol].invested]
        available_stocks = [stock for stock in available_stocks if stock not in current_holdings]
        
        if not available_stocks:
            self.log("No available replacement stocks found")
            return []
        
        # Select up to 3 replacement stocks (or fewer if not enough available)
        num_replacements = min(3, len(available_stocks))
        replacement_stocks = available_stocks[:num_replacements]
        
        # Convert to symbols
        replacement_symbols = []
        for stock_ticker in replacement_stocks:
            try:
                symbol = Symbol.create(stock_ticker, SecurityType.EQUITY, Market.USA)
                replacement_symbols.append(symbol)
            except:
                self.log(f"Could not create symbol for replacement stock {stock_ticker}")
                continue
        
        self.log(f"Selected {len(replacement_symbols)} replacement stocks: {[str(s) for s in replacement_symbols]}")
        return replacement_symbols

    # NEW: Clean up blacklist
    def clean_blacklist(self):
        """Remove stocks from blacklist after specified duration"""
        current_time = self.time
        stocks_to_remove = []
        
        for stock, blacklist_date in self.stock_blacklist_dates.items():
            if (current_time - blacklist_date).days >= self.blacklist_duration:
                stocks_to_remove.append(stock)
        
        for stock in stocks_to_remove:
            self.blacklisted_stocks.discard(stock)
            del self.stock_blacklist_dates[stock]
            self.log(f"Removed {stock} from blacklist after {self.blacklist_duration} days")

    # ENHANCED: Immediate stop loss check with rebalancing trigger
    def immediate_stop_loss_check(self, data):
        """Check stop losses immediately on every data update"""
        if not self.is_warmed_up or self.emergency_liquidation:
            return
            
        stop_loss_executed = False
        
        for symbol in list(self.portfolio.keys()):
            if not self.portfolio[symbol].invested or symbol == self.spy:
                continue
                
            if not data.contains_key(symbol):
                continue
                
            bar = data[symbol]
            if bar is None:
                continue
            current_price = bar.close
                
            position = self.portfolio[symbol]
            
            # Initialize highest price tracking
            if symbol not in self.highest_prices:
                self.highest_prices[symbol] = current_price
                
            # Update highest price for trailing stop
            if current_price > self.highest_prices[symbol]:
                self.highest_prices[symbol] = current_price
                
            # Calculate stop loss price
            entry_price = position.average_price
            highest_price = self.highest_prices[symbol]
            
            # Use trailing stop if price has moved up significantly (2% buffer)
            if highest_price > entry_price * 1.02:
                stop_price = highest_price * (1 - self.trailing_stop_percentage)
            else:
                stop_price = entry_price * (1 - self.stop_loss_percentage)
            
            # ENHANCED: Immediate execution if stop loss triggered
            if current_price <= stop_price:
                self.log(f"IMMEDIATE STOP LOSS: {symbol} at ${current_price:.2f} (stop: ${stop_price:.2f})")
                
                # Add to blacklist
                stock_ticker = str(symbol).split()[0]
                self.blacklisted_stocks.add(stock_ticker)
                self.stock_blacklist_dates[stock_ticker] = self.time
                self.log(f"Added {stock_ticker} to blacklist for {self.blacklist_duration} days")
                
                # Liquidate position
                self.liquidate(symbol)
                
                # Clean up tracking
                if symbol in self.highest_prices:
                    del self.highest_prices[symbol]
                
                # Flag for rebalancing
                stop_loss_executed = True
        
        # NEW: Trigger rebalancing if any stop loss was executed
        if stop_loss_executed:
            self.stop_loss_triggered = True
            self.need_rebalance_after_stop_loss = True
            self.log("Stop loss executed - will rebalance with new stocks")

    # ENHANCED: Portfolio-level stop loss protection
    def check_portfolio_stop_loss(self):
        """Check portfolio-level stop loss to prevent large drawdowns"""
        if not self.is_warmed_up or self.emergency_liquidation:
            return
            
        current_value = self.portfolio.total_portfolio_value
        
        # Update highest portfolio value
        if current_value > self.highest_portfolio_value:
            self.highest_portfolio_value = current_value
            
        # Calculate portfolio drawdown
        if self.highest_portfolio_value > 0:
            drawdown = (self.highest_portfolio_value - current_value) / self.highest_portfolio_value
            
            # Log current drawdown
            self.log(f"Portfolio drawdown: {drawdown:.2%} (Current: ${current_value:.2f}, Peak: ${self.highest_portfolio_value:.2f})")
            
            # ENHANCED: Emergency liquidation if portfolio stop loss hit
            if drawdown >= self.portfolio_stop_loss:
                self.log(f"PORTFOLIO STOP LOSS TRIGGERED! Drawdown: {drawdown:.2%} >= {self.portfolio_stop_loss:.2%}")
                self.log("EMERGENCY LIQUIDATION - Selling all positions")
                
                # Liquidate everything except SPY
                for symbol in list(self.portfolio.keys()):
                    if self.portfolio[symbol].invested and symbol != self.spy:
                        self.liquidate(symbol)
                        self.log(f"Emergency liquidated: {symbol}")
                
                # Set emergency flag to prevent new trades
                self.emergency_liquidation = True
                
                # Clear tracking
                self.highest_prices.clear()
                self.blacklisted_stocks.clear()
                self.stock_blacklist_dates.clear()

    def check_stop_losses(self):
        """Scheduled method to check stop losses every 30 minutes"""
        if not self.is_warmed_up or self.emergency_liquidation:
            return
            
        if not self.portfolio.invested:
            return
            
        stop_loss_executed = False
        
        # Check stop losses for each invested position
        for symbol in list(self.portfolio.keys()):
            if not self.portfolio[symbol].invested or symbol == self.spy:
                continue
                
            try:
                current_price = self.securities[symbol].price
                if current_price <= 0:
                    continue
                    
                position = self.portfolio[symbol]
                
                # Initialize highest price tracking
                if symbol not in self.highest_prices:
                    self.highest_prices[symbol] = current_price
                    
                # Update highest price for trailing stop
                if current_price > self.highest_prices[symbol]:
                    self.highest_prices[symbol] = current_price
                    
                # Calculate stop loss price
                entry_price = position.average_price
                highest_price = self.highest_prices[symbol]
                
                # Use trailing stop if price has moved up significantly
                if highest_price > entry_price * 1.02:  # 2% buffer
                    stop_price = highest_price * (1 - self.trailing_stop_percentage)
                else:
                    stop_price = entry_price * (1 - self.stop_loss_percentage)
                
                # Check if we should trigger stop loss
                if current_price <= stop_price:
                    self.log(f"SCHEDULED STOP LOSS: {symbol} at ${current_price:.2f} (stop: ${stop_price:.2f})")
                    
                    # Add to blacklist
                    stock_ticker = str(symbol).split()[0]
                    self.blacklisted_stocks.add(stock_ticker)
                    self.stock_blacklist_dates[stock_ticker] = self.time
                    self.log(f"Added {stock_ticker} to blacklist for {self.blacklist_duration} days")
                    
                    # Liquidate position
                    self.liquidate(symbol)
                    
                    # Clean up tracking
                    if symbol in self.highest_prices:
                        del self.highest_prices[symbol]
                    
                    # Flag for rebalancing
                    stop_loss_executed = True
                        
            except Exception as e:
                self.log(f"Error in stop loss check for {symbol}: {str(e)}")
        
        # NEW: Trigger rebalancing if any stop loss was executed
        if stop_loss_executed:
            self.stop_loss_triggered = True
            self.need_rebalance_after_stop_loss = True
            self.log("Scheduled stop loss executed - will rebalance with new stocks")

    def UpdateUniverse(self):
        """Update the selected sectors based on ETF performance"""
        # Skip if still in warmup period or in emergency mode
        if not self.is_warmed_up or self.emergency_liquidation:
            return
        
        # Step 1: Calculate sector returns
        etf_symbols = list(self.sector_etf_map.values())
        
        if not etf_symbols:
            self.log("No sector ETFs defined. Cannot update sector returns.")
            return

        history = self.history(etf_symbols, self.lookback_days, resolution=Resolution.DAILY)
        
        if history is None or history.empty:
            self.log("ETF history data is empty. Cannot update sector returns.")
            self.sector_returns = {}
            return

        temp_sector_returns = {}
        for symbol, df in history.groupby(level=0):
            if len(df) < 2: continue
            
            start_price = df.iloc[0]['close']
            end_price = df.iloc[-1]['close']
            
            if start_price > 0:
                ret = (end_price / start_price) - 1
                sector_code = next((k for k, v in self.sector_etf_map.items() if v == symbol), None)
                if sector_code: temp_sector_returns[sector_code] = ret
        
        self.sector_returns = temp_sector_returns
        
        # Step 2: Select the top-performing sectors
        sorted_sectors = sorted(self.sector_returns.items(), key=lambda x: x[1], reverse=True)
        rising_sectors = [sector for sector, _ in sorted_sectors[:self.num_sectors]]
        
        self.selected_sectors = rising_sectors
        
        self.log(f"Selected rising sectors: {rising_sectors}")
        for sector, ret in sorted_sectors[:self.num_sectors]:
            self.log(f"  {sector}: {ret:.2%}")

    def coarse_selection_function(self, coarse):
        """Coarse universe selection"""
        if not self.is_warmed_up or self.emergency_liquidation:
            return Universe.UNCHANGED
            
        # RESTORED: Your original coarse filtering logic
        filtered = [x for x in coarse if x.has_fundamental_data and x.market_cap > 1e9 and x.dollar_volume > 10e6 and x.price > 5]
        sorted_by_volume = sorted(filtered, key=lambda x: x.dollar_volume, reverse=True)
        
        return [x.symbol for x in sorted_by_volume[:500]]

    def fine_selection_function(self, fine):
        """Fine universe selection - RESTORED and IMPLEMENTED"""
        if not self.selected_sectors or self.emergency_liquidation:
            self.log("No selected sectors available or in emergency mode")
            return []
        
        # RESTORED: Use your sector stocks dictionary for selection
        selected_stocks = []
        
        for sector in self.selected_sectors:
            if sector in self.sector_stocks_map:
                sector_stocks = self.sector_stocks_map[sector]
                # NEW: Filter out blacklisted stocks
                filtered_stocks = [stock for stock in sector_stocks if stock not in self.blacklisted_stocks]
                selected_stocks.extend(filtered_stocks)
        
        if not selected_stocks:
            self.log("No stocks found in selected sectors (after blacklist filter)")
            return []
        
        # Convert to symbols and limit to num_stocks
        final_universe = []
        for stock_ticker in selected_stocks[:self.num_stocks]:
            try:
                symbol = Symbol.create(stock_ticker, SecurityType.EQUITY, Market.USA)
                final_universe.append(symbol)
            except:
                self.log(f"Could not create symbol for {stock_ticker}")
                continue
        
        self.log(f"Selected {len(final_universe)} stocks: {[str(s) for s in final_universe]}")
        if self.blacklisted_stocks:
            self.log(f"Blacklisted stocks: {list(self.blacklisted_stocks)}")
        
        # Store the universe symbols for trading
        self.universe_symbols = final_universe
        
        # Clean up stop loss tracking for symbols no longer in universe
        self.cleanup_stop_loss_tracking(final_universe)
        
        # If no stocks selected, return unchanged to avoid empty universe
        if not final_universe:
            self.log("Warning: No stocks selected, returning unchanged universe")
            return Universe.UNCHANGED
        
        return final_universe
    
    def cleanup_stop_loss_tracking(self, new_universe):
        """Clean up stop loss tracking for symbols no longer in universe"""
        universe_symbols = set(str(s) for s in new_universe)
        
        # Remove tracking for symbols no longer in universe
        symbols_to_remove = []
        for symbol in self.highest_prices.keys():
            if str(symbol) not in universe_symbols:
                symbols_to_remove.append(symbol)
                
        for symbol in symbols_to_remove:
            if symbol in self.highest_prices:
                del self.highest_prices[symbol]

    # NEW: End of day processing
    def OnEndOfDay(self):
        """End of day processing"""
        # Clean up blacklist daily
        self.clean_blacklist()
        
        if self.emergency_liquidation:
            # Check if we should exit emergency mode (e.g., after 30 days)
            # This is conservative - you might want to add conditions to re-enter
            pass
