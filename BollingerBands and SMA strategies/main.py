# region imports
from AlgorithmImports import *
from datetime import timedelta
from sklearn.preprocessing import MinMaxScaler
import numpy as np
from abc import ABC, abstractmethod
from enum import Enum
from Library import add
# endregion

class TradingSignal(Enum):
    """Trading signal types"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class TradingStrategy(ABC):
    """Abstract base class for trading strategies"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.indicators = {}
        
    @abstractmethod
    def initialize_indicators(self, symbol):
        """Initialize indicators for a given symbol"""
        pass
    
    @abstractmethod
    def get_signal(self, symbol, data):
        """Get trading signal for a symbol"""
        pass
    
    @abstractmethod
    def get_strategy_name(self):
        """Get strategy name for logging"""
        pass

class BollingerBandsStrategy(TradingStrategy):
    """Bollinger Bands trading strategy"""
    
    def __init__(self, algorithm, period=20, std_dev=2.0):
        super().__init__(algorithm)
        self.period = period
        self.std_dev = std_dev
        
    def initialize_indicators(self, symbol):
        """Initialize Bollinger Bands indicators"""
        if symbol not in self.indicators:
            self.indicators[symbol] = {
                'bb': self.algorithm.BB(symbol, 
                self.period, self.std_dev, 
                Resolution.DAILY),
                'last_signal': TradingSignal.HOLD,
                'signal_time': None
            }
    
    def get_signal(self, symbol, data):
        """
        Bollinger Bands Strategy:
        - BUY when price touches lower band (oversold)
        - SELL when price touches upper band (overbought)
        - Avoid rapid signal changes with cooldown
        """
        if symbol not in self.indicators:
            return TradingSignal.HOLD
            
        bb = self.indicators[symbol]['bb']
        
        if not bb.IsReady:
            return TradingSignal.HOLD
            
        price = data[symbol].Price
        upper_band = bb.UpperBand.Current.Value
        middle_band = bb.MiddleBand.Current.Value
        lower_band = bb.LowerBand.Current.Value
        
        # Signal cooldown to prevent whipsaws
        last_signal_time = self.indicators[symbol]['signal_time']
        if last_signal_time and (self.algorithm.Time - last_signal_time).days < 2:
            return TradingSignal.HOLD
        
        signal = TradingSignal.HOLD
        
        # Buy signal: price near lower band
        if price <= lower_band * 1.02:  # 2% tolerance
            signal = TradingSignal.BUY
            
        # Sell signal: price near upper band
        elif price >= upper_band * 0.98:  # 2% tolerance
            signal = TradingSignal.SELL
            
        # Update last signal if changed
        if signal != self.indicators[symbol]['last_signal']:
            self.indicators[symbol]['last_signal'] = signal
            self.indicators[symbol]['signal_time'] = self.algorithm.Time
            
        return signal
    
    def get_strategy_name(self):
        return f"BollingerBands_{self.period}_{self.std_dev}"

class SMATraversalStrategy(TradingStrategy):
    """SMA Traversal trading strategy"""
    
    def __init__(self, algorithm, fast_period=5, slow_period=20):
        super().__init__(algorithm)
        self.fast_period = fast_period
        self.slow_period = slow_period
        
    def initialize_indicators(self, symbol):
        """Initialize SMA indicators"""
        if symbol not in self.indicators:
            self.indicators[symbol] = {
                'sma_fast': self.algorithm.SMA(symbol, self.fast_period, Resolution.DAILY),
                'sma_slow': self.algorithm.SMA(symbol, self.slow_period, Resolution.DAILY),
                'last_signal': TradingSignal.HOLD,
                'signal_time': None,
                'previous_fast': None,
                'previous_slow': None
            }
    
    def get_signal(self, symbol, data):
        """
        SMA Traversal Strategy:
        - BUY when fast SMA crosses above slow SMA (golden cross)
        - SELL when fast SMA crosses below slow SMA (death cross)
        """
        if symbol not in self.indicators:
            return TradingSignal.HOLD
            
        sma_fast = self.indicators[symbol]['sma_fast']
        sma_slow = self.indicators[symbol]['sma_slow']
        
        if not (sma_fast.IsReady and sma_slow.IsReady):
            return TradingSignal.HOLD
            
        current_fast = sma_fast.Current.Value
        current_slow = sma_slow.Current.Value
        previous_fast = self.indicators[symbol]['previous_fast']
        previous_slow = self.indicators[symbol]['previous_slow']
        
        signal = TradingSignal.HOLD
        
        # Check for crossover only if we have previous values
        if previous_fast is not None and previous_slow is not None:
            # Golden Cross: fast SMA crosses above slow SMA
            if (previous_fast <= previous_slow and current_fast > current_slow):
                signal = TradingSignal.BUY
                
            # Death Cross: fast SMA crosses below slow SMA
            elif (previous_fast >= previous_slow and current_fast < current_slow):
                signal = TradingSignal.SELL
        
        # Update previous values for next iteration
        self.indicators[symbol]['previous_fast'] = current_fast
        self.indicators[symbol]['previous_slow'] = current_slow
        
        # Update last signal if changed
        if signal != TradingSignal.HOLD:
            self.indicators[symbol]['last_signal'] = signal
            self.indicators[symbol]['signal_time'] = self.algorithm.Time
            
        return signal
    
    def get_strategy_name(self):
        return f"SMATraversal_{self.fast_period}_{self.slow_period}"

class TradingEngine:
    """Main trading engine that manages different strategies"""
    
    def __init__(self, algorithm):
        self.algorithm = algorithm
        self.active_strategy = None
        self.strategies = {}
        
    def add_strategy(self, name, strategy):
        """Add a trading strategy"""
        self.strategies[name] = strategy
        
    def set_active_strategy(self, name):
        """Set the active trading strategy"""
        if name in self.strategies:
            self.active_strategy = self.strategies[name]
            self.algorithm.Debug(f"Active trading strategy set to: {name}")
        else:
            self.algorithm.Debug(f"Strategy {name} not found!")
            
    def initialize_for_symbol(self, symbol):
        """Initialize all strategies for a symbol"""
        for strategy in self.strategies.values():
            strategy.initialize_indicators(symbol)
            
    def get_trading_signal(self, symbol, data):
        """Get trading signal from active strategy"""
        if self.active_strategy is None:
            return TradingSignal.HOLD
            
        return self.active_strategy.get_signal(symbol, data)
    
    def execute_trade(self, symbol, signal, data):
        """Execute trade based on signal"""
        if signal == TradingSignal.HOLD:
            return
            
        portfolio = self.algorithm.Portfolio
        
        if signal == TradingSignal.BUY and not portfolio[symbol].Invested:
            # Calculate position size (you can modify this logic)
            cash_per_position = portfolio.Cash / len(self.algorithm.ActiveSecurities)
            quantity = int(cash_per_position / data[symbol].Price)
            
            if quantity > 0:
                self.algorithm.MarketOrder(symbol, quantity)
                self.algorithm.Debug(f"BUY signal executed for {symbol}: {quantity} shares")
                
        elif signal == TradingSignal.SELL and portfolio[symbol].Invested:
            self.algorithm.Liquidate(symbol)
            self.algorithm.Debug(f"SELL signal executed for {symbol}")


def calculate_linear_weights(symbols):
    """
    Optimized linear weighting:
    - Best symbol gets 2x the weight of the worst
    - Linearly interpolated in between
    """
    n = len(symbols)
    if n <= 1:
        return [1.0]

    worst_weight = 2.0 / (3.0 * n)
    best_weight = 2.0 * worst_weight
    step = (best_weight - worst_weight) / (n - 1)
    weights = [best_weight - i * step for i in range(n)]
    total = sum(weights)
    return [w / total for w in weights]


class UniverseSelectionAlgorithm(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2025, 5, 1)
        self.SetCash(100000)
        self.SetBenchmark("SPY")

        # Screening parameters
        self.min_market_cap = 1e9
        self.min_volume = 1e6
        self.min_price = 50.0
        self.pe_ratio_min = 5
        self.debt_to_equity_max = 1.0
        self.roe_min = 0.10
        self.stop_loss = 0.07  # 7% trailing stop loss

        # Tracking state
        self.entryTickets = {}
        self.stopMarketTickets = {}
        self.entryTimes = {}
        self.highestPrices = {}
        self.stopMarketOrderFillTimes = {}

        # Initialize Trading Engine
        self.trading_engine = TradingEngine(self)
        
        # Add trading strategies
        bb_strategy = BollingerBandsStrategy(self, period=20, std_dev=2.0)
        sma_strategy = SMATraversalStrategy(self, fast_period=5, slow_period=20)
        
        self.trading_engine.add_strategy("bollinger", bb_strategy)
        self.trading_engine.add_strategy("sma_traversal", sma_strategy)
        
        # Set active strategy (change this to switch strategies)
        self.trading_engine.set_active_strategy("bollinger")  # or "sma_traversal"

        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)
        self.SetWarmup(timedelta(days=30))

        self.Schedule.On(
            self.DateRules.MonthStart(),
            self.TimeRules.At(9, 30),
            self.Rebalance
        )

    def OnWarmupFinished(self):
        self.Debug("Warmup completed. Trading logic now active.")

    def CoarseSelectionFunction(self, coarse):
        filtered = [x for x in coarse if x.HasFundamentalData and x.Price > self.min_price
                    and x.DollarVolume > self.min_volume and x.Market == Market.USA]
        sorted_by_volume = sorted(filtered, key=lambda x: x.DollarVolume, reverse=True)
        return [x.Symbol for x in sorted_by_volume[:500]]

    def FineSelectionFunction(self, fine):
        filtered = []
        for f in fine:
            try:
                if f.MarketCap < self.min_market_cap:
                    continue

                pe = f.ValuationRatios.PERatio
                if pe is None or pe <= self.pe_ratio_min:
                    continue

                equity = f.FinancialStatements.BalanceSheet.TotalEquity.Value
                debt = f.FinancialStatements.BalanceSheet.TotalDebt.Value
                if equity <= 0:
                    continue
                d2e = debt / equity
                if d2e > self.debt_to_equity_max:
                    continue

                roe = f.OperationRatios.ROE.OneYear
                if roe is None or roe < self.roe_min:
                    continue

                rev_growth = f.OperationRatios.RevenueGrowth.OneYear
                if rev_growth is None or rev_growth < 0:
                    continue

                liabilities = f.FinancialStatements.BalanceSheet.CurrentLiabilities.Value
                assets = f.FinancialStatements.BalanceSheet.CurrentAssets.Value
                if liabilities <= 0 or (assets / liabilities) < 1.0:
                    continue

                revenue = f.FinancialStatements.IncomeStatement.TotalRevenue.Value
                rd = f.FinancialStatements.IncomeStatement.ResearchAndDevelopment.Value
                rd_ratio = rd / revenue if revenue > 0 else 0

                gross_margin = f.OperationRatios.GrossMargin.Value

                # Skip invalid or incomplete records
                if any(x is None for x in [roe, rev_growth, pe, d2e, gross_margin, rd_ratio]):
                    continue

                # Feature vector
                filtered.append({
                    "symbol": f.Symbol,
                    "features": [
                        roe,
                        rev_growth,
                        1 / pe,
                        1 / (1 + d2e),
                        np.log(f.MarketCap + 1),
                        gross_margin,
                        rd_ratio
                    ]
                })
            except:
                continue

        if not filtered:
            return []

        # Normalize and score
        features_matrix = np.array([row["features"] for row in filtered])
        scaler = MinMaxScaler()
        X = scaler.fit_transform(features_matrix)

        weights = np.array([0.2, 0.25, 0.15, 0.05, 0.1, 0.05, 0.2])
        scores = X.dot(weights)

        # Attach scores
        for i, row in enumerate(filtered):
            row["score"] = scores[i]

        # Sort and return top 10 symbols
        top = sorted(filtered, key=lambda x: x["score"], reverse=True)[:10]
        selected = [row["symbol"] for row in top]
        self.Debug(f"Top 10 Selected: {[s.Value for s in selected]}")
        
        return selected

    def OnSecuritiesChanged(self, changes):
        # Initialize trading indicators for new securities
        for security in changes.AddedSecurities:
            self.trading_engine.initialize_for_symbol(security.Symbol)
            
        for security in changes.RemovedSecurities:
            self.Liquidate(security.Symbol)

    def Rebalance(self):
        symbols = list(self.ActiveSecurities.Keys)
        if not symbols:
            return

        # Get the latest slice (market data)
        slice = self.CurrentSlice

        # Filter for symbols that have up-to-date data
        tradable_symbols = [
            s for s in symbols
            if self.Securities[s].HasData and s in slice and slice[s] is not None and slice[s].Price > 0
        ]

        if not tradable_symbols:
            self.Debug("No tradable symbols with current price data.")
            return

        weights = calculate_linear_weights(tradable_symbols)
        for symbol, weight in zip(tradable_symbols, weights):
            self.SetHoldings(symbol, weight)

        self.Debug(f"Rebalanced with {len(tradable_symbols)} tradable stocks.")

    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status != OrderStatus.Filled:
            return

        symbol = orderEvent.Symbol

        if symbol in self.entryTickets and self.entryTickets[symbol].OrderId == orderEvent.OrderId:
            stop_price = (1 - self.stop_loss) * self.entryTickets[symbol].AverageFillPrice
            self.stopMarketTickets[symbol] = self.StopMarketOrder(symbol, -self.entryTickets[symbol].Quantity, stop_price)
            self.highestPrices[symbol] = self.entryTickets[symbol].AverageFillPrice
            del self.entryTickets[symbol]

        elif symbol in self.stopMarketTickets and self.stopMarketTickets[symbol].OrderId == orderEvent.OrderId:
            self.stopMarketOrderFillTimes[symbol] = self.Time
            self.highestPrices[symbol] = 0
            del self.stopMarketTickets[symbol]
            self.Debug(f"Stop loss filled for {symbol}, cooldown started")

    def OnData(self, data):
        if self.IsWarmingUp:
            return

        symbols = list(self.ActiveSecurities.Keys)
        
        # MODULAR TRADING LOGIC - Easy to switch strategies!
        for symbol in symbols:
            if symbol not in data or not data[symbol]:
                continue

            # Get trading signal from active strategy
            signal = self.trading_engine.get_trading_signal(symbol, data)
            
            # Execute trade based on signal
            if signal != TradingSignal.HOLD:
                self.trading_engine.execute_trade(symbol, signal, data)

        # Original stop-loss and order management logic
        for symbol in symbols:
            if symbol not in data or not data[symbol]:
                continue

            price = data[symbol].Price

            if symbol not in self.stopMarketOrderFillTimes:
                self.stopMarketOrderFillTimes[symbol] = self.Time - timedelta(days=31)

            if (self.Time - self.stopMarketOrderFillTimes[symbol]).days < 30:
                continue

            if (not self.Portfolio[symbol].Invested and
                symbol not in self.entryTickets and
                not self.Transactions.GetOpenOrders(symbol)):

                quantity = int((self.Portfolio.Cash / len(symbols)) / price)
                if quantity > 0:
                    self.entryTickets[symbol] = self.LimitOrder(symbol, quantity, price)
                    self.entryTimes[symbol] = self.Time

            if (symbol in self.entryTickets and
                symbol in self.entryTimes and
                (self.Time - self.entryTimes[symbol]).days > 1 and
                self.entryTickets[symbol].Status != OrderStatus.Filled):

                update = UpdateOrderFields()
                update.LimitPrice = price
                self.entryTickets[symbol].Update(update)
                self.entryTimes[symbol] = self.Time

            if (symbol in self.stopMarketTickets and
                self.Portfolio[symbol].Invested and
                price > self.highestPrices[symbol]):

                self.highestPrices[symbol] = price
                update = UpdateOrderFields()
                update.StopPrice = price * (1 - self.stop_loss)
                self.stopMarketTickets[symbol].Update(update)
