"""
Simple test to diagnose backtest issues
"""

import os
import sys
from datetime import datetime

print("🔧 Testing local backtest setup...")

# Test 1: List algorithms
print("\n1. Testing algorithm discovery...")
algos = []
for d in os.listdir('.'):
    if os.path.isdir(d) and not d.startswith('.') and os.path.exists(os.path.join(d, 'main.py')):
        algos.append(d)

print(f"Found {len(algos)} algorithms:")
for i, algo in enumerate(algos[:5], 1):  # Show first 5
    print(f"  {i}. {algo}")

if not algos:
    print("❌ No algorithms found!")
    sys.exit(1)

# Test 2: Test import
print(f"\n2. Testing import for first algorithm: {algos[0]}")
try:
    project_path = os.path.join('.', algos[0])
    sys.path.insert(0, project_path)
    
    import main as project_module
    print("✅ Successfully imported main.py")
    
    # Find algorithm class
    algorithm_classes = []
    for name in dir(project_module):
        if (name.endswith('Algorithm') or 
            name.endswith('Algo') or 
            name.endswith('Strategy') or
            'Algorithm' in name or
            'Algo' in name):
            algorithm_classes.append(name)
    
    print(f"Found algorithm classes: {algorithm_classes}")
    
    if algorithm_classes:
        algorithm_class = getattr(project_module, algorithm_classes[0])
        print(f"✅ Successfully found algorithm class: {algorithm_classes[0]}")
    else:
        print("❌ No algorithm classes found")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error importing: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Test local test setup
print(f"\n3. Testing local test setup...")
try:
    import local_test_setup
    print("✅ Local test setup imported successfully")
except Exception as e:
    print(f"❌ Error importing local test setup: {e}")
    sys.exit(1)

# Test 4: Test yfinance
print(f"\n4. Testing yfinance...")
try:
    import yfinance as yf
    print("✅ yfinance imported successfully")
    
    # Test a simple download
    print("Testing data download...")
    ticker = yf.Ticker("SPY")
    hist = ticker.history(start="2023-01-01", end="2023-01-10")
    print(f"✅ Downloaded {len(hist)} days of data")
    
except Exception as e:
    print(f"❌ Error with yfinance: {e}")
    sys.exit(1)

print(f"\n✅ All tests passed! The issue might be in the main backtest loop.")
print(f"Try running a specific algorithm manually to see where it hangs.") 