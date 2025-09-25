"""
Local Backtesting Framework for QuantConnect Algorithms
This allows you to run QuantConnect algorithms locally with simulated data
"""

import sys
import os
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Import our local testing setup
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import local_test_setup

def find_algorithm_class(project_path):
    """Find the main algorithm class in a project"""
    sys.path.insert(0, project_path)
    
    try:
        import main as project_module
        
        # Look for common algorithm class patterns
        algorithm_classes = []
        for name in dir(project_module):
            if (name.endswith('Algorithm') or 
                name.endswith('Algo') or 
                name.endswith('Strategy') or
                'Algorithm' in name or
                'Algo' in name):
                algorithm_classes.append(name)
        
        if algorithm_classes:
            return getattr(project_module, algorithm_classes[0])
        else:
            # Return the first class that inherits from QCAlgorithm
            for name in dir(project_module):
                obj = getattr(project_module, name)
                if hasattr(obj, '__bases__'):
                    for base in obj.__bases__:
                        if 'QCAlgorithm' in str(base):
                            return obj
            
            return None
            
    except Exception as e:
        print(f"Error importing {project_path}: {e}")
        return None

class LocalBacktestEngine:
    """Simple local backtesting engine for QuantConnect algorithms"""
    
    def __init__(self, algorithm_class, symbols=None, start_date=None, end_date=None, initial_cash=100000):
        self.algorithm_class = algorithm_class
        self.symbols = symbols or ["SPY"]
        self.start_date = start_date or datetime(2023, 1, 1)
        self.end_date = end_date or datetime(2024, 1, 1)
        self.initial_cash = initial_cash
        
        # Download data
        self.data = self._download_data()
        
        # Initialize algorithm
        self.algorithm = algorithm_class()
        self._setup_algorithm()
        
    def _download_data(self):
        """Download historical data for symbols"""
        print(f"📊 Downloading data for {self.symbols}...")
        data = {}
        
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=self.start_date, end=self.end_date)
                data[symbol] = hist
                print(f"✅ Downloaded {len(hist)} days of data for {symbol}")
            except Exception as e:
                print(f"❌ Error downloading data for {symbol}: {e}")
                # Create dummy data
                dates = pd.date_range(self.start_date, self.end_date, freq='D')
                data[symbol] = pd.DataFrame({
                    'Open': [100] * len(dates),
                    'High': [105] * len(dates),
                    'Low': [95] * len(dates),
                    'Close': [100 + i * 0.1 for i in range(len(dates))],
                    'Volume': [1000000] * len(dates)
                }, index=dates)
        
        return data
    
    def _setup_algorithm(self):
        """Setup the algorithm with mock QuantConnect environment"""
        # Mock algorithm properties
        self.algorithm.Time = self.start_date
        self.algorithm.Securities = {}
        self.algorithm.Portfolio = {}
        self.algorithm.Cash = self.initial_cash
        self.algorithm.TotalPortfolioValue = self.initial_cash
        self.algorithm.UniverseSettings = type('obj', (object,), {'Resolution': 'Hour'})()
        self.algorithm.Charts = {}

        # Setup securities
        for symbol in self.symbols:
            self.algorithm.Securities[symbol] = type('obj', (object,), {
                'Symbol': symbol,
                'Price': self.data[symbol]['Close'].iloc[0] if len(self.data[symbol]) > 0 else 100,
                'Open': self.data[symbol]['Open'].iloc[0] if len(self.data[symbol]) > 0 else 100,
                'High': self.data[symbol]['High'].iloc[0] if len(self.data[symbol]) > 0 else 105,
                'Low': self.data[symbol]['Low'].iloc[0] if len(self.data[symbol]) > 0 else 95,
                'Volume': self.data[symbol]['Volume'].iloc[0] if len(self.data[symbol]) > 0 else 1000000
            })()
            
            self.algorithm.Portfolio[symbol] = type('obj', (object,), {
                'IsLong': False,
                'IsShort': False,
                'Quantity': 0,
                'HoldingsValue': 0,
                'UnrealizedProfit': 0
            })()
        
        # Mock algorithm methods
        self.algorithm.SetCash = lambda cash: setattr(self.algorithm, 'Cash', cash)
        self.algorithm.SetStartDate = lambda year, month, day: None
        self.algorithm.SetEndDate = lambda year, month, day: None
        self.algorithm.AddEquity = lambda symbol: type('obj', (object,), {'Symbol': symbol})()
        self.algorithm.SMA = lambda symbol, period, resolution: type('obj', (object,), {
            'Current': type('obj', (object,), {'Value': 100})(),
            'IsReady': True
        })()
        self.algorithm.MOM = lambda symbol, period, resolution: type('obj', (object,), {
            'Current': type('obj', (object,), {'Value': 0.05})(),
            'IsReady': True
        })()
        self.algorithm.Plot = lambda chart, series, value: None
        self.algorithm.AddChart = lambda chart: None
        self.algorithm.SetUniverseSelection = lambda model: None
        self.algorithm.SetAlpha = lambda model: None
        self.algorithm.SetPortfolioConstruction = lambda model: None
        self.algorithm.SetRiskManagement = lambda model: None
        self.algorithm.SetExecution = lambda model: None
        
        # Try to call Initialize if it exists
        if hasattr(self.algorithm, 'Initialize'):
            try:
                self.algorithm.Initialize()
                print("✅ Algorithm initialized successfully")
            except Exception as e:
                print(f"⚠️  Algorithm initialization had issues: {e}")
    
    def run_backtest(self):
        """Run the backtest"""
        print(f"\n🚀 Starting local backtest...")
        print(f"📅 Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"💰 Initial Cash: ${self.initial_cash:,.2f}")
        print(f"📈 Symbols: {self.symbols}")
        
        # Get the shortest data series
        min_length = min(len(data) for data in self.data.values())
        
        # Track performance
        portfolio_values = []
        trades = []
        
        for i in range(min_length):
            # Update current time
            current_date = self.data[self.symbols[0]].index[i]
            self.algorithm.Time = current_date
            
            # Update security prices
            for symbol in self.symbols:
                if i < len(self.data[symbol]):
                    self.algorithm.Securities[symbol].Price = self.data[symbol]['Close'].iloc[i]
                    self.algorithm.Securities[symbol].Open = self.data[symbol]['Open'].iloc[i]
                    self.algorithm.Securities[symbol].High = self.data[symbol]['High'].iloc[i]
                    self.algorithm.Securities[symbol].Low = self.data[symbol]['Low'].iloc[i]
                    self.algorithm.Securities[symbol].Volume = self.data[symbol]['Volume'].iloc[i]
            
            # Create mock data object
            mock_data = type('obj', (object,), {
                'Keys': self.symbols,
                'Values': [self.algorithm.Securities[symbol] for symbol in self.symbols]
            })()
            
            # Call OnData if it exists
            if hasattr(self.algorithm, 'OnData'):
                try:
                    self.algorithm.OnData(mock_data)
                except Exception as e:
                    print(f"⚠️  Error in OnData on {current_date}: {e}")
            
            # Calculate portfolio value
            portfolio_value = self.algorithm.Cash
            for symbol in self.symbols:
                if self.algorithm.Portfolio[symbol].Quantity != 0:
                    portfolio_value += self.algorithm.Portfolio[symbol].Quantity * self.algorithm.Securities[symbol].Price
            
            portfolio_values.append({
                'Date': current_date,
                'PortfolioValue': portfolio_value,
                'Cash': self.algorithm.Cash
            })
            
            # Print progress every 30 days
            if i % 30 == 0:
                print(f"📊 {current_date.date()}: Portfolio Value = ${portfolio_value:,.2f}")
        
        # Calculate final results
        final_value = portfolio_values[-1]['PortfolioValue']
        total_return = (final_value - self.initial_cash) / self.initial_cash * 100
        
        print(f"\n📊 Backtest Results:")
        print(f"💰 Final Portfolio Value: ${final_value:,.2f}")
        print(f"📈 Total Return: {total_return:.2f}%")
        print(f"💵 Cash: ${self.algorithm.Cash:,.2f}")
        
        # Show holdings
        print(f"\n📋 Final Holdings:")
        for symbol in self.symbols:
            holding = self.algorithm.Portfolio[symbol]
            if holding.Quantity != 0:
                value = holding.Quantity * self.algorithm.Securities[symbol].Price
                print(f"  {symbol}: {holding.Quantity} shares = ${value:,.2f}")
        
        return {
            'final_value': final_value,
            'total_return': total_return,
            'portfolio_values': portfolio_values
        }

def run_algorithm_backtest(project_name, algorithm_class_name=None):
    """Helper function to run a backtest for a specific project"""
    print(f"🎯 Running backtest for: {project_name}")
    
    # Import the project
    project_path = os.path.join(os.path.dirname(__file__), project_name)
    sys.path.insert(0, project_path)
    
    try:
        import main as project_module
        
        # Find the algorithm class
        if algorithm_class_name:
            algorithm_class = getattr(project_module, algorithm_class_name)
        else:
            # Try to find the main algorithm class
            algorithm_classes = [cls for cls in dir(project_module) 
                               if cls.endswith('Algorithm') or cls.endswith('Algo')]
            if algorithm_classes:
                algorithm_class = getattr(project_module, algorithm_classes[0])
            else:
                print("❌ Could not find algorithm class")
                return
        
        # Run backtest
        engine = LocalBacktestEngine(algorithm_class)
        results = engine.run_backtest()
        
        return results
        
    except Exception as e:
        print(f"❌ Error running backtest: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Example usage
    print("🔧 Local Backtesting Framework")
    print("=" * 50)
    
    # Test with Alert Fluorescent Pink Zebra
    results = run_algorithm_backtest("Alert Fluorescent Pink Zebra", "FrameworkAlgorithm") 