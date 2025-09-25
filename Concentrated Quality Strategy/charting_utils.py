from AlgorithmImports import *
import pandas as pd
import numpy as np
from datetime import datetime

class ChartingManager:
    """
    Manages charting functionality including benchmark drawdown and normalized equity comparison
    """
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.equity_history = []
        self.benchmark_history = []
        self.dates = []
        self.initial_equity = None
        self.initial_benchmark = None
        
        # Initialize charts
        self.setup_charts()
    
    def setup_charts(self):
        """Setup initial charts"""
        # Create equity vs benchmark chart
        self.equity_chart = Chart("Equity vs Benchmark")
        self.strategy_series = Series("Strategy", SeriesType.LINE, 0)
        self.benchmark_series = Series("Benchmark", SeriesType.LINE, 1)
        self.equity_chart.add_series(self.strategy_series)
        self.equity_chart.add_series(self.benchmark_series)
        self.algorithm.AddChart(self.equity_chart)
        
        # Create drawdown chart
        self.drawdown_chart = Chart("Drawdown Analysis")
        self.strategy_drawdown_series = Series("Strategy Drawdown", SeriesType.LINE, 0)
        self.benchmark_drawdown_series = Series("Benchmark Drawdown", SeriesType.LINE, 1)
        self.drawdown_chart.add_series(self.strategy_drawdown_series)
        self.drawdown_chart.add_series(self.benchmark_drawdown_series)
        self.algorithm.AddChart(self.drawdown_chart)
    
    def update_equity_tracking(self):
        """Update equity and benchmark tracking"""
        try:
            current_equity = self.algorithm.portfolio.total_portfolio_value
            current_benchmark = self.algorithm.securities[self.algorithm.spy].price
            
            # Initialize baseline values
            if self.initial_equity is None:
                self.initial_equity = current_equity
            if self.initial_benchmark is None:
                self.initial_benchmark = current_benchmark
            
            # Check for division by zero
            if self.initial_equity == 0 or self.initial_benchmark == 0:
                return
            
            # Store history
            self.equity_history.append(current_equity)
            self.benchmark_history.append(current_benchmark)
            self.dates.append(self.algorithm.time)
            
            # Calculate normalized values (base 100)
            normalized_equity = (current_equity / self.initial_equity) * 100
            normalized_benchmark = (current_benchmark / self.initial_benchmark) * 100
            
            # Update equity vs benchmark chart
            self.strategy_series.add_point(self.algorithm.time, normalized_equity)
            self.benchmark_series.add_point(self.algorithm.time, normalized_benchmark)
            
            # Calculate and update drawdowns
            self.update_drawdown_chart()
            
        except Exception as e:
            self.algorithm.log(f"Error updating equity tracking: {str(e)}")
    
    def update_drawdown_chart(self):
        """Update drawdown chart with both strategy and benchmark drawdowns"""
        try:
            if len(self.equity_history) < 2:
                return
            
            # Calculate strategy drawdown
            strategy_drawdown = self.calculate_drawdown(self.equity_history)
            
            # Calculate benchmark drawdown
            benchmark_drawdown = self.calculate_drawdown(self.benchmark_history)
            
            # Update drawdown chart
            self.strategy_drawdown_series.add_point(self.algorithm.time, strategy_drawdown)
            self.benchmark_drawdown_series.add_point(self.algorithm.time, benchmark_drawdown)
            
        except Exception as e:
            self.algorithm.log(f"Error updating drawdown chart: {str(e)}")
    
    def calculate_drawdown(self, price_history):
        """Calculate current drawdown from peak"""
        try:
            if not price_history:
                return 0.0
            
            # Find peak value
            peak = max(price_history)
            current = price_history[-1]
            
            # Calculate drawdown percentage
            drawdown = ((current - peak) / peak) * 100
            return drawdown
            
        except Exception as e:
            self.algorithm.log(f"Error calculating drawdown: {str(e)}")
            return 0.0
    
    def log_performance_summary(self):
        """Log a summary of current performance vs benchmark"""
        try:
            if len(self.equity_history) < 2:
                return
            
            # Calculate returns
            strategy_return = ((self.equity_history[-1] / self.initial_equity) - 1) * 100
            benchmark_return = ((self.benchmark_history[-1] / self.initial_benchmark) - 1) * 100
            
            # Calculate current drawdowns
            strategy_drawdown = self.calculate_drawdown(self.equity_history)
            benchmark_drawdown = self.calculate_drawdown(self.benchmark_history)
            
            # Calculate excess return
            excess_return = strategy_return - benchmark_return
            
            self.algorithm.log("=== PERFORMANCE SUMMARY ===")
            self.algorithm.log(f"Strategy Return: {strategy_return:.2f}%")
            self.algorithm.log(f"Benchmark Return: {benchmark_return:.2f}%")
            self.algorithm.log(f"Excess Return: {excess_return:.2f}%")
            self.algorithm.log(f"Strategy Drawdown: {strategy_drawdown:.2f}%")
            self.algorithm.log(f"Benchmark Drawdown: {benchmark_drawdown:.2f}%")
            self.algorithm.log("==========================")
            
        except Exception as e:
            self.algorithm.log(f"Error logging performance summary: {str(e)}")
    
    def get_performance_metrics(self):
        """Get current performance metrics as dictionary"""
        try:
            if len(self.equity_history) < 2:
                return {}
            
            strategy_return = ((self.equity_history[-1] / self.initial_equity) - 1) * 100
            benchmark_return = ((self.benchmark_history[-1] / self.initial_benchmark) - 1) * 100
            strategy_drawdown = self.calculate_drawdown(self.equity_history)
            benchmark_drawdown = self.calculate_drawdown(self.benchmark_history)
            excess_return = strategy_return - benchmark_return
            
            return {
                'strategy_return': strategy_return,
                'benchmark_return': benchmark_return,
                'excess_return': excess_return,
                'strategy_drawdown': strategy_drawdown,
                'benchmark_drawdown': benchmark_drawdown,
                'outperforming': excess_return > 0
            }
            
        except Exception as e:
            self.algorithm.log(f"Error getting performance metrics: {str(e)}")
            return {}
