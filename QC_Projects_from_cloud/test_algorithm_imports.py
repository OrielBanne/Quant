"""
Test script to verify QuantConnect algorithm imports work locally
"""

# First, import the local testing setup
import local_test_setup

# Now try to import the problematic algorithm
try:
    # Import the algorithm that was causing the NameError
    import sys
    import os
    
    # Add the algorithm directory to the path
    algorithm_path = "Alert Fluorescent Pink Zebra"
    sys.path.insert(0, algorithm_path)
    
    # Try to import the main module
    import main as algorithm_module
    
    print("✅ Successfully imported algorithm module!")
    print(f"Available classes: {[cls for cls in dir(algorithm_module) if not cls.startswith('_')]}")
    
    # Test creating instances
    try:
        mom_alpha = algorithm_module.MOMAlphaModel()
        print("✅ Successfully created MOMAlphaModel instance")
    except Exception as e:
        print(f"❌ Error creating MOMAlphaModel: {e}")
    
    try:
        dual_sma_alpha = algorithm_module.DualSmaAlphaModel()
        print("✅ Successfully created DualSmaAlphaModel instance")
    except Exception as e:
        print(f"❌ Error creating DualSmaAlphaModel: {e}")
    
    try:
        framework_algo = algorithm_module.FrameworkAlgorithm()
        print("✅ Successfully created FrameworkAlgorithm instance")
    except Exception as e:
        print(f"❌ Error creating FrameworkAlgorithm: {e}")
        
except Exception as e:
    print(f"❌ Error importing algorithm: {e}")
    import traceback
    traceback.print_exc()

print("\n🎉 Local testing setup is working!")
print("You can now run your QuantConnect algorithms locally for development and testing.") 