
"""
Strategy Utilities for Rising Sector Fundamental Universe Algorithm
Contains configuration data, constants, and utility functions with normalized scoring
"""

from AlgorithmImports import *
import numpy as np
import math

# =============================================================================
# CONFIGURATION CONSTANTS
# =============================================================================

class StrategyConfig:
    """Centralized configuration for the strategy"""
    
    # Risk Parameters
    STOP_LOSS_PERCENTAGE = 0.05
    TRAILING_STOP_PERCENTAGE = 0.03
    PORTFOLIO_STOP_LOSS = 0.01
    MAX_POSITION_SIZE = 0.15
    
    # Universe Parameters
    NUM_STOCKS = 12
    NUM_SECTORS = 4
    LOOKBACK_DAYS = 60
    REBALANCE_FREQUENCY = 30
    
    # Filter Parameters
    MIN_MARKET_CAP = 1e9
    MIN_DOLLAR_VOLUME = 10e6
    MIN_PRICE = 5.0
    
    # Blacklist Parameters
    BLACKLIST_DURATION = 7
    RESTART_DELAY_DAYS = 1
    
    # Warmup Parameters
    WARMUP_PERIOD = 50
    
    # Filter Update Frequency
    FILTER_UPDATE_FREQUENCY = 90

# =============================================================================
# SECTOR CONFIGURATION DATA
# =============================================================================

# Sector ETF mapping with GICS names
# SECTOR_ETF_MAP = {   #SPDR ONLY
#     "Information Technology": "XLK",
#     "Communication Services": "XLC", 
#     "Consumer Discretionary": "XLY",
#     "Financials": "XLF",
#     "Health Care": "XLV",
#     "Industrials": "XLI",
#     "Consumer Staples": "XLP",
#     "Energy": "XLE",
#     "Materials": "XLB",
#     "Real Estate": "XLRE",
#     "Utilities": "XLU"
# }
SECTOR_ETF_MAP = {
    "Information Technology": "IYW",
    "Communication Services": "VDC", 
    "Consumer Discretionary": "XLY",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "VIS",
    "Consumer Staples": "XLP",
    "Energy": "VDE",
    "Materials": "IYM",
    "Real Estate": "XLRE",
    "Utilities": "FUTY"
}

# Default sector-specific fundamental filters
DEFAULT_SECTOR_FILTERS = {
    "Information Technology": {
        "pe_ratio_max": 100.0,
        "pe_ratio_min": 5.0,
        "pb_ratio_max": 50.0,
        "roe_min": 0.10,
        "roe_max": 0.60,
        "revenue_growth_min": 0.05,
        "debt_to_equity_max": 1.5,
        "min_quarterly_revenue": 500_000_000
    },
    "Communication Services": {
        "pe_ratio_max": 45.0,
        "pe_ratio_min": 8.0,
        "pb_ratio_max": 6.0,
        "roe_min": 0.12,
        "roe_max": 0.40,
        "revenue_growth_min": 0.03,
        "debt_to_equity_max": 1.5,
        "min_quarterly_revenue": 1_000_000_000
    },
    "Consumer Discretionary": {
        "pe_ratio_max": 100.0,
        "pe_ratio_min": 8.0,
        "pb_ratio_max": 50.0,
        "roe_min": 0.10,
        "roe_max": 0.40,
        "revenue_growth_min": 0.05,
        "debt_to_equity_max": 2.0,
        "min_quarterly_revenue": 1_000_000_000
    },
    "Financials": {
        "pe_ratio_max": 25.0,
        "pe_ratio_min": 5.0,
        "pb_ratio_max": 3.0,
        "roe_min": 0.06,
        "roe_max": 0.30,
        "revenue_growth_min": 0.02,
        "debt_to_equity_max": 5.0,
        "min_quarterly_revenue": 500_000_000
    },
    "Health Care": {
        "pe_ratio_max": 25.0,
        "pe_ratio_min": 8.0,
        "pb_ratio_max": 5.0,
        "roe_min": 0.12,
        "roe_max": 0.40,
        "revenue_growth_min": 0.04,
        "debt_to_equity_max": 1.2,
        "min_quarterly_revenue": 500_000_000 
    },
    "Industrials": {
        "pe_ratio_max": 25.0,
        "pe_ratio_min": 8.0,
        "pb_ratio_max": 4.0,
        "roe_min": 0.10,
        "roe_max": 0.40,
        "revenue_growth_min": 0.03,
        "debt_to_equity_max": 1.5,
        "min_quarterly_revenue": 500_000_000
    },
    "Consumer Staples": {
        "pe_ratio_max": 22.0,
        "pe_ratio_min": 10.0,
        "pb_ratio_max": 15.0,
        "roe_min": 0.12,
        "roe_max": 0.40,
        "revenue_growth_min": 0.02,
        "debt_to_equity_max": 1.0,
        "min_quarterly_revenue": 1_000_000_000
    },
    "Energy": {
        "pe_ratio_max": 20.0,
        "pe_ratio_min": 5.0,
        "pb_ratio_max": 3.0,
        "roe_min": 0.08,
        "roe_max": 0.40,
        "revenue_growth_min": 0.00, 
        "debt_to_equity_max": 1.8,
        "min_quarterly_revenue": 500_000_000 
    },
    "Materials": {
        "pe_ratio_max": 20.0,
        "pe_ratio_min": 5.0,
        "pb_ratio_max": 3.0,
        "roe_min": 0.08,
        "roe_max": 0.40,
        "revenue_growth_min": 0.02,
        "debt_to_equity_max": 1.5,
        "min_quarterly_revenue": 500_000_000
    },
    "Real Estate": {
        "pe_ratio_max": 30.0,  # REITs often have higher P/E
        "pe_ratio_min": 8.0,
        "pb_ratio_max": 2.0,
        "roe_min": 0.06,
        "roe_max": 0.40,
        "revenue_growth_min": 0.02,
        "debt_to_equity_max": 3.0,
        "min_quarterly_revenue": 200_000_000
    },
    "Utilities": {
        "pe_ratio_max": 18.0,
        "pe_ratio_min": 10.0,
        "pb_ratio_max": 2.5,
        "roe_min": 0.08,
        "roe_max": 0.40,
        "revenue_growth_min": 0.01,
        "debt_to_equity_max": 2.0,
        "min_quarterly_revenue": 500_000_000
    }
}

# Sector stocks mapping with major stocks per sector
# SECTOR_STOCKS_MAP = {
#     "Information Technology": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "AMD", "INTC"],
#     "Communication Services": ["GOOG", "GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR"],
#     "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
#     "Financials": ["BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "AXP"],
#     "Health Care": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "PFE", "TMO", "ABT", "DHR", "BMY"],
#     "Industrials": ["CAT", "GE", "HON", "UPS", "FDX", "MMM", "RTX", "LMT", "DE", "BA"],
#     "Consumer Staples": ["WMT", "PG", "COST", "KO", "PEP", "CL", "KMB", "GIS", "K", "CPB"],
#     "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "PXD", "KMI", "WMB", "MPC", "VLO"],
#     "Materials": ["LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF"],
#     "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "EXR", "AVB", "EQR", "MAA", "SPG"],
#     "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "WEC"]
# }
SECTOR_STOCKS_MAP = {
    "Information Technology": ["MSFT", "AAPL", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "CSCO", "AMD", "INTC"],
    "Communication Services": ["GOOG", "GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "TMUS", "CHTR"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
    "Financials": ["BRK.B", "JPM", "V", "MA", "BAC", "WFC"],
    "Health Care": ["LLY", "UNH", "JNJ", "MRK", "ABBV", "TMO", "ABT", "DHR"],
    "Consumer Staples": ["WMT", "PG", "COST", "KO", "PEP", "CL", "KMB", "GIS", "K", "CPB"],
    "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "PXD", "KMI", "WMB", "MPC", "VLO"],
    "Materials": ["LIN", "APD", "SHW", "FCX", "NEM", "DOW", "DD", "PPG", "ECL", "IFF"],
    "Real Estate": ["AMT", "PLD", "CCI","PSA", "EXR", "AVB", "EQR", "MAA", "SPG"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "SRE", "PEG", "WEC"]
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def passes_fundamental_filters(stock_fine_data, sector_filter, stock_ticker=None, algorithm=None):
    """Check if stock passes fundamental filters"""
    try:
        # PE Ratio check
        pe_ratio = stock_fine_data.valuation_ratios.pe_ratio
        if pe_ratio <= 0 or pe_ratio < sector_filter['pe_ratio_min'] or pe_ratio > sector_filter['pe_ratio_max']:
            if stock_ticker == "NVDA" and algorithm:
                algorithm.log(f"NVDA filtered: PE={pe_ratio}, min={sector_filter['pe_ratio_min']}, max={sector_filter['pe_ratio_max']}")
            return False
        
        # PB Ratio check
        pb_ratio = stock_fine_data.valuation_ratios.pb_ratio
        if pb_ratio <= 0 or pb_ratio > sector_filter['pb_ratio_max']:
            if stock_ticker == "NVDA" and algorithm:
                algorithm.log(f"NVDA filtered: PB={pb_ratio}, max={sector_filter['pb_ratio_max']}")
            return False
        
        # ROE check
        roe = stock_fine_data.operation_ratios.roe.one_year
        if roe <= 0 or roe < sector_filter['roe_min']:
            if stock_ticker == "NVDA" and algorithm:
                algorithm.log(f"NVDA filtered: ROE={roe}, min={sector_filter['roe_min']}")
            return False
        
        # Revenue check
        revenue = stock_fine_data.financial_statements.income_statement.total_revenue.three_months
        min_revenue = sector_filter['min_quarterly_revenue']
        if revenue <= 0 or revenue < min_revenue:
            if stock_ticker == "NVDA" and algorithm:
                algorithm.log(f"NVDA filtered: Revenue={revenue}, min={min_revenue}")
            return False
        
        # Debt to Equity check (optional - only if data is available)
        try:
            debt_to_equity = None
            if hasattr(stock_fine_data.operation_ratios, 'debt_to_equity'):
                debt_to_equity = stock_fine_data.operation_ratios.debt_to_equity.one_year
            elif hasattr(stock_fine_data.operation_ratios, 'total_debt_to_equity'):
                debt_to_equity = stock_fine_data.operation_ratios.total_debt_to_equity.one_year
            elif hasattr(stock_fine_data.operation_ratios, 'debt_to_equity_ratio'):
                debt_to_equity = stock_fine_data.operation_ratios.debt_to_equity_ratio.one_year
            
            if debt_to_equity is not None and debt_to_equity > sector_filter['debt_to_equity_max']:
                if stock_ticker == "NVDA" and algorithm:
                    algorithm.log(f"NVDA filtered: Debt/Equity={debt_to_equity}, max={sector_filter['debt_to_equity_max']}")
                return False
        except:
            pass  # Skip if data not available
        
        if stock_ticker == "NVDA" and algorithm:
            algorithm.log(f"NVDA PASSED all fundamental filters!")
        
        return True
        
    except Exception as e:
        if stock_ticker == "NVDA" and algorithm:
            algorithm.log(f"NVDA filtered: Exception={str(e)}")
        return False

def normalize_score(score, min_score, max_score):
    """Normalize score to 0-1 range"""
    if max_score == min_score:
        return 0.5  # Return middle value if no variation
    return (score - min_score) / (max_score - min_score)

# =============================================================================
# NATURAL BUSINESS RANGES FOR NORMALIZATION
# =============================================================================

# Define natural ranges based on business fundamentals
NATURAL_RANGES = {
    "roe": {
        "min": 0.05,      # 5% - minimum acceptable ROE
        "good": 0.15,     # 15% - good ROE
        "excellent": 0.25, # 25% - excellent ROE
        "max": 0.50       # 50% - maximum realistic sustainable ROE
    },
    "pe_ratio": {
        "min": 5.0,       # 5 - very cheap
        "good": 15.0,     # 15 - fair value
        "expensive": 25.0, # 25 - getting expensive
        "max": 50.0       # 50 - very expensive
    },
    "pb_ratio": {
        "min": 0.5,       # 0.5 - very cheap
        "good": 1.5,      # 1.5 - fair value
        "expensive": 3.0,  # 3.0 - expensive
        "max": 10.0       # 10.0 - very expensive
    },
    "revenue_growth": {
        "min": -0.10,     # -10% - declining
        "good": 0.05,     # 5% - steady growth
        "excellent": 0.15, # 15% - strong growth
        "max": 0.50       # 50% - exceptional growth
    },
    "debt_to_equity": {
        "min": 0.0,       # 0 - no debt
        "good": 0.3,      # 30% - healthy debt
        "high": 1.0,      # 100% - high debt
        "max": 3.0        # 300% - very high debt
    }
}

# Sector-specific adjustments to natural ranges
SECTOR_ADJUSTMENTS = {
    "Information Technology": {
        "pe_ratio": {"good": 20.0, "expensive": 35.0, "max": 80.0},  # Tech can have higher P/E
        "roe": {"excellent": 0.30, "max": 0.60},  # Tech can have higher ROE
        "debt_to_equity": {"good": 0.2, "high": 0.5, "max": 1.0}  # Tech typically low debt
    },
    "Financials": {
        "debt_to_equity": {"good": 2.0, "high": 5.0, "max": 10.0},  # Banks use leverage
        "pb_ratio": {"good": 1.0, "expensive": 2.0, "max": 4.0},  # Banks trade closer to book
        "roe": {"good": 0.10, "excellent": 0.18, "max": 0.30}  # Banks have different ROE profile
    },
    "Utilities": {
        "pe_ratio": {"good": 12.0, "expensive": 18.0, "max": 25.0},  # Utilities lower P/E
        "revenue_growth": {"good": 0.02, "excellent": 0.05, "max": 0.15},  # Utilities slower growth
        "debt_to_equity": {"good": 0.8, "high": 1.5, "max": 3.0}  # Utilities use more debt
    },
    "Real Estate": {
        "debt_to_equity": {"good": 1.5, "high": 3.0, "max": 5.0},  # REITs use leverage
        "pe_ratio": {"good": 18.0, "expensive": 30.0, "max": 50.0},  # REITs different P/E
        "roe": {"good": 0.08, "excellent": 0.15, "max": 0.25}  # REITs different ROE
    },
    "Energy": {
        "pe_ratio": {"good": 12.0, "expensive": 20.0, "max": 35.0},  # Energy cyclical
        "revenue_growth": {"min": -0.20, "good": 0.00, "excellent": 0.10, "max": 0.30}  # Energy volatile
    }
}

def sigmoid_normalize(value, ranges, invert=False):
    """
    Normalize value using sigmoid function based on natural ranges
    Returns score from 0-100
    
    Args:
        value: The value to normalize
        ranges: Dict with 'min', 'good', 'excellent', 'max' keys
        invert: True for metrics where lower is better (P/E, P/B, Debt)
    """
    if value is None or math.isnan(value):
        return 50.0  # Neutral score for missing data
    
    # Clamp extreme values
    value = max(ranges['min'], min(ranges['max'], value))
    
    if invert:
        # For metrics where lower is better (P/E, P/B, Debt)
        if value <= ranges['good']:
            # Excellent to good range: 100 to 80
            ratio = (ranges['good'] - value) / (ranges['good'] - ranges['min'])
            score = 80 + (ratio * 20)
        else:
            # Good to max range: 80 to 0
            ratio = (value - ranges['good']) / (ranges['max'] - ranges['good'])
            # Use sigmoid for smooth transition
            sigmoid_ratio = 1 / (1 + math.exp(-6 * (ratio - 0.5)))
            score = 80 * (1 - sigmoid_ratio)
    else:
        # For metrics where higher is better (ROE, Growth)
        if value >= ranges['excellent']:
            # Excellent to max range: 90 to 100
            ratio = min(1.0, (value - ranges['excellent']) / (ranges['max'] - ranges['excellent']))
            score = 90 + (ratio * 10)
        elif value >= ranges['good']:
            # Good to excellent range: 70 to 90
            ratio = (value - ranges['good']) / (ranges['excellent'] - ranges['good'])
            score = 70 + (ratio * 20)
        else:
            # Min to good range: 0 to 70
            ratio = (value - ranges['min']) / (ranges['good'] - ranges['min'])
            # Use sigmoid for smooth transition
            sigmoid_ratio = 1 / (1 + math.exp(-6 * (ratio - 0.5)))
            score = 70 * sigmoid_ratio
    
    return max(0.0, min(100.0, score))

def get_sector_adjusted_ranges(metric, sector):
    """Get sector-adjusted ranges for a metric"""
    base_range = NATURAL_RANGES[metric].copy()
    
    if sector in SECTOR_ADJUSTMENTS and metric in SECTOR_ADJUSTMENTS[sector]:
        # Update with sector-specific values
        base_range.update(SECTOR_ADJUSTMENTS[sector][metric])
    
    return base_range

def calculate_fundamental_score(stock_data, sector):
    """
    Calculate fundamental score using natural normalization
    Returns score from 0-100 where higher is better
    """
    ticker, fine_data, pe_ratio, roe = stock_data
    
    try:
        # Apply ROE max filter first
        if roe <= 0:
            return 0.0
        elif roe > DEFAULT_SECTOR_FILTERS[sector]["roe_max"]:
            roe = DEFAULT_SECTOR_FILTERS[sector]["roe_max"]
        
        # Get all metrics
        pb_ratio = fine_data.valuation_ratios.pb_ratio
        revenue_growth = fine_data.operation_ratios.revenue_growth.one_year
        
        # Try to get debt-to-equity ratio if available
        debt_to_equity = None
        try:
            # Try different possible attribute names
            if hasattr(fine_data.operation_ratios, 'debt_to_equity'):
                debt_to_equity = fine_data.operation_ratios.debt_to_equity.one_year
            elif hasattr(fine_data.operation_ratios, 'total_debt_to_equity'):
                debt_to_equity = fine_data.operation_ratios.total_debt_to_equity.one_year
            elif hasattr(fine_data.operation_ratios, 'debt_to_equity_ratio'):
                debt_to_equity = fine_data.operation_ratios.debt_to_equity_ratio.one_year
        except:
            debt_to_equity = None
        
        # Apply additional filters
        if pb_ratio <= 0:
            return 0.0
        
        # Calculate normalized scores for each metric
        roe_score = sigmoid_normalize(roe, get_sector_adjusted_ranges("roe", sector), invert=False)
        pe_score = sigmoid_normalize(pe_ratio, get_sector_adjusted_ranges("pe_ratio", sector), invert=True)
        pb_score = sigmoid_normalize(pb_ratio, get_sector_adjusted_ranges("pb_ratio", sector), invert=True)
        
        growth_score = 50.0  # Default neutral
        if revenue_growth is not None:
            growth_score = sigmoid_normalize(revenue_growth, get_sector_adjusted_ranges("revenue_growth", sector), invert=False)
        
        debt_score = 70.0  # Default good score (assume reasonable debt if missing)
        if debt_to_equity is not None:
            debt_score = sigmoid_normalize(debt_to_equity, get_sector_adjusted_ranges("debt_to_equity", sector), invert=True)
        
        # Sector-specific weighting
        if sector == "Information Technology":
            # Tech: Focus on growth and profitability
            final_score = (
                roe_score * 0.35 +      # Profitability: 35%
                growth_score * 0.25 +   # Growth: 25%
                pe_score * 0.20 +       # Valuation: 20%
                pb_score * 0.10 +       # Book value: 10%
                debt_score * 0.10       # Financial health: 10%
            )
        elif sector == "Financials":
            # Financials: Focus on valuation and profitability
            final_score = (
                roe_score * 0.40 +      # Profitability: 40%
                pe_score * 0.25 +       # Valuation: 25%
                pb_score * 0.25 +       # Book value: 25%
                growth_score * 0.10     # Growth: 10%
                # Debt less important for banks
            )
        elif sector == "Utilities":
            # Utilities: Focus on stability and reasonable valuation
            final_score = (
                roe_score * 0.30 +      # Profitability: 30%
                pe_score * 0.25 +       # Valuation: 25%
                debt_score * 0.25 +     # Financial health: 25%
                pb_score * 0.20         # Book value: 20%
                # Growth less important: 0%
            )
        elif sector == "Energy":
            # Energy: Focus on financial health during cycles
            final_score = (
                roe_score * 0.25 +      # Profitability: 25%
                pe_score * 0.25 +       # Valuation: 25%
                debt_score * 0.25 +     # Financial health: 25%
                pb_score * 0.15 +       # Book value: 15%
                growth_score * 0.10     # Growth: 10%
            )
        else:
            # Default weighting for other sectors
            final_score = (
                roe_score * 0.30 +      # Profitability: 30%
                pe_score * 0.25 +       # Valuation: 25%
                growth_score * 0.20 +   # Growth: 20%
                pb_score * 0.15 +       # Book value: 15%
                debt_score * 0.10       # Financial health: 10%
            )
        
        return max(0.0, min(100.0, final_score))
        
    except Exception as e:
        return 0.0

def normalize_scores_across_sector(stocks_with_scores):
    """Normalize scores within a sector for fair comparison"""
    if not stocks_with_scores:
        return stocks_with_scores
    
    scores = [score for _, _, score in stocks_with_scores]
    min_score = min(scores)
    max_score = max(scores)
    
    # Normalize scores to 0-1 range
    normalized_stocks = []
    for ticker, fine_data, score in stocks_with_scores:
        normalized_score = normalize_score(score, min_score, max_score)
        normalized_stocks.append((ticker, fine_data, normalized_score))
    
    return normalized_stocks

def build_final_universe(algorithm, sector_filtered_stocks, num_stocks):
    """Build final universe from filtered stocks with natural normalization scoring"""
    all_stocks = []
    
    # Collect all stocks that passed filters
    for sector, stocks in sector_filtered_stocks.items():
        if stocks:
            all_stocks.extend(stocks)
    
    if not all_stocks:
        algorithm.log("No stocks passed sector-specific fundamental filters")
        return []
        
    # The stocks are already scored, so we just need to sort them
    scored_stocks = all_stocks  # all_stocks already contains (ticker, fine_data, score)
                
    if not scored_stocks:
        algorithm.log("No stocks could be scored")
        return []
    
    # Sort by score and take top stocks
    scored_stocks.sort(key=lambda x: x[2], reverse=True)
    top_stocks = scored_stocks[:num_stocks]
    
    final_universe = []
    msgs = ["Final universe scores:",]
    
    for stock_ticker, fine_data, score in top_stocks:
        try:
            # symbol = Symbol.create(stock_ticker, SecurityType.EQUITY, Market.USA)
            symbol = fine_data.symbol
            final_universe.append(symbol)
            msgs.append(f" {stock_ticker}: {score:.1f}")
        except Exception as e:
            algorithm.log(f"Could not create symbol for {stock_ticker} : {str(e)}")
            continue

    algorithm.log(" ".join(msgs))
    
    if not final_universe:
        algorithm.log("Warning: No stocks selected, returning unchanged universe")
        return Universe.UNCHANGED
    
    return final_universe
    
# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_sector_etf_symbols(algorithm):
    """Get sector ETF symbols for the algorithm"""
    sector_etf_symbols = {}
    for sector, etf_ticker in SECTOR_ETF_MAP.items():
        try:
            symbol = algorithm.add_equity(etf_ticker, Resolution.DAILY).symbol
            sector_etf_symbols[sector] = symbol
        except Exception as e:
            algorithm.log(f"Error adding ETF {etf_ticker} for sector {sector}: {str(e)}")
    
    return sector_etf_symbols

def log_sector_performance(algorithm, sector_returns, num_sectors):
    """Log sector performance information"""
    # sorted_sectors = sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)
    # Only consider sectors that have stocks available
    available_sectors = set(SECTOR_ETF_MAP.keys()) & set(SECTOR_STOCKS_MAP.keys())
    filtered_returns = {sector: ret for sector, ret in sector_returns.items() if sector in available_sectors}
    
    # Log all sector returns for debugging
    # algorithm.log("=== ALL SECTOR RETURNS ===")
    all_sorted = sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)

    # First determine which sectors will actually be selected
    sorted_sectors = sorted(filtered_returns.items(), key=lambda x: x[1], reverse=True)
    rising_sectors = [sector for sector, _ in sorted_sectors[:num_sectors]]

    for sector, ret in all_sorted:
        status = "✓" if sector in available_sectors else "✗ (no stocks)"
        # Add blue checkmark for actually selected sectors
        if sector in rising_sectors:
            selected_mark = " ✓"  # Blue checkmark for selected
        else:
            selected_mark = ""
        # algorithm.log(f"  {sector}: {ret:.2%} {status}{selected_mark}")
    # algorithm.log("==========================")

    
    algorithm.log(f"Selected rising sectors: {rising_sectors}")
    for sector, ret in sorted_sectors[:num_sectors]:
        algorithm.log(f"  {sector}: {ret:.2%}")
    
    return rising_sectors

def log_filter_status(algorithm, sector_filters, selected_sectors):
    """Log current filter status"""
    algorithm.log("=== CURRENT SECTOR FILTER STATUS ===")
    for sector, filters in sector_filters.items():
        if sector in selected_sectors:
            algorithm.log(f"  {sector}:")
            algorithm.log(f"    P/E: {filters['pe_ratio_min']:.1f} - {filters['pe_ratio_max']:.1f}")
            algorithm.log(f"    ROE: {filters['roe_min']:.1%} - {filters['roe_max']:.1%}")
            algorithm.log(f"    P/B: max {filters['pb_ratio_max']:.1f}")
            algorithm.log(f"    Revenue: min ${filters['min_quarterly_revenue']:,.0f}")
            algorithm.log(f"    Debt/Equity: max {filters['debt_to_equity_max']:.1f}")
    algorithm.log("=====================================")
