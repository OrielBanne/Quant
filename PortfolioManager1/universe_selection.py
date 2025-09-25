"""
Universe Selection Module
Handles coarse and fine selection, sector analysis, and stock filtering
"""

from AlgorithmImports import *
from utils import (
    StrategyConfig, SECTOR_ETF_MAP, DEFAULT_SECTOR_FILTERS, SECTOR_STOCKS_MAP,
    passes_fundamental_filters, calculate_fundamental_score, build_final_universe,
    get_sector_etf_symbols, log_sector_performance, log_filter_status
)
from momentum_utils import check_positive_momentum, log_momentum_summary
from SNP_Influencers import IntegratedSP500Tracker

class UniverseSelector:
    """Handles universe selection logic"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.lookback_days = StrategyConfig.LOOKBACK_DAYS
        self.num_stocks = StrategyConfig.NUM_STOCKS
        self.num_sectors = StrategyConfig.NUM_SECTORS
        self.sector_returns = {}
        self.sector_etf_map = get_sector_etf_symbols(algorithm)
        self.sector_stocks_map = SECTOR_STOCKS_MAP
        self.sector_filters = DEFAULT_SECTOR_FILTERS.copy()
        self.last_filter_update = datetime.min
        self.filter_update_frequency = StrategyConfig.FILTER_UPDATE_FREQUENCY
        self.selected_sectors = []
        
        # Initialize S&P 500 tracker
        self.sp500_tracker = IntegratedSP500Tracker(algorithm)
    
    def coarse_selection_function(self, coarse):
        """Coarse selection function for universe selection"""
        try:
            # Filter by market cap, dollar volume, and price
            filtered = [x for x in coarse if 
                       x.market_cap > StrategyConfig.MIN_MARKET_CAP and
                       x.dollar_volume > StrategyConfig.MIN_DOLLAR_VOLUME and
                       x.price > StrategyConfig.MIN_PRICE]
            
            # Sort by dollar volume and take top stocks
            sorted_by_volume = sorted(filtered, key=lambda x: x.dollar_volume, reverse=True)
            
            # Take top stocks for fine selection
            return [x.symbol for x in sorted_by_volume[:200]]
            
        except Exception as e:
            self.algorithm.log(f"Error in coarse selection: {str(e)}")
            return Universe.UNCHANGED
    
    def fine_selection_function(self, fine):
        """Fine selection function for universe selection"""
        try:
            # Convert iterator to list to allow multiple consumption
            fine_data_list = list(fine)
            
            # Process S&P 500 data early
            if hasattr(self, 'sp500_tracker') and self.sp500_tracker is not None:
                try:
                    self.sp500_tracker.process_fine_data_for_sp500(fine_data_list)
                except Exception as e:
                    self.algorithm.log(f"S&P 500 processing error: {str(e)}")
            
            # Create lookup dictionary for fine data
            fine_data_lookup = {data.symbol.value: data for data in fine_data_list}
            
            # Get selected sectors
            self.selected_sectors = self.get_rising_sectors()
            
            if not self.selected_sectors:
                self.algorithm.log("No rising sectors found")
                return Universe.UNCHANGED
            
            # Filter stocks by sector and fundamentals
            sector_filtered_stocks = {}
            
            for sector in self.selected_sectors:
                if sector not in self.sector_stocks_map:
                    continue
                
                sector_stocks = self.sector_stocks_map[sector]
                sector_filter = self.sector_filters[sector]
                filtered_stocks = []
                momentum_results = []
                
                for stock_ticker in sector_stocks:
                    if stock_ticker in self.algorithm.risk_manager.blacklisted_stocks:
                        continue
                    
                    try:
                        stock_fine_data = fine_data_lookup[stock_ticker]
                    except:
                        stock_fine_data = None
                        continue

                    if not passes_fundamental_filters(stock_fine_data, sector_filter, stock_ticker=stock_ticker, algorithm=self.algorithm):
                        continue

                    # Check for positive momentum - only include stocks with upward momentum
                    if not check_positive_momentum(self.algorithm, stock_ticker, stock_fine_data, momentum_results):
                        continue

                    try:
                        pe_ratio = stock_fine_data.valuation_ratios.pe_ratio
                        roe = stock_fine_data.operation_ratios.roe.one_year
                        score = calculate_fundamental_score((stock_ticker, stock_fine_data, pe_ratio, roe), sector)
                        actual_ticker = stock_fine_data.symbol.Value  
                        filtered_stocks.append((actual_ticker, stock_fine_data, score))
                    except Exception as e:
                        continue

                # Log momentum summary for this sector
                log_momentum_summary(self.algorithm, momentum_results, sector)
                
                # Sort by score and take top 3 stocks per sector
                filtered_stocks.sort(key=lambda x: x[2], reverse=True)
                sector_filtered_stocks[sector] = filtered_stocks[:3]
            
            # Build sector-based universe (12 stocks: 3 per sector)
            sector_universe = build_final_universe(self.algorithm, sector_filtered_stocks, 12)
            
            # Check if sector_universe is valid
            if sector_universe == Universe.UNCHANGED:
                self.algorithm.log("No sector stocks selected - returning unchanged universe")
                return Universe.UNCHANGED
            
            # Get S&P 500 stocks (8 stocks) with momentum filtering
            sp500_stocks = []
            if hasattr(self, 'sp500_tracker') and self.sp500_tracker is not None:
                try:
                    sp500_stocks = self.sp500_tracker.get_top_missing_sp500_stocks(sector_universe, top_n=8, algorithm=self.algorithm)
                    if sp500_stocks:
                        sp500_names = [s.value for s in sp500_stocks]
                        self.algorithm.log(f"S&P 500 stocks ({len(sp500_stocks)} stocks): {sp500_names}")
                    else:
                        self.algorithm.log("No S&P 500 stocks available (all filtered out by momentum)")
                except Exception as e:
                    self.algorithm.log(f"S&P 500 error: {str(e)}")
            
            # Combine sector and S&P 500 stocks, removing duplicates
            final_universe = list(sector_universe)
            sector_symbols = {s.value for s in sector_universe}
            
            for sp500_symbol in sp500_stocks:
                if sp500_symbol.value not in sector_symbols:
                    final_universe.append(sp500_symbol)
            
            self.algorithm.log(f"Final universe: {len(final_universe)} stocks ({len(sector_universe)} sector + {len(final_universe) - len(sector_universe)} S&P 500)")
            
            return final_universe if final_universe else Universe.UNCHANGED
            
        except Exception as e:
            self.algorithm.log(f"Error in fine selection: {str(e)}")
            return Universe.UNCHANGED
    
    def get_rising_sectors(self):
        """Get the top performing sectors"""
        try:
            # Calculate sector returns
            sector_returns = {}
            
            for sector, etf_symbol in self.sector_etf_map.items():
                try:
                    # Get historical data for the ETF
                    history = self.algorithm.history(etf_symbol, self.lookback_days, Resolution.DAILY)
                    
                    if history is None or history.empty:
                        continue
                    
                    # Calculate return over the lookback period
                    start_price = history['close'].iloc[0]
                    end_price = history['close'].iloc[-1]
                    sector_return = (end_price - start_price) / start_price
                    
                    sector_returns[sector] = sector_return
                    
                except Exception as e:
                    self.algorithm.log(f"Error calculating return for {sector}: {str(e)}")
                    continue
            
            if not sector_returns:
                self.algorithm.log("No sector returns calculated")
                return []
            
            # Log sector performance and get top sectors
            rising_sectors = log_sector_performance(self.algorithm, sector_returns, self.num_sectors)
            
            return rising_sectors
            
        except Exception as e:
            self.algorithm.log(f"Error getting rising sectors: {str(e)}")
            return []
    
    def update_sector_filters(self):
        """Update sector-specific fundamental filters"""
        try:
            current_time = self.algorithm.time
            
            # Check if it's time to update filters
            if (current_time - self.last_filter_update).days < self.filter_update_frequency:
                return
            
            self.algorithm.log("Updating sector filters...")
            
            # Update filters based on current market conditions
            # This could be enhanced with dynamic filter adjustment
            self.sector_filters = DEFAULT_SECTOR_FILTERS.copy()
            
            self.last_filter_update = current_time
            
            # Log current filter status
            log_filter_status(self.algorithm, self.sector_filters, self.selected_sectors)
            
        except Exception as e:
            self.algorithm.log(f"Error updating sector filters: {str(e)}")
            # Fall back to default filters
            self.sector_filters = DEFAULT_SECTOR_FILTERS.copy()
    
    def analyze_missing_sp500_leaders(self):
        """Analyze missing S&P 500 leaders"""
        try:
            if hasattr(self, 'sp500_tracker') and self.sp500_tracker is not None:
                current_symbols = [s.value for s in self.algorithm.universe_symbols] if hasattr(self.algorithm, 'universe_symbols') else []
                self.sp500_tracker.analyze_sp500_influence(current_symbols)
        except Exception as e:
            self.algorithm.log(f"Error in S&P 500 analysis: {str(e)}")
