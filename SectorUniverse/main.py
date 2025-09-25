from AlgorithmImports import *

class RisingSectorFundamentalUniverse(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2025, 8, 1)
        self.set_cash(100000)
        
        # We need a benchmark to compare against
        self.spy = self.add_equity("SPY", Resolution.DAILY).Symbol
        
        self.lookback_days = 60
        self.num_stocks = 10
        self.num_sectors = 3
        self.sector_returns = {}
        
        # Mapping of Morningstar sectors to a representative ETF
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

        # Schedule the universe selection and sector return calculation
        self.schedule.on(self.date_rules.every_day(), self.time_rules.after_market_open(self.spy, 30), self.UpdateUniverse)
        
        # Schedule daily stop loss checks (more frequent than rebalancing)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.every(timedelta(hours=1)), self.check_stop_losses)
        
        # We'll use a single variable to store the universe of symbols.
        self.universe_symbols = []
        
        # Store the selected sectors for use in universe selection
        self.selected_sectors = []
        
        # Add universe selection with proper coarse and fine filters
        self.add_universe(self.coarse_selection_function, self.fine_selection_function)
        
        # Add rebalancing controls
        self.last_rebalance = datetime.min
        self.rebalance_frequency = 30  # Rebalance every 30 days, not daily
        
        # Stop loss controls
        self.stop_loss_percentage = 0.10  # 10% stop loss
        self.trailing_stop_percentage = 0.03  # 5% trailing stop
        self.highest_prices = {}  # Track highest prices for trailing stops
        self.stop_loss_orders = {}  # Track stop loss orders
        
        # Warmup period to ensure we have enough data
        self.warmup_period = 50  # days of warmup
        self.is_warmed_up = False
        self.start_time = self.time  # Track when algorithm started
        
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
        # Check if we're still in warmup period
        if not self.is_warmed_up:
            if self.time < self.start_time + timedelta(days=self.warmup_period):
                return
            else:
                self.is_warmed_up = True
                self.log(f"Warmup period completed at {self.time}")
        
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
            
        # Simple rebalancing logic - equal weight all stocks
        weight = 1.0 / len(self.universe_symbols) if self.universe_symbols else 0
        
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
            
        # Rebalance only valid symbols
        for symbol in valid_symbols:
            self.set_holdings(symbol, weight)
            
        self.last_rebalance = self.time
        self.log(f"Rebalanced portfolio with {len(valid_symbols)} symbols at {self.time}")
        
        # Update stop losses for all invested positions
        self.update_stop_losses(data)
    
    def update_stop_losses(self, data):
        """Update stop losses for all invested positions"""
        for symbol in self.portfolio.keys():
            if not self.portfolio[symbol].invested:
                continue
                
            if not data.contains_key(symbol):
                continue
                
            current_price = data[symbol].price
            position = self.portfolio[symbol]
            
            # Initialize highest price tracking
            if symbol not in self.highest_prices:
                self.highest_prices[symbol] = current_price
                
            # Update highest price for trailing stop
            if current_price > self.highest_prices[symbol]:
                self.highest_prices[symbol] = current_price
                
            # Calculate stop loss price
            # Use trailing stop if price has moved up, otherwise use fixed stop loss
            if self.highest_prices[symbol] > position.average_price:
                # Trailing stop: 5% below highest price
                stop_price = self.highest_prices[symbol] * (1 - self.trailing_stop_percentage)
            else:
                # Fixed stop loss: 10% below entry price
                stop_price = position.average_price * (1 - self.stop_loss_percentage)
            
            # Check if we should trigger stop loss
            if current_price <= stop_price:
                self.log(f"Stop loss triggered for {symbol}: Price ${current_price:.2f} <= Stop ${stop_price:.2f}")
                self.liquidate(symbol)
                # Clean up tracking
                if symbol in self.highest_prices:
                    del self.highest_prices[symbol]
                if symbol in self.stop_loss_orders:
                    del self.stop_loss_orders[symbol]
                # Trigger rebalancing after stop loss
                self.trigger_rebalance_after_stop_loss()
            else:
                # Update or create stop loss order
                self.update_stop_loss_order(symbol, stop_price)
    
    def update_stop_loss_order(self, symbol, stop_price):
        """Update or create stop loss order for a symbol"""
        try:
            if symbol in self.stop_loss_orders:
                # Update existing stop loss order
                order = self.stop_loss_orders[symbol]
                if order.status == OrderStatus.FILLED:
                    # Order was filled, clean up
                    del self.stop_loss_orders[symbol]
                    return
                    
                # Update the stop price
                update_fields = UpdateOrderFields()
                update_fields.stop_price = stop_price
                order.update(update_fields)
            else:
                # Create new stop loss order
                quantity = -self.portfolio[symbol].quantity  # Negative for sell order
                order = self.stop_market_order(symbol, quantity, stop_price)
                self.stop_loss_orders[symbol] = order
                
        except Exception as e:
            self.log(f"Error updating stop loss for {symbol}: {str(e)}")
    
    def trigger_rebalance_after_stop_loss(self):
        """Trigger immediate rebalancing after a stop loss"""
        self.log("Stop loss triggered - initiating immediate rebalancing")
        
        # Reset the rebalance timer to allow immediate rebalancing
        self.last_rebalance = datetime.min
        
        # Get current data for rebalancing
        if not self.universe_symbols:
            self.log("No universe symbols available for rebalancing after stop loss")
            return
            
        # Get current data
        data = self.history(self.universe_symbols, 1, Resolution.MINUTE)
        if data is None or data.empty:
            self.log("No data available for rebalancing after stop loss")
            return
            
        # Calculate equal weight for remaining positions
        valid_symbols = []
        for symbol in self.universe_symbols:
            if self.securities.contains_key(symbol) and symbol in data.index.get_level_values(0):
                valid_symbols.append(symbol)
        
        if not valid_symbols:
            self.log("No valid symbols for rebalancing after stop loss")
            return
            
        # Rebalance with equal weights
        weight = 1.0 / len(valid_symbols)
        
        for symbol in valid_symbols:
            if self.portfolio[symbol].invested:
                self.set_holdings(symbol, weight)
            else:
                # If symbol is not invested but should be, add it
                self.set_holdings(symbol, weight)
        
        self.log(f"Rebalanced after stop loss with {len(valid_symbols)} symbols at {self.time}")
        
        # Update the rebalance time
        self.last_rebalance = self.time
    
    def OnOrderEvent(self, orderEvent):
        """Handle order events, especially stop loss fills"""
        if orderEvent.status == OrderStatus.FILLED:
            symbol = orderEvent.symbol
            
            # If this was a stop loss order, clean up tracking and rebalance
            if symbol in self.stop_loss_orders and self.stop_loss_orders[symbol].order_id == orderEvent.order_id:
                self.log(f"Stop loss order filled for {symbol} at ${orderEvent.fill_price:.2f}")
                del self.stop_loss_orders[symbol]
                # Trigger rebalancing after stop loss order is filled
                self.trigger_rebalance_after_stop_loss()
                
            # Clean up highest price tracking if position is closed
            if symbol in self.highest_prices and not self.portfolio[symbol].invested:
                del self.highest_prices[symbol]
    
    def check_stop_losses(self):
        """Scheduled method to check stop losses more frequently"""
        # Skip if still in warmup period
        if not self.is_warmed_up:
            return
            
        if not self.portfolio.invested:
            return
            
        # Get current data for all invested symbols
        symbols = [symbol for symbol in self.portfolio.keys() if self.portfolio[symbol].invested]
        if not symbols:
            return
            
        # Get current prices
        data = self.history(symbols, 1, Resolution.MINUTE)
        if data is None or data.empty:
            return
            
        # Check stop losses for each symbol
        for symbol in symbols:
            if symbol not in data.index.get_level_values(0):
                continue
                
            current_price = data.loc[symbol].iloc[-1]['close']
            position = self.portfolio[symbol]
            
            # Initialize highest price tracking
            if symbol not in self.highest_prices:
                self.highest_prices[symbol] = current_price
                
            # Update highest price for trailing stop
            if current_price > self.highest_prices[symbol]:
                self.highest_prices[symbol] = current_price
                
            # Calculate stop loss price
            if self.highest_prices[symbol] > position.average_price:
                # Trailing stop: 5% below highest price
                stop_price = self.highest_prices[symbol] * (1 - self.trailing_stop_percentage)
            else:
                # Fixed stop loss: 10% below entry price
                stop_price = position.average_price * (1 - self.stop_loss_percentage)
            
            # Check if we should trigger stop loss
            if current_price <= stop_price:
                self.log(f"Stop loss triggered for {symbol}: Price ${current_price:.2f} <= Stop ${stop_price:.2f}")
                self.liquidate(symbol)
                # Clean up tracking
                if symbol in self.highest_prices:
                    del self.highest_prices[symbol]
                if symbol in self.stop_loss_orders:
                    del self.stop_loss_orders[symbol]
                # Trigger rebalancing after stop loss
                self.trigger_rebalance_after_stop_loss()

    def UpdateUniverse(self):
        """Update the selected sectors based on ETF performance"""
        # Skip if still in warmup period
        if not self.is_warmed_up:
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
        self.log(f"Top {self.num_sectors} sectors by return: {[s for s in rising_sectors]}")

        # Store the selected sectors for use in universe selection
        self.selected_sectors = rising_sectors

    def coarse_selection_function(self, coarse):
        """Coarse selection function for universe selection"""
        # If no sectors selected yet, return empty list
        if not self.selected_sectors:
            return Universe.UNCHANGED
            
        # Predefined major stocks per sector
        sector_stocks_map = {
            "Information Technology": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "AMD", "INTC"],
            "Communication Services": ["GOOG", "GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR"],
            "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
            "Financials": ["BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "AXP"],
            "Health Care": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "PFE", "TMO", "ABT", "DHR", "BMY"],
            "Industrials": ["CAT", "GE", "HON", "UPS", "FDX", "MMM", "RTX", "LMT", "DE", "BA"],
            "Consumer Staples": ["WMT", "PG", "COST", "KO", "PEP", "CL", "KMB", "GIS", "K", "CPB"],
            "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "PXD", "KMI", "WMB", "MPC", "VLO"],
            "Materials": ["LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF"],
            "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR", "MAA", "SPG"],
            "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "WEC"]
        }
        
        # Get all stocks from selected sectors
        candidate_symbols = []
        for sector in self.selected_sectors:
            sector_stocks = sector_stocks_map.get(sector, [])
            candidate_symbols.extend(sector_stocks)
        
        # Filter coarse data to only include our candidate symbols
        filtered = [x for x in coarse if x.Symbol.Value in candidate_symbols and x.HasFundamentalData and x.Price > 5 and x.DollarVolume > 1000000]
        
        # Sort by dollar volume and return top 100
        sorted_by_volume = sorted(filtered, key=lambda x: x.DollarVolume, reverse=True)
        return [x.Symbol for x in sorted_by_volume[:100]]

    def fine_selection_function(self, fine):
        """Fine selection function for universe selection"""
        if not self.selected_sectors:
            self.log("No sectors selected, returning unchanged universe")
            return Universe.UNCHANGED
            
        if not fine:
            self.log("No fine data available, returning unchanged universe")
            return Universe.UNCHANGED

            
        # Predefined major stocks per sector
        sector_stocks_map = {
                "Information Technology": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "AMD", "INTC"],
                "Communication Services": ["GOOG", "GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR"],
                "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
                "Financials": ["BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "AXP"],
                "Health Care": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "PFE", "TMO", "ABT", "DHR", "BMY"],
                "Industrials": ["CAT", "GE", "HON", "UPS", "FDX", "MMM", "RTX", "LMT", "DE", "BA"],
                "Consumer Staples": ["WMT", "PG", "COST", "KO", "PEP", "CL", "KMB", "GIS", "K", "CPB"],
                "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "PXD", "KMI", "WMB", "MPC", "VLO"],
                "Materials": ["LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF"],
                "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR", "MAA", "SPG"],
                "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "WEC"]
            }
        
        final_universe = []
        
        # Process each selected sector
        for sector in self.selected_sectors:
            sector_stocks = sector_stocks_map.get(sector, [])
            if not sector_stocks:
                continue
                
            # Filter fine data for this sector
            sector_fine = [f for f in fine if f.Symbol.Value in sector_stocks]
            
            # Apply fundamental filters
            qualified_stocks = []
            filtered_count = 0
            
            for f in sector_fine:
                try:
                    if f.ValuationRatios is None or f.OperationRatios is None:
                        filtered_count += 1
                        continue
            
                    pe = f.ValuationRatios.PERatio
                    roe = f.OperationRatios.ROE.Value if f.OperationRatios.ROE and f.OperationRatios.ROE.HasValue else None
                    current_ratio = f.OperationRatios.CurrentRatio.Value if f.OperationRatios.CurrentRatio and f.OperationRatios.CurrentRatio.HasValue else None
                    debt = f.FinancialStatements.BalanceSheet.TotalDebt.Value if f.FinancialStatements.BalanceSheet.TotalDebt and f.FinancialStatements.BalanceSheet.TotalDebt.HasValue else None
            
                    # More lenient fundamental filters with logging
                    if pe is None or pe <= 0 or pe > 100: 
                        filtered_count += 1
                        continue  # Relaxed PE filter
                    if roe is None or roe < 0.05: 
                        filtered_count += 1
                        continue  # Relaxed ROE filter (5% instead of 10%)
                    if current_ratio is None or current_ratio < 1.0: 
                        filtered_count += 1
                        continue  # Relaxed current ratio
                    if debt is not None and debt > 5e10: 
                        filtered_count += 1
                        continue  # Relaxed debt filter
                    
                    # Score by ROE and Market Cap
                    score = roe * (f.MarketCap / 1e9)  # ROE * Market Cap in billions
                    qualified_stocks.append((f.Symbol, score))
                    
                except Exception as e:
                    self.log(f"Error processing {f.Symbol}: {str(e)}")
                    filtered_count += 1
                    continue
            
            self.log(f"Sector {sector}: {len(sector_fine)} candidates, {filtered_count} filtered out, {len(qualified_stocks)} qualified")
            
            # Sort by score and take top 3 from this sector
            if qualified_stocks:
                qualified_stocks = sorted(qualified_stocks, key=lambda x: x[1], reverse=True)
                top_3_sector = [symbol for symbol, _ in qualified_stocks[:3]]
            else:
                # Fallback: if no stocks pass fundamental filters, take first 3 from sector
                self.log(f"No stocks passed fundamental filters for {sector}, using fallback selection")
                top_3_sector = [f.Symbol for f in sector_fine[:3]]
            
            final_universe.extend(top_3_sector)
            self.log(f"Selected {len(top_3_sector)} stocks from {sector}: {[str(s) for s in top_3_sector]}")
        
        self.log(f"Final Universe ({len(final_universe)} stocks): {[str(s) for s in final_universe]}")
        
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
            if symbol in self.stop_loss_orders:
                # Cancel the stop loss order
                try:
                    self.stop_loss_orders[symbol].cancel()
                except:
                    pass
                del self.stop_loss_orders[symbol]
