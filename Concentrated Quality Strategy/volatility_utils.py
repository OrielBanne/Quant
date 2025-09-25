"""
Volatility and Market Regime Detection Utilities
Contains functions for market regime detection and volatility-based position sizing
"""

from AlgorithmImports import *
import numpy as np
from utils import StrategyConfig

def detect_market_regime(algorithm, spy_symbol, lookback_days=20):
    """
    Detect current market regime to adjust strategy accordingly
    Returns: 'bull', 'bear', 'sideways', 'high_volatility'
    """
    try:
        # Get SPY history
        history = algorithm.history(spy_symbol, lookback_days, Resolution.DAILY)
        
        if history is None or history.empty or len(history) < lookback_days:
            return 'unknown'
        
        closes = history['close'].values
        
        # Calculate returns
        returns = np.diff(closes) / closes[:-1]
        
        # Calculate volatility (standard deviation of returns)
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        
        # Calculate trend (simple linear regression slope)
        x = np.arange(len(closes))
        slope = np.polyfit(x, closes, 1)[0]
        
        # Calculate trend strength
        trend_strength = slope / closes[0] * 252  # Annualized trend
        
        # Determine regime
        if volatility > 0.25:  # High volatility (>25% annualized)
            return 'high_volatility'
        elif trend_strength > 0.1:  # Strong uptrend (>10% annualized)
            return 'bull'
        elif trend_strength < -0.1:  # Strong downtrend (<-10% annualized)
            return 'bear'
        else:
            return 'sideways'
            
    except Exception as e:
        algorithm.log(f"Error detecting market regime: {str(e)}")
        return 'unknown'

def calculate_volatility_adjusted_position_size(algorithm, base_position_size, spy_symbol):
    """
    Adjust position size based on market volatility
    """
    try:
        market_regime = detect_market_regime(algorithm, spy_symbol)
        
        if market_regime == 'high_volatility':
            # Reduce position sizes during high volatility
            adjusted_size = base_position_size * StrategyConfig.HIGH_VOLATILITY_REDUCTION
            algorithm.log(f"High volatility detected - reducing position sizes by {StrategyConfig.HIGH_VOLATILITY_REDUCTION:.0%}")
        elif market_regime == 'bear':
            # Further reduce in bear markets
            adjusted_size = base_position_size * 0.3
            algorithm.log(f"Bear market detected - reducing position sizes to 30%")
        elif market_regime == 'sideways':
            # In sideways markets, maintain normal position sizes but force more rotation
            adjusted_size = base_position_size
            algorithm.log(f"Sideways market detected - maintaining position sizes but forcing rotation")
        else:
            adjusted_size = base_position_size
            
        return adjusted_size
        
    except Exception as e:
        algorithm.log(f"Error adjusting position size: {str(e)}")
        return base_position_size

def should_force_rotation(algorithm, spy_symbol):
    """
    Determine if we should force stock rotation based on market conditions
    """
    try:
        market_regime = detect_market_regime(algorithm, spy_symbol)
        
        # Force more aggressive rotation in sideways markets
        if market_regime == 'sideways':
            return True
        elif market_regime == 'high_volatility':
            return True  # Also rotate more in volatile markets
        else:
            return False
            
    except Exception as e:
        algorithm.log(f"Error checking rotation need: {str(e)}")
        return False
