"""
Local Testing Setup for QuantConnect Algorithms
This file provides mock classes and imports for local development
"""

import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
from abc import ABC, abstractmethod
from enum import Enum

# Mock QuantConnect classes for local testing
class AlphaModel(ABC):
    """Base class for Alpha Models"""
    @abstractmethod
    def Update(self, algorithm, data):
        pass
    
    def OnSecuritiesChanged(self, algorithm, changes):
        pass

class PythonIndicator(ABC):
    """Base class for Python indicators"""
    def __init__(self, name, period=None):
        self.Name = name
        self.Time = datetime.min
        self.Value = 0
        self.IsReady = False
        self.Current = type('obj', (object,), {'Value': 0})()
    
    def Update(self, input):
        pass

class PythonData:
    """Base class for Python data"""
    def __init__(self):
        self.EndTime = datetime.now()
        self.Close = 0.0

class FundamentalUniverseSelectionModel(ABC):
    """Base class for fundamental universe selection"""
    def __init__(self):
        pass

class ETFConstituentsUniverseSelectionModel(ABC):
    """Base class for ETF constituents universe selection"""
    def __init__(self):
        pass

class QCAlgorithm:
    """Mock QCAlgorithm class for local testing"""
    def __init__(self):
        self.Time = datetime.now()
        self.Securities = {}
        self.UniverseSettings = type('obj', (object,), {'Resolution': 'Hour'})()
        self.Charts = {}
        self.Portfolio = {}
        self.Spy = None

class Insight:
    """Mock Insight class"""
    @staticmethod
    def Price(symbol, timedelta, direction):
        return f"Insight.Price({symbol}, {timedelta}, {direction})"
    
    @staticmethod
    def Group(insights):
        return insights

class InsightDirection:
    UP = "Up"
    DOWN = "Down"
    FLAT = "Flat"

class Symbol:
    """Mock Symbol class"""
    @staticmethod
    def Create(ticker, security_type, market):
        return f"Symbol({ticker}, {security_type}, {market})"

class SecurityType:
    Equity = "Equity"

class Market:
    USA = "USA"

class Resolution:
    DAILY = "Daily"
    HOUR = "Hour"

class ManualUniverseSelectionModel:
    def __init__(self, symbols):
        self.symbols = symbols

class EqualWeightingPortfolioConstructionModel:
    pass

class MaximumDrawdownPercentPerSecurity:
    def __init__(self, percent):
        self.percent = percent

class ImmediateExecutionModel:
    pass

class Chart:
    def __init__(self, name):
        self.name = name
        self.series = {}
    
    def AddSeries(self, series):
        self.series[series.name] = series

class Series:
    def __init__(self, name, series_type):
        self.name = name
        self.series_type = series_type

class SeriesType:
    Scatter = "Scatter"

class Color:
    Green = "Green"
    Red = "Red"

class ChartPoint:
    def __init__(self, time, value):
        self.time = time
        self.value = value

# Add these to sys.modules so they can be imported
sys.modules['AlgorithmImports'] = type('obj', (object,), {
    'AlphaModel': AlphaModel,
    'PythonIndicator': PythonIndicator,
    'PythonData': PythonData,
    'FundamentalUniverseSelectionModel': FundamentalUniverseSelectionModel,
    'ETFConstituentsUniverseSelectionModel': ETFConstituentsUniverseSelectionModel,
    'QCAlgorithm': QCAlgorithm,
    'Insight': Insight,
    'InsightDirection': InsightDirection,
    'Symbol': Symbol,
    'SecurityType': SecurityType,
    'Market': Market,
    'Resolution': Resolution,
    'ManualUniverseSelectionModel': ManualUniverseSelectionModel,
    'EqualWeightingPortfolioConstructionModel': EqualWeightingPortfolioConstructionModel,
    'MaximumDrawdownPercentPerSecurity': MaximumDrawdownPercentPerSecurity,
    'ImmediateExecutionModel': ImmediateExecutionModel,
    'Chart': Chart,
    'Series': Series,
    'SeriesType': SeriesType,
    'Color': Color,
    'ChartPoint': ChartPoint,
    'Enum': Enum,
})()

# Add wildcard import
sys.modules['AlgorithmImports'].__all__ = [
    'AlphaModel', 'PythonIndicator', 'PythonData', 'FundamentalUniverseSelectionModel',
    'ETFConstituentsUniverseSelectionModel', 'QCAlgorithm', 'Insight', 'InsightDirection', 'Symbol',
    'SecurityType', 'Market', 'Resolution', 'ManualUniverseSelectionModel',
    'EqualWeightingPortfolioConstructionModel', 'MaximumDrawdownPercentPerSecurity',
    'ImmediateExecutionModel', 'Chart', 'Series', 'SeriesType', 'Color', 'ChartPoint', 'Enum'
]

print("✅ Local testing environment set up successfully!")
print("You can now import and test your QuantConnect algorithms locally.") 