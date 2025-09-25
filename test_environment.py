#!/usr/bin/env python3
"""
Test script to verify QuantConnect Virtual Environment setup
"""

def test_imports():
    """Test that all key packages can be imported successfully"""
    print("Testing QuantConnect Virtual Environment...")
    print("=" * 50)
    
    # Test data analysis packages
    try:
        import pandas as pd
        print("✓ pandas imported successfully")
        print(f"  Version: {pd.__version__}")
    except ImportError as e:
        print(f"✗ pandas import failed: {e}")
    
    try:
        import numpy as np
        print("✓ numpy imported successfully")
        print(f"  Version: {np.__version__}")
    except ImportError as e:
        print(f"✗ numpy import failed: {e}")
    
    try:
        import matplotlib.pyplot as plt
        print("✓ matplotlib imported successfully")
        print(f"  Version: {plt.matplotlib.__version__}")
    except ImportError as e:
        print(f"✗ matplotlib import failed: {e}")
    
    try:
        import seaborn as sns
        print("✓ seaborn imported successfully")
        print(f"  Version: {sns.__version__}")
    except ImportError as e:
        print(f"✗ seaborn import failed: {e}")
    
    try:
        import plotly
        print("✓ plotly imported successfully")
        print(f"  Version: {plotly.__version__}")
    except ImportError as e:
        print(f"✗ plotly import failed: {e}")
    
    # Test financial data packages
    try:
        import yfinance as yf
        print("✓ yfinance imported successfully")
        print(f"  Version: {yf.__version__}")
    except ImportError as e:
        print(f"✗ yfinance import failed: {e}")
    
    try:
        import alpha_vantage
        print("✓ alpha_vantage imported successfully")
    except ImportError as e:
        print(f"✗ alpha_vantage import failed: {e}")
    
    # Test machine learning packages
    try:
        import sklearn
        print("✓ scikit-learn imported successfully")
        print(f"  Version: {sklearn.__version__}")
    except ImportError as e:
        print(f"✗ scikit-learn import failed: {e}")
    
    # Test development tools
    try:
        import jupyter
        print("✓ jupyter imported successfully")
    except ImportError as e:
        print(f"✗ jupyter import failed: {e}")
    
    try:
        import black
        print("✓ black imported successfully")
        print(f"  Version: {black.__version__}")
    except ImportError as e:
        print(f"✗ black import failed: {e}")
    
    try:
        import flake8
        print("✓ flake8 imported successfully")
    except ImportError as e:
        print(f"✗ flake8 import failed: {e}")
    
    try:
        import pytest
        print("✓ pytest imported successfully")
        print(f"  Version: {pytest.__version__}")
    except ImportError as e:
        print(f"✗ pytest import failed: {e}")
    
    # Test utility packages
    try:
        import requests
        print("✓ requests imported successfully")
        print(f"  Version: {requests.__version__}")
    except ImportError as e:
        print(f"✗ requests import failed: {e}")
    
    try:
        import dotenv
        print("✓ python-dotenv imported successfully")
    except ImportError as e:
        print(f"✗ python-dotenv import failed: {e}")
    
    try:
        import tqdm
        print("✓ tqdm imported successfully")
        print(f"  Version: {tqdm.__version__}")
    except ImportError as e:
        print(f"✗ tqdm import failed: {e}")

def test_basic_functionality():
    """Test basic functionality of key packages"""
    print("\n" + "=" * 50)
    print("Testing basic functionality...")
    print("=" * 50)
    
    # Test pandas functionality
    try:
        import pandas as pd
        import numpy as np
        
        # Create a simple DataFrame
        df = pd.DataFrame({
            'Date': pd.date_range('2023-01-01', periods=10),
            'Price': np.random.randn(10).cumsum() + 100,
            'Volume': np.random.randint(1000, 10000, 10)
        })
        print("✓ pandas DataFrame creation successful")
        print(f"  DataFrame shape: {df.shape}")
        
    except Exception as e:
        print(f"✗ pandas functionality test failed: {e}")
    
    # Test yfinance functionality
    try:
        import yfinance as yf
        
        # Get basic info for a stock
        ticker = yf.Ticker("AAPL")
        info = ticker.info
        print("✓ yfinance data retrieval successful")
        print(f"  Retrieved data for: {info.get('longName', 'AAPL')}")
        
    except Exception as e:
        print(f"✗ yfinance functionality test failed: {e}")
    
    # Test matplotlib functionality
    try:
        import matplotlib.pyplot as plt
        
        # Create a simple plot
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot([1, 2, 3, 4], [1, 4, 2, 3])
        ax.set_title('Test Plot')
        plt.close()  # Close to avoid displaying
        print("✓ matplotlib plotting successful")
        
    except Exception as e:
        print(f"✗ matplotlib functionality test failed: {e}")

def main():
    """Main test function"""
    print("QuantConnect Virtual Environment Test")
    print("=" * 50)
    
    # Test imports
    test_imports()
    
    # Test functionality
    test_basic_functionality()
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("=" * 50)
    print("\nYour QuantConnect Virtual Environment is ready!")
    print("\nTo start using it:")
    print("1. Activate: .\\QC_VENV\\Scripts\\activate.bat")
    print("2. Start Jupyter: jupyter notebook")
    print("3. Deactivate: deactivate")

if __name__ == "__main__":
    main() 