# region imports
from AlgorithmImports import *

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
# endregion



# Linear weight allocation where best ticker gets 2x weight of worst ticker
def calculate_linear_weights(universe_symbols):
    """
    Calculate linear weights where:
    - Best ticker (first in list) gets highest weight
    - Worst ticker (last in list) gets lowest weight  
    - Best ticker weight = 2 * worst ticker weight
    - Linear interpolation for tickers in between
    """
    n = len(universe_symbols)
    
    if n == 1:
        return [1.0]
    
    # For linear weights where best = 2 * worst:
    # If worst weight = w, then best weight = 2w
    # Sum of arithmetic sequence = n * (first + last) / 2 = n * (2w + w) / 2 = 1.5 * n * w
    # Since sum must equal 1: 1.5 * n * w = 1, so w = 2 / (3 * n)
    
    worst_weight = 2.0 / (3.0 * n)
    best_weight = 2.0 * worst_weight
    
    # Create linear weights from best to worst
    weights = []
    for i in range(n):
        # Linear interpolation between best_weight and worst_weight
        weight = best_weight - i * (best_weight - worst_weight) / (n - 1)
        weights.append(weight)
    
    # Normalize to ensure sum equals 1 (handle floating point precision)
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]
    
    return weights

# QuantConnect Universe Selection Algorithm
# This script demonstrates various stock selection criteria
class UniverseSelectionAlgorithm(QCAlgorithm):
    
    def Initialize(self):
        # Set start and end dates for backtesting
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2025, 5, 1)
        
        # Set initial cash
        self.SetCash(100000)
        
        # Set benchmark
        self.SetBenchmark("SPY")
        
        # Universe selection parameters
        self.min_market_cap = 1e9  # $1B minimum market cap
        self.min_volume = 1e6  # Minimum daily volume
        self.min_price = 50.0  # Minimum stock price
        # self.pe_ratio_max = 50  # Maximum P/E ratio
        self.pe_ratio_min = 5
        self.debt_to_equity_max = 0.5  # Maximum debt-to-equity ratio
        self.roe_min = 0.10  # Minimum return on equity (10%)

        # OnData trade parameters
        self.entryTicket = None
        self.stopMarketTicket = None
        self.entryTime = datetime.min
        self.stopMerketOrderFillTime = datetime.min
        self.highestPrice = 0

        # add functions
        # calculate linear weights
        self.calculate_linear_weights = calculate_linear_weights
        
        # Add universe selection
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)
        
        # Dictionary to store selected symbols
        self.selected_symbols = {}
        
        # Rebalance monthly
        self.Schedule.On(
            self.DateRules.MonthStart(),
            self.TimeRules.At(9, 30),
            self.Rebalance
        )
    
    def CoarseSelectionFunction(self, coarse):
        """
        Coarse universe selection based on basic criteria
        """
        # Filter stocks based on basic criteria
        filtered = [x for x in coarse if 
                   x.HasFundamentalData and
                   x.Price > self.min_price and
                   x.DollarVolume > self.min_volume and
                   x.Market == "usa"]
        
        # Sort by dollar volume and take top 500
        sorted_by_volume = sorted(filtered, key=lambda x: x.DollarVolume, reverse=True)
        
        return [x.Symbol for x in sorted_by_volume[:500]]
    
    def FineSelectionFunction(self, fine):
        """
        Fine universe selection based on fundamental data
        """
        # Filter based on fundamental criteria
        filtered = []
        
        for f in fine:
            # Market cap filter
            market_cap = f.MarketCap
            # if market_cap < self.min_market_cap or market_cap > self.max_market_cap:
            if market_cap < self.min_market_cap:
                continue
            
            # P/E ratio filter
            pe_ratio = f.ValuationRatios.PERatio
            if pe_ratio <= self.pe_ratio_min:
                continue
            
            # Debt-to-equity filter
            total_debt = f.FinancialStatements.BalanceSheet.TotalDebt.Value
            total_equity = f.FinancialStatements.BalanceSheet.TotalEquity.Value
            if total_equity > 0:
                debt_to_equity = total_debt / total_equity
                if debt_to_equity > self.debt_to_equity_max:
                    continue
            else:
                continue  # Skip if no equity data
            
            # Return on equity filter
            roe = f.OperationRatios.ROE.OneYear
            if roe == 0 or roe < self.roe_min:
                continue
            
            # Additional quality filters
            # Positive earnings growth
            if f.OperationRatios.RevenueGrowth.OneYear < 0:
                continue
            
            # Current ratio > 1 (liquidity check)
            current_assets = f.FinancialStatements.BalanceSheet.CurrentAssets.Value
            current_liabilities = f.FinancialStatements.BalanceSheet.CurrentLiabilities.Value
            if current_liabilities > 0:
                current_ratio = current_assets / current_liabilities
                if current_ratio < 1.0:
                    continue
            else:
                continue  # Skip if no current liabilities data
            
            filtered.append(f)
        
        # Sort by a composite score (you can customize this)
        scored = []
        for f in filtered:
            # Simple scoring system - higher ROE and lower P/E is better
            roe = f.OperationRatios.ROE.OneYear
            pe_ratio = f.ValuationRatios.PERatio
            if pe_ratio > 0 and roe > 0:
                score = roe / pe_ratio
                scored.append((f, score))
        
        # Sort by score and take top stocks
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return top 10 symbols
        selected = [x[0].Symbol for x in scored[:10]]
        
        # Log selected stocks
        if selected:
            self.Log(f"Selected {len(selected)} stocks for universe")
            for symbol in selected[:5]:  # Log first 5
                self.Log(f"Selected: {symbol}")
        
        return selected
    

    def OnSecuritiesChanged(self, changes):
        """
        Handle changes in the universe
        """
        # Log additions and removals
        for security in changes.AddedSecurities:
            self.Log(f"Added to universe: {security.Symbol}")
            
        for security in changes.RemovedSecurities:
            self.Log(f"Removed from universe: {security.Symbol}")
            # Liquidate removed securities
            if security.Symbol in self.Portfolio and self.Portfolio[security.Symbol].Invested:
                self.Liquidate(security.Symbol)
    
    def Rebalance(self):
        """
        Rebalance portfolio monthly
        """
        # Get current universe
        universe_symbols = list(self.ActiveSecurities.Keys)
        
        if not universe_symbols:
            return
        
        # With linear weight allocation:
        weights = self.calculate_linear_weights(universe_symbols)

        # Now weights[i] corresponds to universe_symbols[i]
        for i, symbol in enumerate(universe_symbols):
            print(f"{symbol}: {weights[i]:.4f}")

        # Verify the ratio
        print(f"\nBest/Worst ratio: {weights[0]/weights[-1]:.2f}")
        print(f"Sum of weights: {sum(weights):.6f}")
        
        # Rebalance positions
        for place,symbol in enumerate(universe_symbols):
            self.SetHoldings(symbol, weights[place])
        
        self.Log(f"Rebalanced portfolio with {len(universe_symbols)} stocks")
    
    
    def OnOrderEvent(self, orderEvent):
        """
        Handle order events for all symbols
        """
        if orderEvent.Status != OrderStatus.Filled:
            return

        symbol = orderEvent.Symbol
        
        # Initialize tracking dictionaries if not exists
        if not hasattr(self, 'entryTickets'):
            self.entryTickets = {}
            self.stopMarketTickets = {}
            self.highestPrices = {}
            self.stopMarketOrderFillTimes = {}

        # Send stop loss order if entry limit order is filled
        if (symbol in self.entryTickets and 
            self.entryTickets[symbol] is not None and 
            self.entryTickets[symbol].OrderId == orderEvent.OrderId):
            
            self.stopMarketTickets[symbol] = self.StopMarketOrder(
                symbol,
                -self.entryTickets[symbol].Quantity,
                0.95 * self.entryTickets[symbol].AverageFillPrice
            )
            self.highestPrices[symbol] = self.entryTickets[symbol].AverageFillPrice
            self.Log(f"Placed stop loss order for {symbol} at ${0.95 * self.entryTickets[symbol].AverageFillPrice:.2f}")
            
            # Clear the entry ticket
            del self.entryTickets[symbol]  # Remove instead of setting to None

        # Save fill time of stop loss order
        if (symbol in self.stopMarketTickets and 
            self.stopMarketTickets[symbol] is not None and 
            self.stopMarketTickets[symbol].OrderId == orderEvent.OrderId):
            
            self.stopMarketOrderFillTimes[symbol] = self.Time
            self.highestPrices[symbol] = 0
            del self.stopMarketTickets[symbol]  # Remove instead of setting to None
            self.Log(f"Stop loss filled for {symbol}, waiting 30 days before re-entry")
            
    def OnData(self, data):
        """
        Main data handler with trailing stop logic for all tickers
        """
        # Initialize tracking dictionaries if not exists
        if not hasattr(self, 'entryTickets'):
            self.entryTickets = {}
            self.stopMarketTickets = {}
            self.entryTimes = {}
            self.highestPrices = {}
            self.stopMarketOrderFillTimes = {}
        
        # Get all symbols in our universe
        universe_symbols = list(self.ActiveSecurities.Keys)
        
        for symbol in universe_symbols:
            if symbol not in data or not data[symbol]:
                continue
                
            price = data[symbol].Price
            
            # Initialize tracking for new symbols
            if symbol not in self.stopMarketOrderFillTimes:
                self.stopMarketOrderFillTimes[symbol] = self.Time - timedelta(days=31)
            if symbol not in self.highestPrices:
                self.highestPrices[symbol] = 0
            
            # Wait 30 days after last exit for this symbol
            if (self.Time - self.stopMarketOrderFillTimes[symbol]).days < 30:
                continue

            # Check if we have available cash (keep 10% reserve)
            available_cash = self.Portfolio.Cash * 0.9
            target_allocation_per_stock = available_cash / len(universe_symbols)
            
            # Send entry limit order if not invested in this symbol
            if (not self.Portfolio[symbol].Invested and 
                symbol not in self.entryTickets and
                not self.Transactions.GetOpenOrders(symbol)):
                
                if target_allocation_per_stock > 100:  # Minimum order size check
                    quantity = int(target_allocation_per_stock / price)
                    if quantity > 0:
                        self.entryTickets[symbol] = self.LimitOrder(symbol, quantity, price, f"Entry Order for {symbol}")
                        self.entryTimes[symbol] = self.Time
                        self.Log(f"Placed entry order for {symbol} at ${price:.2f}")

            # Move limit price if not filled after 1 day - FIXED: Check if ticket exists and is not None
            if (symbol in self.entryTickets and 
                self.entryTickets[symbol] is not None and  # Added None check
                symbol in self.entryTimes and
                (self.Time - self.entryTimes[symbol]).days > 1 and 
                self.entryTickets[symbol].Status != OrderStatus.Filled):
                
                self.entryTimes[symbol] = self.Time
                # Update limit price to current market price
                updateFields = UpdateOrderFields()
                updateFields.LimitPrice = price
                self.entryTickets[symbol].Update(updateFields)
                self.Log(f"Updated entry limit price for {symbol} to ${price:.2f}")

            # Move up trailing stop price
            if (symbol in self.stopMarketTickets and 
                self.stopMarketTickets[symbol] is not None and 
                self.Portfolio[symbol].Invested):
                
                if price > self.highestPrices[symbol]:
                    self.highestPrices[symbol] = price
                    updateFields = UpdateOrderFields()
                    updateFields.StopPrice = price * 0.95  # 5% trailing stop
                    self.stopMarketTickets[symbol].Update(updateFields)
                    self.Log(f"Updated trailing stop for {symbol} to ${price * 0.95:.2f}")
    

# Alternative Universe Selection Examples
class SectorBasedUniverse(QCAlgorithm):
    """
    Example of sector-based universe selection
    """
    
    def Initialize(self):
        self.SetStartDate(2023, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(100000)
        
        # Target sectors (Morningstar sector codes)
        self.target_sectors = [
            MorningstarSectorCode.Technology,
            MorningstarSectorCode.Healthcare,
            MorningstarSectorCode.FinancialServices
        ]
        
        self.AddUniverse(self.SectorCoarseSelection, self.SectorFineSelection)
    
    def SectorCoarseSelection(self, coarse):
        # Basic filtering
        filtered = [x for x in coarse if 
                   x.HasFundamentalData and
                   x.Price > 10 and
                   x.DollarVolume > 1e6]
        
        return [x.Symbol for x in filtered[:1000]]
    
    def SectorFineSelection(self, fine):
        # Filter by sector
        sector_filtered = [f for f in fine if 
                          f.AssetClassification.MorningstarSectorCode in self.target_sectors]
        
        # Additional fundamental filters
        quality_filtered = [f for f in sector_filtered if
                           f.ValuationRatios.PERatio > 0 and
                           f.ValuationRatios.PERatio < 25 and
                           f.OperationRatios.ROE.OneYear > 0.15]
        
        # Sort by ROE and return top 30
        quality_filtered.sort(key=lambda x: x.OperationRatios.ROE.OneYear, reverse=True)
        
        return [f.Symbol for f in quality_filtered[:30]]
