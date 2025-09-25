"""
Local Backtesting Framework for All QuantConnect Algorithms
Choose any algorithm and run a local backtest with detailed results
"""

import os
import sys
from datetime import datetime
from local_backtest_runner import LocalBacktestEngine, find_algorithm_class

def list_algorithms():
    """List all available algorithms"""
    algos = []
    for d in os.listdir('.'):
        if os.path.isdir(d) and not d.startswith('.') and os.path.exists(os.path.join(d, 'main.py')):
            algos.append(d)
    return sorted(algos)

def prompt(msg, default=None, cast=str):
    """Helper function to prompt user for input"""
    val = input(f"{msg} [{default}]: ").strip()
    if not val:
        return default
    try:
        return cast(val)
    except Exception:
        return val

def print_summary(results, algo_name):
    """Print comprehensive backtest results"""
    print(f"\n{'='*60}")
    print(f"📊 BACKTEST RESULTS: {algo_name}")
    print(f"{'='*60}")
    print(f"💰 Final Portfolio Value: ${results['final_value']:,.2f}")
    print(f"📈 Total Return: {results['total_return']:.2f}%")
    print(f"💵 Initial Cash: ${results.get('initial_cash', 100000):,.2f}")
    print(f"💵 Final Cash: ${results['portfolio_values'][-1]['Cash']:,.2f}")
    
    # Calculate additional metrics
    if len(results['portfolio_values']) > 1:
        returns = []
        for i in range(1, len(results['portfolio_values'])):
            prev_val = results['portfolio_values'][i-1]['PortfolioValue']
            curr_val = results['portfolio_values'][i]['PortfolioValue']
            if prev_val > 0:
                returns.append((curr_val - prev_val) / prev_val)
        
        if returns:
            import numpy as np
            returns_series = np.array(returns)
            volatility = returns_series.std() * np.sqrt(252) * 100
            sharpe_ratio = (returns_series.mean() * 252) / (returns_series.std() * np.sqrt(252)) if returns_series.std() > 0 else 0
            
            print(f"\n📊 PERFORMANCE METRICS:")
            print(f"📈 Sharpe Ratio: {sharpe_ratio:.2f}")
            print(f"📊 Volatility: {volatility:.2f}%")
    
    print(f"\n📋 FINAL HOLDINGS:")
    final_pv = results['portfolio_values'][-1]
    holdings_value = final_pv['PortfolioValue'] - final_pv['Cash']
    if holdings_value > 0:
        print(f"  📈 Total Holdings Value: ${holdings_value:,.2f}")
    else:
        print(f"  💰 All in cash")
    
    print(f"\n{'='*60}")

def main():
    """Main function to run local backtests"""
    print("🔧 LOCAL BACKTESTING FRAMEWORK")
    print("="*60)
    
    # Get available algorithms
    algos = list_algorithms()
    if not algos:
        print("❌ No algorithms found!")
        return
    
    print(f"📁 Found {len(algos)} algorithms:")
    for i, algo in enumerate(algos, 1):
        print(f"  {i}. {algo}")
    
    # Get user selection
    while True:
        try:
            choice = int(input(f"\n🎯 Select algorithm (1-{len(algos)}): ").strip())
            if 1 <= choice <= len(algos):
                selected_algo = algos[choice-1]
                break
        except Exception:
            pass
        print("❌ Invalid selection. Please try again.")
    
    # Get backtest parameters
    symbols = prompt("📈 Symbols (comma-separated)", default="SPY,QQQ", cast=str)
    symbols = [s.strip() for s in symbols.split(',') if s.strip()]
    
    start_date = prompt("📅 Start date (YYYY-MM-DD)", default="2023-01-01", cast=str)
    end_date = prompt("📅 End date (YYYY-MM-DD)", default="2024-01-01", cast=str)
    initial_cash = prompt("💰 Initial cash", default=100000, cast=float)
    
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    
    # Find and run algorithm
    project_path = os.path.join('.', selected_algo)
    algorithm_class = find_algorithm_class(project_path)
    
    if algorithm_class is None:
        print(f"❌ Could not find algorithm class in {selected_algo}")
        return
    
    print(f"\n🚀 Running backtest for {selected_algo}...")
    
    try:
        engine = LocalBacktestEngine(
            algorithm_class=algorithm_class,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash
        )
        
        results = engine.run_backtest()
        print_summary(results, selected_algo)
        
    except Exception as e:
        print(f"❌ Error running backtest: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 