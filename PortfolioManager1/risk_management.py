"""
Risk Management Module
Handles stop losses, circuit breakers, blacklisting, and emergency liquidation
"""

from AlgorithmImports import *
from utils import StrategyConfig
from volatility_utils import detect_market_regime

class RiskManager:
    """Manages all risk-related functionality"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        
        # Stop loss tracking
        self.stop_loss_prices = {}
        self.trailing_stop_prices = {}
        self.highest_prices = {}
        
        # Portfolio tracking
        self.highest_portfolio_value = algorithm.portfolio.total_portfolio_value
        self.emergency_liquidation = False
        self.emergency_liquidation_date = None
        self.restart_delay_days = StrategyConfig.RESTART_DELAY_DAYS
        
        # Circuit breaker protection
        self.consecutive_losses = 0
        self.circuit_breaker_active = False
        self.circuit_breaker_date = None
        self.last_portfolio_value = 0
        
        # Blacklist management
        self.blacklisted_stocks = set()
        self.blacklist_duration = StrategyConfig.BLACKLIST_DURATION
        self.stock_blacklist_dates = {}
    
    def check_consecutive_losses(self):
        """Check for consecutive losses and trigger circuit breaker if needed"""
        try:
            current_value = self.algorithm.portfolio.total_portfolio_value
            
            if self.last_portfolio_value > 0:
                daily_return = (current_value - self.last_portfolio_value) / self.last_portfolio_value
                
                if daily_return < -0.01:  # Loss > 1%
                    self.consecutive_losses += 1
                    self.algorithm.log(f"Consecutive loss #{self.consecutive_losses}: {daily_return:.2%}")
                    
                    if self.consecutive_losses >= StrategyConfig.MAX_CONSECUTIVE_LOSSES:
                        self.trigger_circuit_breaker()
                else:
                    # Reset consecutive losses on positive or small negative day
                    if self.consecutive_losses > 0:
                        self.algorithm.log(f"Consecutive losses reset (return: {daily_return:.2%})")
                    self.consecutive_losses = 0
            
            self.last_portfolio_value = current_value
            
        except Exception as e:
            self.algorithm.log(f"Error checking consecutive losses: {str(e)}")
    
    def trigger_circuit_breaker(self):
        """Trigger circuit breaker to pause trading"""
        self.circuit_breaker_active = True
        self.circuit_breaker_date = self.algorithm.time
        self.consecutive_losses = 0
        
        # Liquidate all positions
        self.algorithm.liquidate()
        
        self.algorithm.log(f" CIRCUIT BREAKER TRIGGERED  - Pausing trading for {StrategyConfig.CIRCUIT_BREAKER_PAUSE_DAYS} days")
    
    def check_circuit_breaker_reset(self):
        """Check if circuit breaker should be reset"""
        if not self.circuit_breaker_active:
            return
        
        days_paused = (self.algorithm.time - self.circuit_breaker_date).days
        
        if days_paused >= StrategyConfig.CIRCUIT_BREAKER_PAUSE_DAYS:
            self.circuit_breaker_active = False
            self.circuit_breaker_date = None
            self.consecutive_losses = 0
            
            self.algorithm.log(f"Circuit breaker reset - resuming trading after {days_paused} days")
            return True  # Signal that rebalancing should be triggered
        
        return False
    
    def check_emergency_restart(self):
        """Check if emergency liquidation period has ended"""
        if not self.emergency_liquidation:
            return
        
        days_since_liquidation = (self.algorithm.time - self.emergency_liquidation_date).days
        
        if days_since_liquidation >= self.restart_delay_days:
            self.emergency_liquidation = False
            self.emergency_liquidation_date = None
            self.algorithm.log("Emergency liquidation period ended - resuming normal operations")
            return True  # Signal that rebalancing should be triggered
        
        return False
    
    def trigger_emergency_liquidation(self, reason):
        """Trigger emergency liquidation of all positions"""
        self.emergency_liquidation = True
        self.emergency_liquidation_date = self.algorithm.time
        
        # Liquidate all positions except SPY
        for symbol in list(self.algorithm.portfolio.keys()):
            if self.algorithm.portfolio[symbol].invested and symbol != self.algorithm.spy:
                current_price = self.algorithm.securities[symbol].price
                self.algorithm.liquidate(symbol)
                self.algorithm.log(f"Emergency liquidated: {symbol} at ${current_price:.2f}")
        
        self.algorithm.log(f" EMERGENCY LIQUIDATION TRIGGERED: {reason} ")
    
    def check_portfolio_stop_loss(self):
        """Check if portfolio has hit stop loss threshold"""
        try:
            current_value = self.algorithm.portfolio.total_portfolio_value
            
            if current_value > self.highest_portfolio_value:
                self.highest_portfolio_value = current_value
            
            # Check if portfolio has dropped below stop loss threshold
            if self.highest_portfolio_value > 0:
                drawdown = (self.highest_portfolio_value - current_value) / self.highest_portfolio_value
                
                if drawdown >= StrategyConfig.PORTFOLIO_STOP_LOSS:
                    self.trigger_emergency_liquidation(f"Portfolio stop loss triggered: {drawdown:.2%} drawdown")
                    return True
            
            return False
            
        except Exception as e:
            self.algorithm.log(f"Error checking portfolio stop loss: {str(e)}")
            return False
    
    def check_stop_losses(self, data):
        """Check individual stock stop losses"""
        try:
            for symbol in list(self.algorithm.portfolio.keys()):
                if not self.algorithm.portfolio[symbol].invested or symbol == self.algorithm.spy:
                    continue
                
                if not data.contains_key(symbol):
                    continue
                
                # Check if data[symbol] is not None
                symbol_data = data[symbol]
                if symbol_data is None:
                    continue
                
                current_price = symbol_data.price
                
                # Update highest price for trailing stop
                if symbol not in self.highest_prices or current_price > self.highest_prices[symbol]:
                    self.highest_prices[symbol] = current_price
                
                # Check regular stop loss
                if symbol in self.stop_loss_prices and current_price <= self.stop_loss_prices[symbol]:
                    self.algorithm.liquidate(symbol)
                    self.algorithm.log(f"Stop loss triggered for {symbol} at ${current_price:.2f}")
                    self.blacklist_stock(symbol)
                    continue
                
                # Check trailing stop loss
                if symbol in self.highest_prices:
                    trailing_stop_price = self.highest_prices[symbol] * (1 - StrategyConfig.TRAILING_STOP_PERCENTAGE)
                    
                    if current_price <= trailing_stop_price:
                        self.algorithm.liquidate(symbol)
                        self.algorithm.log(f"Trailing stop triggered for {symbol} at ${current_price:.2f}")
                        self.blacklist_stock(symbol)
                        continue
                
        except Exception as e:
            self.algorithm.log(f"Error checking stop losses: {str(e)}")
    
    def set_stop_loss(self, symbol, entry_price):
        """Set stop loss price for a symbol"""
        stop_loss_price = entry_price * (1 - StrategyConfig.STOP_LOSS_PERCENTAGE)
        self.stop_loss_prices[symbol] = stop_loss_price
    
    def blacklist_stock(self, symbol):
        """Add stock to blacklist"""
        self.blacklisted_stocks.add(symbol)
        self.stock_blacklist_dates[symbol] = self.algorithm.time
        self.algorithm.log(f"Blacklisted {symbol} for {self.blacklist_duration} days")
    
    def clean_blacklist(self):
        """Remove expired stocks from blacklist"""
        current_time = self.algorithm.time
        symbols_to_remove = []
        
        for symbol, blacklist_date in self.stock_blacklist_dates.items():
            days_blacklisted = (current_time - blacklist_date).days
            if days_blacklisted >= self.blacklist_duration:
                symbols_to_remove.append(symbol)
        
        for symbol in symbols_to_remove:
            self.blacklisted_stocks.discard(symbol)
            del self.stock_blacklist_dates[symbol]
            # Clean up tracking dictionaries
            if symbol in self.highest_prices:
                del self.highest_prices[symbol]
    
    def is_blacklisted(self, symbol):
        """Check if symbol is blacklisted"""
        return symbol in self.blacklisted_stocks
    
    def should_pause_trading(self):
        """Check if trading should be paused due to risk management"""
        return self.emergency_liquidation or self.circuit_breaker_active
