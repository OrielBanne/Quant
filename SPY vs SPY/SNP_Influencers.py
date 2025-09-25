"""s
Integrated S&P 500 Analysis - Works WITH Your Existing Universe
No parallel universe - integrates S&P 500 analysis into your existing system
"""

# SOLUTION: Integrate S&P 500 analysis into your EXISTING universe selection
# Instead of creating a parallel universe, we'll enhance your existing fine_selection_function

from AlgorithmImports import *
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from momentum_utils import check_positive_momentum, calculate_williams_alligator_momentum, log_momentum_summary

class IntegratedSP500Tracker:
    """S&P 500 analysis that works with your existing universe selection"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.sp500_candidates = {}  # Large cap stocks from your universe
        self.sp500_analysis_data = {}
       
        self.last_sp500_analysis = None
        self.analysis_frequency = 7  # Weekly analysis

    def initialize(self):
        """Initialize S&P 500 tracking without creating separate universe"""
        try:
            # FIXED: Use existing SPY symbol instead of creating new one
            if hasattr(self.algorithm, 'spy'):
                self.spy_symbol = self.algorithm.spy
                self.algorithm.log("Using existing SPY symbol for S&P 500 tracker")
            else:
                # Fallback: create SPY if it doesn't exist
                self.spy_symbol = self.algorithm.add_equity("SPY", Resolution.DAILY).symbol
                self.algorithm.log("Created new SPY symbol for S&P 500 tracker")

        except Exception as e:
            self.algorithm.log(f"Error initializing S&P 500 tracker: {str(e)}")
            self.spy_symbol = None
        

    def process_fine_data_for_sp500(self, fine_data_list):
        """Process fine data to identify S&P 500 candidates - call this from your fine_selection_function"""
        try:
            # Clear previous data
            self.sp500_candidates = {}
            
            # Process all stocks from your universe selection
            large_cap_stocks = []
            
            # Convert iterator to list for processing and counting
            fine_data_list = list(fine_data_list)
            for stock_fine_data in fine_data_list:
                try:
                    symbol = stock_fine_data.symbol
                    symbol_str = symbol.value
                    market_cap = stock_fine_data.market_cap
                    
                    # Identify S&P 500 candidates (large cap stocks)
                    if market_cap > 3e9:  # $3B+ market cap
                        sector = self.get_sector_from_fine_data(stock_fine_data)
                        
                        large_cap_stocks.append({
                            'symbol_str': symbol_str,
                            'symbol': symbol,
                            'market_cap': market_cap,
                            'sector': sector,
                            'fine_data': stock_fine_data
                        })
                
                except Exception as e:
                    continue
            
            # Sort by market cap and take top 500 (S&P 500 approximation)
            large_cap_stocks.sort(key=lambda x: x['market_cap'], reverse=True)
            top_500 = large_cap_stocks[:500]
            
            # Calculate weights
            total_market_cap = sum(stock['market_cap'] for stock in top_500)
            
            # Store S&P 500 candidates
            for stock in top_500:
                weight = (stock['market_cap'] / total_market_cap) * 100 if total_market_cap > 0 else 0
                
                self.sp500_candidates[stock['symbol_str']] = {
                    'symbol': stock['symbol'],
                    'market_cap': stock['market_cap'],
                    'sector': stock['sector'],
                    'weight': weight,
                    'fine_data': stock['fine_data']
                }
            
            if len(self.sp500_candidates) == 0:
                self.algorithm.log("No S&P 500 candidates identified")
            
        except Exception as e:
            self.algorithm.log(f"Error processing S&P 500 candidates: {str(e)}")
    
    def get_sector_from_fine_data(self, fine_data):
        """Extract sector from fundamental data"""
        try:
            if hasattr(fine_data, 'asset_classification'):
                asset_class = fine_data.asset_classification
                if hasattr(asset_class, 'morningstar_sector_code'):
                    morningstar_sector = asset_class.morningstar_sector_code
                    return self._convert_morningstar_to_gics(morningstar_sector)
            return "Unknown"
        except:
            return "Unknown"
    
    def _convert_morningstar_to_gics(self, morningstar_code):
        """Convert Morningstar sector code to GICS sector"""
        if morningstar_code is None:
            return "Unknown"
        
        morningstar_to_gics = {
            311: "Information Technology", 312: "Information Technology", 313: "Information Technology",
            501: "Communication Services", 502: "Communication Services", 503: "Communication Services",
            205: "Consumer Discretionary", 206: "Consumer Discretionary", 208: "Consumer Discretionary",
            207: "Consumer Staples", 209: "Consumer Staples",
            103: "Financials", 104: "Financials", 105: "Financials", 107: "Financials",
            204: "Health Care", 210: "Health Care", 211: "Health Care",
            310: "Industrials", 309: "Industrials", 315: "Industrials",
            101: "Energy", 108: "Energy",
            102: "Materials", 212: "Materials", 213: "Materials",
            106: "Real Estate", 214: "Real Estate",
            308: "Utilities", 215: "Utilities"
        }
        
        return morningstar_to_gics.get(morningstar_code, "Unknown")
    
    def analyze_sp500_influence(self, current_universe_symbols, period_days=30):
        """Analyze S&P 500 influence using identified candidates"""
        try:
            if len(self.sp500_candidates) == 0:
                return None
            
            # Calculate SPY performance
            spy_performance = self.calculate_spy_performance(period_days)
            if spy_performance is None:
                return None
            
            # Calculate influence for each S&P 500 candidate
            influences = []
            
            for symbol_str, data in self.sp500_candidates.items():
                influence = self.calculate_stock_influence(symbol_str, data, period_days)
                if influence is not None:
                    influences.append(influence)
            
            # Sort by positive contribution
            positive_influences = [inf for inf in influences if inf['sp500_contribution'] > 0]
            positive_influences.sort(key=lambda x: x['sp500_contribution'], reverse=True)
            
            # Find missing influential stocks
            current_symbol_strings = set(str(symbol) for symbol in current_universe_symbols)
            missing_influencers = []
            
            for stock in positive_influences:
                stock_symbol = stock['symbol']
                if stock_symbol not in current_symbol_strings:
                    missing_influencers.append(stock)
            
            return {
                'top_influencers': positive_influences[:15],
                'missing_influencers': missing_influencers[:10],
                'spy_performance': spy_performance,
                'total_analyzed': len(influences)
            }
            
        except Exception as e:
            self.algorithm.log(f"Error in S&P 500 analysis: {str(e)}")
            return None
    
    def calculate_spy_performance(self, period_days):
        """Calculate SPY performance"""
        try:
            if self.spy_symbol is None:
                self.algorithm.log("SPY symbol not available for performance calculation")
                return None
            
            spy_history = self.algorithm.history(self.spy_symbol, period_days + 5, Resolution.DAILY)
            
            if not spy_history.empty and len(spy_history) >= period_days:
                start_price = spy_history.iloc[-period_days-1]['close']
                end_price = spy_history.iloc[-1]['close']
                performance = ((end_price / start_price) - 1) * 100
                
                return {
                    'performance': performance,
                    'period_days': period_days
                }
            else:
                self.algorithm.log(f"Insufficient SPY history data: {len(spy_history) if not spy_history.empty else 0} points available, need {period_days}")
        except Exception as e:
            self.algorithm.log(f"Error calculating SPY performance: {str(e)}")
        
        return None
    
    def calculate_stock_influence(self, symbol_str, stock_data, period_days):
        """Calculate individual stock's S&P 500 influence"""
        try:
            symbol = stock_data['symbol']
            weight = stock_data['weight']
            sector = stock_data['sector']
            
            # Get stock history
            stock_history = self.algorithm.history(symbol, period_days + 5, Resolution.DAILY)
            
            if not stock_history.empty and len(stock_history) >= period_days:
                start_price = stock_history.iloc[-period_days-1]['close']
                end_price = stock_history.iloc[-1]['close']
                performance = ((end_price / start_price) - 1) * 100
                
                # Calculate S&P 500 contribution
                sp500_contribution = (performance / 100) * (weight / 100) * 100
                
                return {
                    'symbol': symbol_str,
                    'sector': sector,
                    'weight': weight,
                    'performance': performance,
                    'sp500_contribution': sp500_contribution,
                    'market_cap': stock_data['market_cap']
                }
        except:
            pass
        
        return None
    
    def get_top_missing_sp500_stocks(self, current_universe_symbols, top_n=5, algorithm=None):
        """Get top N missing S&P 500 influential stocks with momentum filtering"""
        try:
            analysis = self.analyze_sp500_influence(current_universe_symbols)
            
            if analysis and analysis['missing_influencers']:
                top_missing = analysis['missing_influencers']
                
                # Filter by momentum if algorithm is provided
                momentum_filtered_stocks = []
                momentum_results = []
                
                for stock in top_missing:
                    try:
                        symbol = Symbol.create(stock['symbol'], SecurityType.EQUITY, Market.USA)

                            # Get momentum score
                            momentum_score = calculate_williams_alligator_momentum(algorithm, symbol, 30)
                            has_positive_momentum = momentum_score > 40  # Relaxed threshold
                            
                            # Store result for logging
                            momentum_results.append((stock['symbol'], momentum_score, has_positive_momentum))
                            
                            # Only include if positive momentum
                            if has_positive_momentum:
                                momentum_filtered_stocks.append(symbol)
                        else:
                            # No momentum filtering if no algorithm provided
                            momentum_filtered_stocks.append(symbol)
                            
                    except Exception as e:
                        continue
                
                # Log S&P 500 momentum summary
                if algorithm is not None and momentum_results:
                    log_momentum_summary(algorithm, momentum_results, "S&P 500")
                
                # Return top N momentum-filtered stocks
                return momentum_filtered_stocks[:top_n]
            
            return []
            
        except Exception as e:
            if algorithm:
                algorithm.log(f"Error in S&P 500 momentum filtering: {str(e)}")
            return []


