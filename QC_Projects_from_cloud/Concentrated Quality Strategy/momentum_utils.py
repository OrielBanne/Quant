"""
Momentum Analysis Utilities
Contains Williams Alligator momentum calculation and filtering functions
"""

from AlgorithmImports import *
import numpy as np
import math

def calculate_williams_alligator_momentum(algorithm, symbol, lookback_days=30):
    """
    Calculate Williams Alligator momentum indicator (CORRECTED IMPLEMENTATION)
    Returns momentum score (0-100) based on alligator feeding pattern
    """
    try:
        # Get historical data
        history = algorithm.history(symbol, lookback_days + 20, Resolution.DAILY)
        
        if history is None or history.empty or len(history) < 30:
            return 50.0  # Neutral score if insufficient data
        
        # Get close prices
        closes = history['close'].values
        
        # Williams Alligator parameters
        jaw_period = 13
        teeth_period = 8
        lips_period = 5
        jaw_shift = 8
        teeth_shift = 5
        lips_shift = 3
        
        # Calculate Smoothed Moving Average (SMMA) - Williams method
        def calculate_smma(prices, period):
            """Calculate Smoothed Moving Average (SMMA)"""
            if len(prices) < period:
                return None
            
            # First SMMA is simple average
            smma_values = [np.mean(prices[:period])]
            
            # Calculate subsequent SMMA values
            for i in range(period, len(prices)):
                smma = (smma_values[-1] * (period - 1) + prices[i]) / period
                smma_values.append(smma)
            
            return smma_values
        
        # Calculate SMMA for each line
        jaw_smma = calculate_smma(closes, jaw_period)
        teeth_smma = calculate_smma(closes, teeth_period)
        lips_smma = calculate_smma(closes, lips_period)
        
        if not jaw_smma or not teeth_smma or not lips_smma:
            return 50.0
        
        # Apply forward shifts (critical for Williams Alligator)
        # Shift each line forward by its respective shift amount
        jaw_shifted = jaw_smma[-jaw_shift-1] if len(jaw_smma) > jaw_shift else jaw_smma[-1]
        teeth_shifted = teeth_smma[-teeth_shift-1] if len(teeth_smma) > teeth_shift else teeth_smma[-1]
        lips_shifted = lips_smma[-lips_shift-1] if len(lips_smma) > lips_shift else lips_smma[-1]
        
        current_price = closes[-1]
        
        # Check feeding pattern (bullish: Price > Lips > Teeth > Jaw)
        feeding_pattern = (current_price > lips_shifted > teeth_shifted > jaw_shifted)
        
        # Calculate momentum strength based on Williams Alligator states
        momentum_score = 50.0  # Base neutral score
        
        if feeding_pattern:
            # Alligator is feeding (bullish)
            momentum_score = 80.0
            
            # Check how far price is above the lips (feeding intensity)
            price_above_lips = (current_price - lips_shifted) / lips_shifted
            if price_above_lips > 0.05:  # 5% above lips
                momentum_score = 90.0
            elif price_above_lips > 0.02:  # 2% above lips
                momentum_score = 85.0
        else:
            # Check if alligator is sleeping (lines close together)
            line_spread = max(lips_shifted, teeth_shifted, jaw_shifted) - min(lips_shifted, teeth_shifted, jaw_shifted)
            avg_line = (lips_shifted + teeth_shifted + jaw_shifted) / 3
            spread_ratio = line_spread / avg_line if avg_line > 0 else 0
            
            if spread_ratio < 0.01:  # Lines very close (sleeping)
                momentum_score = 30.0
            elif current_price < jaw_shifted:  # Price below jaw (bearish)
                momentum_score = 20.0
            elif current_price < teeth_shifted:  # Price below teeth
                momentum_score = 35.0
            else:
                momentum_score = 45.0  # Neutral/sideways
        
        return max(0.0, min(100.0, momentum_score))
        
    except Exception as e:
        algorithm.log(f"Error calculating Williams Alligator for {symbol}: {str(e)}")
        return 50.0  # Neutral score on error

def check_positive_momentum(algorithm, stock_ticker, fine_data, momentum_results=None):
    """
    Check if stock has positive Williams Alligator momentum
    Returns True if momentum is positive, False otherwise
    """
    try:
        # Calculate momentum for this specific ticker
        momentum_score = calculate_williams_alligator_momentum(algorithm, fine_data.symbol, 30)
        
        # Only allow stocks with positive momentum (above 40 - relaxed threshold)
        has_positive_momentum = momentum_score > 40
        
        # Store result for summary logging
        if momentum_results is not None:
            momentum_results.append((stock_ticker, momentum_score, has_positive_momentum))
        
        return has_positive_momentum
        
    except Exception as e:
        algorithm.log(f"Error checking momentum for {stock_ticker}: {str(e)}")
        return False  # Exclude stock on error

def log_momentum_summary(algorithm, momentum_results, sector):
    """Log momentum check results in a concise format"""
    if not momentum_results:
        return
    
    # Create summary list
    summary_parts = [f"{sector} momentum:"]
    for ticker, score, passed in momentum_results:
        status = "✓" if passed else "✗"
        summary_parts.append(f"{ticker}/{score:.0f}/{status}")
    
    algorithm.log(" ".join(summary_parts))
