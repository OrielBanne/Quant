from AlgorithmImports import *
import math
from calendar import monthrange
from pytz import timezone


class SharpeBasedAthenaMultiSymbol(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2000, 1, 1)
        self.SetEndDate(2026, 1, 1)
        self.SetCash(100000)

        tickers = ["SPY", "SPLG", "SOXX", "IWB", "VV", "XLI", "IVE", "IWD", "SMH", 'QLD', 'EWT', 'VGT', 'XLK', 'VUG']
        tickerslev = ["TQQQ", "SOXL", "UPRO"]
        stocks = ['NFLX', 'MA', 'NVDA']
        tickers = tickers + tickerslev + stocks

        self.SetWarmUp(timedelta(hours=750))
        self.SetBrokerageModel(BrokerageName.Alpaca, AccountType.Margin)

        self.max_leverage_for_account = 2
        self.leverage = 2
        self.MAX_WEIGHT = 0.3 * self.leverage

        self.symbols = []
        for ticker in tickers:
            security = self.AddEquity(ticker, Resolution.Hour)
            if security:
                self.Debug(f"Added {ticker}")
                security.SetLeverage(self.max_leverage_for_account)
                self.symbols.append(security.Symbol)
            else:
                self.Debug(f"Failed to add {ticker}")

        self.yearly_returns = {s: [] for s in self.symbols}
        self.yearly_prices = {s: None for s in self.symbols}
        self.excluded_symbols = set()

        self.per = 518
        self.mult = 1.0
        self.lookback = 30

        self.price_windows = {s: RollingWindow[float](self.per + 2) for s in self.symbols}
        self.last_filts = {s: None for s in self.symbols}
        self.upward = {s: 0 for s in self.symbols}
        self.downward = {s: 0 for s in self.symbols}
        self.return_windows = {s: RollingWindow[float](self.lookback) for s in self.symbols}
        self.last_prices = {s: None for s in self.symbols}

        self.annual_margin_rate = 0.07
        self.monthly_interest_accrued = 0
        self.last_interest_month = self.Time.month

        self.pending_orders = []
        self.ready_to_trade = False

    def OnWarmupFinished(self):
        self.Debug("Warm-up complete.")
        self.ready_to_trade = True


    def OnData(self, data: Slice):
        if not self.ready_to_trade:
            self.Debug("Still warming up...")
            return

        
        
        self.Debug(f"Is Market Open {self.get_market_status('SPY')}")

        if self.Time.minute % 30 == 0:
            self.Debug(f"Time: {self.Time}, MarginRemaining: {self.Portfolio.MarginRemaining:.2f}")

        if self.pending_orders:
            self.Debug(f"Pending orders: {len(self.pending_orders)} at {self.Time}")
            
            # Iterate over a copy so we can safely modify the original list
            for order in self.pending_orders[:]:
                symbol, quantity, weight, price, side = order

                # Only execute if market is open
                if self.get_market_status(symbol) == True:
                    self.Debug(f"-> Executing {side.upper()} {symbol.Value} qty={quantity}")

                    if side == 'long':
                        self.MarketOrder(symbol, quantity)
                    elif side == 'flat':
                        self.Liquidate(symbol)

                    # Remove this order from the pending list
                    self.pending_orders.remove(order)

        sharpe_scores = {}
        profitable = set()

        for symbol in self.symbols:
            if not data.Bars.ContainsKey(symbol):
                self.Debug(f"No data for {symbol.Value}")
                continue
            if symbol in self.excluded_symbols:
                continue

            bar = data[symbol]
            src = (bar.High + bar.Low) / 2
            self.price_windows[symbol].Add(src)

            last_close = self.last_prices[symbol]
            if last_close is not None and last_close > 0:
                ret = math.log(bar.Close / last_close)
                self.return_windows[symbol].Add(ret)
            self.last_prices[symbol] = bar.Close

            if not self.price_windows[symbol].IsReady or not self.return_windows[symbol].IsReady:
                continue

            window = self.price_windows[symbol]
            price_diffs = [abs(window[i] - window[i - 1]) for i in range(1, self.per + 1)]
            avg_range = sum(price_diffs) / len(price_diffs)
            filt = self.rngfilt(src, avg_range * self.mult, self.last_filts[symbol])
            self.last_filts[symbol] = filt

            if filt is None:
                continue

            if src > filt:
                self.upward[symbol] += 1
                self.downward[symbol] = 0
            elif src < filt:
                self.downward[symbol] += 1
                self.upward[symbol] = 0

            returns = list(self.return_windows[symbol])
            cumulative_ret = sum(returns)
            if cumulative_ret <= 0:
                self.Debug(f"{symbol.Value}: Negative return, skipping")
                continue

            profitable.add(symbol)

            mean_ret = cumulative_ret / len(returns)
            std_dev = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns))
            if std_dev > 0:
                sharpe = mean_ret / std_dev
                sharpe_scores[symbol] = sharpe
                self.Debug(f"{symbol.Value} Sharpe: {sharpe:.4f}")

        if not sharpe_scores:
            self.Debug("No sharpe scores, skipping...")
            return

        total_score = sum(max(0, s) for s in sharpe_scores.values())
        if total_score == 0:
            self.Debug("Total sharpe score is 0.")
            return

        raw_allocations = {
            s: max(0, sharpe_scores[s]) / total_score
            for s in sharpe_scores if s in profitable
        }

        allocations = {s: w for s, w in raw_allocations.items() if w >= 1e-4}
        allocations = {s: min(w, self.MAX_WEIGHT) for s, w in allocations.items()}

        portfolio_value = self.Portfolio.TotalPortfolioValue
        available_margin = self.Portfolio.MarginRemaining
        if portfolio_value == 0:
            self.Debug("Portfolio value is 0!")
            return

        max_total_allocation = min(available_margin / portfolio_value, self.leverage)
        total_alloc = sum(allocations.values())
        if total_alloc == 0:
            self.Debug("Final allocations sum to zero, skipping trades.")
            return

        scaling_factor = min(1.0, max_total_allocation / total_alloc)
        allocations = {s: w * scaling_factor for s, w in allocations.items()}

        for symbol in self.symbols:
            if not data.Bars.ContainsKey(symbol) or symbol not in profitable:
                continue

            if not self.price_windows[symbol].IsReady or self.last_filts[symbol] is None:
                continue

            src = self.price_windows[symbol][0]
            filt = self.last_filts[symbol]
            long_condition = src > filt and self.upward[symbol] > 0
            short_condition = src < filt and self.downward[symbol] > 0
            invested = self.Portfolio[symbol].Invested

            self.Debug(f"{symbol.Value}: long={long_condition}, short={short_condition}, invested={invested}")

            if not invested and long_condition and symbol in allocations:
                weight = self.leverage * allocations[symbol]
                target_value = weight * portfolio_value
                price = self.Securities[symbol].Price
                quantity = int(target_value / price)

                if quantity > 0:
                    required_margin = price * quantity / self.Securities[symbol].Leverage
                    if available_margin >= required_margin:
                        if self.get_market_status(symbol) == False:
                            self.pending_orders.append((symbol, quantity, weight, price, 'long'))
                            self.Debug(f"Queued LONG {symbol.Value} qty={quantity}")
                        else:
                            self.Debug(f"MarketOrder LONG {symbol.Value} qty={quantity}")
                            self.MarketOrder(symbol, quantity)

            elif invested and short_condition:
                if self.get_market_status(symbol) == False:
                    quantity = -self.Portfolio[symbol].Quantity
                    price = self.Securities[symbol].Price
                    self.pending_orders.append((symbol, quantity, 0, price, 'flat'))
                    self.Debug(f"Queued SELL {symbol.Value} qty={quantity}")
                else:
                    self.Debug(f"Liquidate {symbol.Value}")
                    self.Liquidate(symbol)

    def rngfilt(self, x, r, prev_filt):
        if prev_filt is None:
            return x
        if x > prev_filt:
            return prev_filt if x - r < prev_filt else x - r
        else:
            return prev_filt if x + r > prev_filt else x + r


    def get_market_status(self, symbol):
        now = self.Time

        # Access the correct Security object from self.Securities
        security = self.Securities[symbol]

        is_open_regular = security.Exchange.Hours.IsOpen(now, extendedMarketHours=False)
        is_open_extended = security.Exchange.Hours.IsOpen(now, extendedMarketHours=True)

        if is_open_regular:
            return True
        elif is_open_extended:
            return False
        else:
            return False

        
    def OnEndOfDay(self):
        holdings_value = self.Portfolio.TotalHoldingsValue
        portfolio_value = self.Portfolio.TotalPortfolioValue
        borrowed = max(0, holdings_value - portfolio_value)
        daily_interest = borrowed * (self.annual_margin_rate / 252)
        self.monthly_interest_accrued += daily_interest

        last_day = monthrange(self.Time.year, self.Time.month)[1]
        if self.Time.day == last_day:
            self.Portfolio.SetCash(self.Portfolio.Cash - self.monthly_interest_accrued)
            self.Debug(f"Monthly interest charged: ${self.monthly_interest_accrued:.2f}")
            self.monthly_interest_accrued = 0

        if self.Time.month == 12 and self.Time.day == 31:
            for symbol in self.symbols:
                if symbol not in self.Securities:
                    continue

                price = self.Securities[symbol].Price
                last_price = self.yearly_prices[symbol]

                if last_price is not None and last_price > 0:
                    yearly_return = (price - last_price) / last_price
                    self.yearly_returns[symbol].append(yearly_return)

                    if len(self.yearly_returns[symbol]) >= 2:
                        if self.yearly_returns[symbol][-1] < 0 and self.yearly_returns[symbol][-2] < 0:
                            self.excluded_symbols.add(symbol)
                            if not self.IsWarmingUp:
                                self.Liquidate(symbol)
                                self.Debug(f"Excluded {symbol.Value} due to 2 bad years")

                self.yearly_prices[symbol] = price
