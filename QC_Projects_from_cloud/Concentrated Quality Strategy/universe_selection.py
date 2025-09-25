"""
Universe Selection Module
Handles coarse and fine selection, sector analysis, and stock filtering
"""

from AlgorithmImports import *
from utils import (
    StrategyConfig, SECTOR_ETF_MAP, DEFAULT_SECTOR_FILTERS,
    passes_fundamental_filters, calculate_fundamental_score, build_final_universe,
    get_sector_etf_symbols, log_sector_performance, log_filter_status
)
from momentum_utils import check_positive_momentum, log_momentum_summary
from SNP_Influencers import IntegratedSP500Tracker
from dynamic_sector_mapper import DynamicSectorMapper

class UniverseSelector:
    """Handles universe selection logic"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.lookback_days = StrategyConfig.LOOKBACK_DAYS
        self.num_stocks = StrategyConfig.NUM_STOCKS
        self.num_sectors = StrategyConfig.NUM_SECTORS
        self.sector_returns = {}
        self.sector_etf_map = get_sector_etf_symbols(algorithm)
        self.sector_mapper = DynamicSectorMapper(algorithm)  # Use dynamic mapper
        self.sector_filters = DEFAULT_SECTOR_FILTERS.copy()
        self.last_filter_update = datetime.min
        self.filter_update_frequency = StrategyConfig.FILTER_UPDATE_FREQUENCY
        self.selected_sectors = []
        
        # Initialize S&P 500 tracker
        self.sp500_tracker = IntegratedSP500Tracker(algorithm)
    
    def coarse_selection_function(self, coarse):
        """Coarse selection function for universe selection"""
        try:
            # Update sector mapping if needed
            if self.sector_mapper.should_update():
                self.sector_mapper.update_sector_mapping(coarse)
            
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
                return Universe.UNCHANGED
            
            # Filter stocks by sector and fundamentals
            sector_filtered_stocks = {}
            
            for sector in self.selected_sectors:
                sector_stocks = self.sector_mapper.get_sector_stocks(sector)
                if not sector_stocks:
                    continue
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

                    # Skip momentum filter - let fundamentals drive selection
                    # if not check_positive_momentum(self.algorithm, stock_ticker, stock_fine_data, momentum_results):
                    #     continue

                    try:
                        pe_ratio = stock_fine_data.valuation_ratios.pe_ratio
                        roe = stock_fine_data.operation_ratios.roe.one_year
                        score = calculate_fundamental_score((stock_ticker, stock_fine_data, pe_ratio, roe), sector, self.algorithm)
                        actual_ticker = stock_fine_data.symbol.Value  
                        filtered_stocks.append((actual_ticker, stock_fine_data, score))
                    except Exception as e:
                        continue

                # Log momentum summary for this sector
                log_momentum_summary(self.algorithm, momentum_results, sector)
                
                # Apply momentum decay to prevent getting stuck with same stocks
                from volatility_utils import should_force_rotation
                force_rotation = should_force_rotation(self.algorithm, self.algorithm.spy)
                
                for i, (ticker, fine_data, score) in enumerate(filtered_stocks):
                    # Check if this stock has been held for too long
                    symbol = fine_data.symbol
                    if (self.algorithm.portfolio.contains_key(symbol) and 
                        self.algorithm.portfolio[symbol].invested):
                        
                        # Use a simpler approach - track holding time in algorithm state
                        if not hasattr(self.algorithm, 'stock_holding_start'):
                            self.algorithm.stock_holding_start = {}
                        
                        # Initialize holding start time if not set
                        if symbol not in self.algorithm.stock_holding_start:
                            self.algorithm.stock_holding_start[symbol] = self.algorithm.time
                        
                        # Calculate days held
                        days_held = (self.algorithm.time - self.algorithm.stock_holding_start[symbol]).days
                        
                        # More aggressive decay in sideways/volatile markets
                        if force_rotation:
                            if days_held > 14:  # Shorter holding period in sideways markets
                                decay_factor = max(0.3, 1.0 - (days_held - 14) * 0.05)  # 5% decay per day
                                filtered_stocks[i] = (ticker, fine_data, score * decay_factor)
                        else:
                            if days_held > 30:  # Normal holding period
                                decay_factor = max(0.5, 1.0 - (days_held - 30) * 0.02)  # 2% decay per day
                                filtered_stocks[i] = (ticker, fine_data, score * decay_factor)
                
                # Sort by score and take top 3 stocks per sector (more candidates)
                filtered_stocks.sort(key=lambda x: x[2], reverse=True)
                sector_filtered_stocks[sector] = filtered_stocks[:3]
            
            # Apply SECTOR BIAS - heavily favor tech and growth sectors
            biased_sector_stocks = {}
            for sector, stocks in sector_filtered_stocks.items():
                if sector == "Information Technology":
                    # Tech gets 2x weight (most important for alpha)
                    biased_sector_stocks[sector] = stocks[:6]  # Take top 6 tech stocks
                elif sector in ["Communication Services", "Consumer Discretionary"]:
                    # Growth sectors get 1.5x weight
                    biased_sector_stocks[sector] = stocks[:4]  # Take top 4 stocks
                else:
                    # Other sectors get normal weight
                    biased_sector_stocks[sector] = stocks[:2]  # Take top 2 stocks
            
            # Build sector-based universe (6 stocks total: 3 tech + 2 growth + 1 other)
            sector_universe = build_final_universe(self.algorithm, biased_sector_stocks, 6)
            
            # Check if sector_universe is valid
            if sector_universe == Universe.UNCHANGED:
                return Universe.UNCHANGED
            
            # Focus only on best sector picks (no S&P 500 integration)
            final_universe = list(sector_universe)
            
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
            rising_sectors = log_sector_performance(self.algorithm, sector_returns, self.num_sectors, self.sector_mapper)
            
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
    
    def analyze_sp500_influence(self):
        """Analyze missing S&P 500 leaders"""
        try:
            if hasattr(self, 'sp500_tracker') and self.sp500_tracker is not None:
                current_symbols = [s.value for s in self.algorithm.universe_symbols] if hasattr(self.algorithm, 'universe_symbols') else []
                self.sp500_tracker.analyze_sp500_influence(current_symbols)
        except Exception as e:
            self.algorithm.log(f"Error in S&P 500 analysis: {str(e)}")
