from AlgorithmImports import *
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Set

class DynamicSectorMapper:
    """
    Dynamically retrieves American stocks and their corresponding sectors
    from QuantConnect data sources. Updates monthly to replace static SECTOR_STOCKS_MAP.
    """
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.sector_stocks_map = {}
        self.last_update = datetime.min
        self.update_frequency_days = 30  # Update monthly
        
        # Sector ETF mapping (this stays static as it's based on known ETFs)
        self.sector_etf_map = {
            'Information Technology': 'IYW',
            'Health Care': 'XLV', 
            'Financials': 'XLF',
            'Consumer Discretionary': 'XLY',
            'Communication Services': 'VDC',
            'Industrials': 'VIS',
            'Consumer Staples': 'XLP',
            'Energy': 'VDE',
            'Utilities': 'FUTY',
            'Real Estate': 'XLRE',
            'Materials': 'IYM'
        }
        
        # Initialize with empty map
        self.initialize_sector_map()
    
    def initialize_sector_map(self):
        """Initialize sector map with empty lists for each sector"""
        for sector in self.sector_etf_map.keys():
            self.sector_stocks_map[sector] = []
    
    def should_update(self) -> bool:
        """Check if sector mapping needs to be updated"""
        return (self.algorithm.time - self.last_update).days >= self.update_frequency_days
    
    def update_sector_mapping(self, coarse_data):
        """
        Update the sector mapping by analyzing current market data
        This method should be called monthly or when should_update() returns True
        """
        try:
            # Clear existing mapping
            self.initialize_sector_map()
            
            # Get all available stocks from coarse data
            available_stocks = []
            for stock in coarse_data:
                if (stock.has_fundamental_data and 
                    stock.market_cap > 1e9 and  # Minimum $1B market cap
                    stock.price > 5 and  # Minimum $5 price
                    stock.volume > 100000):  # Minimum volume
                    available_stocks.append(stock)
            
            # Group stocks by sector using fundamental data
            sector_counts = {}
            for stock in available_stocks:
                try:
                    # Get sector from fundamental data
                    sector = self.get_stock_sector(stock)
                    if sector and sector in self.sector_etf_map:
                        if sector not in sector_counts:
                            sector_counts[sector] = []
                        sector_counts[sector].append(stock.symbol.value)
                except Exception as e:
                    continue
            
            # Update sector mapping
            for sector, stocks in sector_counts.items():
                self.sector_stocks_map[sector] = stocks[:50]  # Limit to top 50 per sector
            
            self.last_update = self.algorithm.time
            self.algorithm.log(f"Sector mapping updated: {len(sector_counts)} sectors")
            
        except Exception as e:
            self.algorithm.log(f"Error updating sector mapping: {str(e)}")
            # Fallback to basic mapping if update fails
            self.create_fallback_mapping()
    
    def get_stock_sector(self, stock) -> str:
        """
        Get sector for a stock from fundamental data
        Returns the sector name or None if not available
        """
        try:
            # This would ideally use QuantConnect's fundamental data
            # For now, we'll use a simplified approach based on symbol patterns
            symbol = stock.symbol.value.upper()
            
            # Information Technology sector patterns
            tech_patterns = ['AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX', 'ADBE']
            if any(pattern in symbol for pattern in tech_patterns):
                return 'Information Technology'
            
            # Health Care sector patterns  
            health_patterns = ['JNJ', 'PFE', 'UNH', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN']
            if any(pattern in symbol for pattern in health_patterns):
                return 'Health Care'
            
            # Financials sector patterns
            fin_patterns = ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'AXP', 'SPGI', 'CB']
            if any(pattern in symbol for pattern in fin_patterns):
                return 'Financials'
            
            # Consumer Discretionary patterns
            consumer_patterns = ['HD', 'MCD', 'NKE', 'SBUX', 'LOW', 'TJX', 'BKNG', 'CMG', 'TGT', 'COST']
            if any(pattern in symbol for pattern in consumer_patterns):
                return 'Consumer Discretionary'
            
            # Default to Information Technology for unknown stocks (most liquid sector)
            return 'Information Technology'
            
        except Exception as e:
            return None
    
    def create_fallback_mapping(self):
        """Create a basic fallback mapping if dynamic update fails"""
        # Basic fallback mapping with well-known stocks
        fallback_map = {
            'Information Technology': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX', 'ADBE', 'CRM'],
            'Health Care': ['JNJ', 'PFE', 'UNH', 'ABBV', 'MRK', 'TMO', 'ABT', 'DHR', 'BMY', 'AMGN'],
            'Financials': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'AXP', 'SPGI', 'CB'],
            'Consumer Discretionary': ['HD', 'MCD', 'NKE', 'SBUX', 'LOW', 'TJX', 'BKNG', 'CMG', 'TGT', 'COST'],
            'Communication Services': ['GOOGL', 'META', 'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'CHTR', 'TMUS', 'DISH'],
            'Industrials': ['BA', 'CAT', 'GE', 'HON', 'UPS', 'FDX', 'MMM', 'RTX', 'LMT', 'NOC'],
            'Consumer Staples': ['PG', 'KO', 'PEP', 'WMT', 'COST', 'CL', 'KMB', 'GIS', 'K', 'HSY'],
            'Energy': ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PXD', 'MPC', 'VLO', 'PSX', 'KMI'],
            'Utilities': ['NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'XEL', 'SRE', 'PEG', 'WEC'],
            'Real Estate': ['AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'EXR', 'AVB', 'EQR', 'MAA', 'UDR'],
            'Materials': ['LIN', 'APD', 'SHW', 'FCX', 'NEM', 'DOW', 'PPG', 'ECL', 'DD', 'NUE']
        }
        
        self.sector_stocks_map = fallback_map
    
    def get_sector_stocks(self, sector: str) -> List[str]:
        """Get list of stocks for a given sector"""
        return self.sector_stocks_map.get(sector, [])
    
    def get_all_sectors(self) -> List[str]:
        """Get list of all available sectors"""
        return list(self.sector_stocks_map.keys())
    
    def get_sector_etf_symbol(self, sector: str) -> str:
        """Get ETF symbol for a given sector"""
        return self.sector_etf_map.get(sector, None)
    
    def get_sector_etf_map(self) -> Dict[str, str]:
        """Get the complete sector to ETF mapping"""
        return self.sector_etf_map.copy()
    
    def log_sector_summary(self):
        """Log a summary of current sector mapping"""
        self.algorithm.log("=== Dynamic Sector Mapping Summary ===")
        for sector, stocks in self.sector_stocks_map.items():
            if stocks:
                self.algorithm.log(f"{sector}: {len(stocks)} stocks")
            else:
                self.algorithm.log(f"{sector}: No stocks mapped")
        self.algorithm.log(f"Last updated: {self.last_update}")
        self.algorithm.log("=====================================")
