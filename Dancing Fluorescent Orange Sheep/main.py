from AlgorithmImports import *

class RisingSectorFundamentalUniverse(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2022, 1, 1)
        self.set_end_date(2025, 8, 1)  # Add end date
        self.set_cash(100000)
        
        # We need a benchmark to compare against
        self.spy = self.add_equity("SPY", Resolution.DAILY).Symbol
        
        self.lookback_days = 60
        self.num_stocks = 10
        self.num_sectors = 3
        self.sector_returns = {}
        
        # Mapping of Morningstar sectors to a representative ETF
        self.sector_etf_map = {
            "BasicMaterials": self.add_equity("XLB", Resolution.DAILY).Symbol,
            "ConsumerCyclical": self.add_equity("XLY", Resolution.DAILY).Symbol,
            "ConsumerDefensive": self.add_equity("XLP", Resolution.DAILY).Symbol,
            "Energy": self.add_equity("XLE", Resolution.DAILY).Symbol,
            "FinancialServices": self.add_equity("XLF", Resolution.DAILY).Symbol,
            "Healthcare": self.add_equity("XLV", Resolution.DAILY).Symbol,
            "Industrials": self.add_equity("XLI", Resolution.DAILY).Symbol,
            "RealEstate": self.add_equity("XLRE", Resolution.DAILY).Symbol,
            "Technology": self.add_equity("XLK", Resolution.DAILY).Symbol,
            "Utilities": self.add_equity("XLU", Resolution.DAILY).Symbol,
            "CommunicationServices": self.add_equity("XLC", Resolution.DAILY).Symbol,
        }

        # Schedule the universe selection and sector return calculation
        self.schedule.on(self.date_rules.every_day(), self.time_rules.after_market_open(self.spy, 30), self.UpdateUniverse)
        
        # We'll use a single variable to store the universe of symbols.
        self.universe_symbols = []
        
        # Store the selected sectors for use in universe selection
        self.selected_sectors = []
        
        # Add universe selection with proper coarse and fine filters
        self.add_universe(self.coarse_selection_function, self.fine_selection_function)
        
        # Add rebalancing controls
        self.last_rebalance = datetime.min
        self.rebalance_frequency = 30  # Rebalance every 30 days, not daily

    def OnData(self, data):
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

    def UpdateUniverse(self):
        """Update the selected sectors based on ETF performance"""
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
            "BasicMaterials": ["LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF"],
            "ConsumerCyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
            "ConsumerDefensive": ["PG", "KO", "PEP", "WMT", "COST", "CL", "KMB", "GIS", "K", "CPB"],
            "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "PXD", "KMI", "WMB", "MPC", "VLO"],
            "FinancialServices": ["JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SPGI", "CB"],
            "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN"],
            "Industrials": ["BA", "CAT", "GE", "HON", "UPS", "FDX", "MMM", "RTX", "LMT", "DE"],
            "RealEstate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR", "MAA", "SPG"],
            "Technology": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX", "CRM", "ADBE"],
            "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "WEC"],
            "CommunicationServices": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "CHTR", "TMUS", "ATVI"]
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
            "BasicMaterials": ["LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF"],
            "ConsumerCyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
            "ConsumerDefensive": ["PG", "KO", "PEP", "WMT", "COST", "CL", "KMB", "GIS", "K", "CPB"],
            "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "PXD", "KMI", "WMB", "MPC", "VLO"],
            "FinancialServices": ["JPM", "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SPGI", "CB"],
            "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN"],
            "Industrials": ["BA", "CAT", "GE", "HON", "UPS", "FDX", "MMM", "RTX", "LMT", "DE"],
            "RealEstate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR", "MAA", "SPG"],
            "Technology": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX", "CRM", "ADBE"],
            "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "WEC"],
            "CommunicationServices": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "CHTR", "TMUS", "ATVI"]
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
        
        # If no stocks selected, return unchanged to avoid empty universe
        if not final_universe:
            self.log("Warning: No stocks selected, returning unchanged universe")
            return Universe.UNCHANGED
        
        return final_universe
