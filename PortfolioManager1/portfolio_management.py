# region imports
from AlgorithmImports import *
# endregion

# Your New Python File
"""
Portfolio Management Module
Handles position sizing, rebalancing, order execution, and portfolio monitoring
"""

from AlgorithmImports import *
from utils import StrategyConfig
from volatility_utils import calculate_volatility_adjusted_position_size

class PortfolioManager:
    """Manages portfolio operations and rebalancing"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.max_position_size = StrategyConfig.MAX_POSITION_SIZE
        self.universe_symbols = []
        self.need_rebalance = False
        self.rebalance_reason = ""
        self.last_rebalance_time = datetime.min
        self.rebalance_frequency = StrategyConfig.REBALANCE_FREQUENCY
    
    def trigger_rebalance(self, reason):
        """Trigger a rebalancing operation"""
        self.need_rebalance = True
        self.rebalance_reason = reason
        self.algorithm.log(f"==== Rebalancing triggered: {reason} ====")
    
    def should_rebalance(self):
        """Check if rebalancing is needed"""
        # Check if rebalancing was triggered
        if self.need_rebalance:
            return True
        
        # Check time-based rebalancing
        days_since_rebalance = (self.algorithm.time - self.last_rebalance_time).days
        if days_since_rebalance >= self.rebalance_frequency:
            self.trigger_rebalance(f"Time-based rebalancing ({days_since_rebalance} days)")
            return True
        
        return False
    
    def execute_rebalance(self, data):
        """Execute portfolio rebalancing"""
        try:
            if not self.universe_symbols:
                self.algorithm.log("No universe symbols available for rebalancing")
                self.reset_rebalance_flags()
                return
            
            # Check cash availability
            if self.algorithm.portfolio.cash <= 1000:
                self.algorithm.log(f"Low cash warning: ${self.algorithm.portfolio.cash:.2f}")
                self.reset_rebalance_flags()
                return
            
            base_weight_per_stock = min(1.0 / len(self.universe_symbols), self.max_position_size)
            
            # Adjust position sizes based on market volatility
            weight_per_stock = calculate_volatility_adjusted_position_size(self.algorithm, base_weight_per_stock, self.algorithm.spy)
            
            valid_symbols = []
            for symbol in self.universe_symbols:
                if (self.algorithm.securities.contains_key(symbol) and 
                    data.contains_key(symbol) and 
                    data[symbol].price > 0):
                    valid_symbols.append(symbol)
            
            if not valid_symbols:
                self.algorithm.log("No valid symbols for rebalancing")
                self.reset_rebalance_flags()
                return
            
            # Calculate target positions
            target_value_per_stock = self.algorithm.portfolio.total_portfolio_value * weight_per_stock
            
            # Execute orders
            orders_placed = 0
            for symbol in valid_symbols:
                try:
                    current_price = data[symbol].price
                    target_shares = int(target_value_per_stock / current_price)
                    
                    if target_shares > 0:
                        # Set stop loss for new positions
                        if not self.algorithm.portfolio[symbol].invested:
                            self.algorithm.risk_manager.set_stop_loss(symbol, current_price)
                        
                        # Place order
                        self.algorithm.set_holdings(symbol, weight_per_stock)
                        orders_placed += 1
                        
                except Exception as e:
                    self.algorithm.log(f"Error placing order for {symbol}: {str(e)}")
                    continue
            
            self.algorithm.log(f"Rebalancing completed: {orders_placed} orders placed")
            self.reset_rebalance_flags()
            
        except Exception as e:
            self.algorithm.log(f"Error in rebalancing: {str(e)}")
            self.reset_rebalance_flags()
    
    def reset_rebalance_flags(self):
        """Reset rebalancing flags"""
        self.need_rebalance = False
        self.rebalance_reason = ""
        self.last_rebalance_time = self.algorithm.time
    
    def update_universe(self, universe_symbols):
        """Update the universe symbols and trigger rebalancing if needed"""
        if universe_symbols != self.universe_symbols:
            self.universe_symbols = universe_symbols
            self.trigger_rebalance("Universe changed")
    
    def liquidate_all_positions(self, reason="Manual liquidation"):
        """Liquidate all positions except SPY"""
        liquidated_count = 0
        for symbol in list(self.algorithm.portfolio.keys()):
            if self.algorithm.portfolio[symbol].invested and symbol != self.algorithm.spy:
                self.algorithm.liquidate(symbol)
                liquidated_count += 1
        
        if liquidated_count > 0:
            self.algorithm.log(f"Liquidated {liquidated_count} positions: {reason}")
        
        return liquidated_count
    
    def get_portfolio_summary(self):
        """Get a summary of current portfolio state"""
        try:
            total_value = self.algorithm.portfolio.total_portfolio_value
            cash = self.algorithm.portfolio.cash
            invested_value = total_value - cash
            
            positions = []
            for symbol in self.algorithm.portfolio.keys():
                if self.algorithm.portfolio[symbol].invested:
                    position = self.algorithm.portfolio[symbol]
                    positions.append({
                        'symbol': symbol.value,
                        'quantity': position.quantity,
                        'value': position.holdings_value,
                        'weight': position.holdings_value / total_value if total_value > 0 else 0
                    })
            
            return {
                'total_value': total_value,
                'cash': cash,
                'invested_value': invested_value,
                'cash_percentage': cash / total_value if total_value > 0 else 1.0,
                'positions': positions,
                'position_count': len(positions)
            }
            
        except Exception as e:
            self.algorithm.log(f"Error getting portfolio summary: {str(e)}")
            return None
    
    def log_portfolio_status(self):
        """Log current portfolio status"""
        summary = self.get_portfolio_summary()
        if summary:
            self.algorithm.log(f"Portfolio: ${summary['total_value']:,.2f} "
                             f"({summary['position_count']} positions, "
                             f"{summary['cash_percentage']:.1%} cash)")
    
    def check_position_sizes(self):
        """Check if any positions exceed maximum size limits"""
        try:
            total_value = self.algorithm.portfolio.total_portfolio_value
            
            for symbol in self.algorithm.portfolio.keys():
                if self.algorithm.portfolio[symbol].invested:
                    position_value = self.algorithm.portfolio[symbol].holdings_value
                    position_weight = position_value / total_value if total_value > 0 else 0
                    
                    if position_weight > self.max_position_size * 1.1:  # 10% tolerance
                        self.algorithm.log(f"Warning: {symbol} position size {position_weight:.1%} exceeds limit")
                        
        except Exception as e:
            self.algorithm.log(f"Error checking position sizes: {str(e)}")
