"""
Main Algorithm - Rising Sector Fundamental Universe
Simplified main algorithm using modular components
"""

from AlgorithmImports import *
from utils import StrategyConfig
from risk_management import RiskManager
from universe_selection import UniverseSelector
from portfolio_management import PortfolioManager

class RisingSectorFundamentalUniverse(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_cash(100000)

        self.set_benchmark("SPY")
        self.spy = self.add_equity("SPY", Resolution.DAILY).Symbol
        
        # Initialize managers
        self.risk_manager = RiskManager(self)
        self.universe_selector = UniverseSelector(self)
        self.portfolio_manager = PortfolioManager(self)
        
        # Initialize universe symbols
        self.universe_symbols = []
        
        # Schedules:
        self.schedule.on(self.date_rules.every_day(), self.time_rules.after_market_open(self.spy, 30), self.UpdateUniverse)
        self.schedule.on(self.date_rules.month_start(), self.time_rules.after_market_open(self.spy, 60), self.update_sector_filters)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.every(timedelta(hours=4)), self.check_stop_losses)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.every(timedelta(hours=4)), self.check_portfolio_stop_loss)
        
        self.add_universe(self.universe_selector.coarse_selection_function, self.universe_selector.fine_selection_function)
        
        # Warmup
        self.warmup_period = StrategyConfig.WARMUP_PERIOD
        self.is_warmed_up = False
        self.start_time = self.time
        
        self.warm_up_historical_data()
        
        # Initialize S&P 500 tracker
        self.universe_selector.sp500_tracker.initialize()
        self.universe_selector.analyze_missing_sp500_leaders()
        
        # Schedule monthly S&P 500 analysis
        self.schedule.on(self.date_rules.month_start(), 
                    self.time_rules.after_market_open(self.spy, 60), 
                    self.universe_selector.analyze_missing_sp500_leaders)

    def OnData(self, data):
        # Check if trading should be paused
        if self.risk_manager.should_pause_trading():
            if self.risk_manager.check_emergency_restart() or self.risk_manager.check_circuit_breaker_reset():
                self.portfolio_manager.trigger_rebalance("Risk management reset")
            return
        
        # Check for rebalancing
        if self.portfolio_manager.should_rebalance():
            self.portfolio_manager.execute_rebalance(data)
            return

    def UpdateUniverse(self):
        """Update universe and trigger rebalancing if needed"""
        try:
            # Update portfolio manager with new universe
            if hasattr(self, 'universe_symbols'):
                self.portfolio_manager.update_universe(self.universe_symbols)
            
            # Check for rebalancing
            if self.portfolio_manager.should_rebalance():
                # Get current data from the algorithm
                data = self.current_slice
                if data is not None:
                    self.portfolio_manager.execute_rebalance(data)
                
        except Exception as e:
            self.log(f"Error in UpdateUniverse: {str(e)}")

    def update_sector_filters(self):
        """Update sector-specific fundamental filters"""
        self.universe_selector.update_sector_filters()

    def check_stop_losses(self):
        """Check individual stock stop losses"""
        # Get current data from the algorithm
        data = self.current_slice
        if data is not None:
            self.risk_manager.check_stop_losses(data)

    def check_portfolio_stop_loss(self):
        """Check portfolio-level stop loss"""
        if self.risk_manager.check_portfolio_stop_loss():
            self.portfolio_manager.liquidate_all_positions("Portfolio stop loss triggered")

    def OnSecuritiesChanged(self, changes):
        """Handle universe changes"""
        try:
            # Update universe symbols
            self.universe_symbols = [security.symbol for security in changes.added_securities]
            
            # Update portfolio manager
            self.portfolio_manager.update_universe(self.universe_symbols)
            
            # Log universe changes
            if changes.added_securities:
                added_symbols = [s.symbol.value for s in changes.added_securities]
                self.log(f"Added to universe: {added_symbols}")
            
            if changes.removed_securities:
                removed_symbols = [s.symbol.value for s in changes.removed_securities]
                self.log(f"Removed from universe: {removed_symbols}")
                
        except Exception as e:
            self.log(f"Error in OnSecuritiesChanged: {str(e)}")

    def warm_up_historical_data(self):
        """Warm up historical data for better performance"""
        try:
            # Warm up SPY data
            self.history(self.spy, self.warmup_period, Resolution.DAILY)
            
            # Warm up sector ETF data
            for sector, etf_symbol in self.universe_selector.sector_etf_map.items():
                try:
                    self.history(etf_symbol, self.warmup_period, Resolution.DAILY)
                except Exception as e:
                    self.log(f"Error warming up {sector} ETF: {str(e)}")
            
            self.is_warmed_up = True
            self.log(f"Historical data warmed up for {self.warmup_period} days")
            
        except Exception as e:
            self.log(f"Error warming up historical data: {str(e)}")

    def OnEndOfDay(self):
        """End of day processing"""
        try:
            # Clean up blacklist
            self.risk_manager.clean_blacklist()
            
            # Check consecutive losses
            self.risk_manager.check_consecutive_losses()
            
            # Log portfolio status
            self.portfolio_manager.log_portfolio_status()
            
        except Exception as e:
            self.log(f"Error in OnEndOfDay: {str(e)}")
