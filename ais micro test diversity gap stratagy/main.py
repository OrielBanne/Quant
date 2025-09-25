from AlgorithmImports import *

class SymbolData:
    def __init__(self, symbol):
        self.symbol = symbol
        self.bar_data = pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        self.lower_threshold = 0.2
        self.upper_threshold = 0.8
        self.last_recalibrate_time = datetime.min
        self.consolidator = None

class IBSMultiAssetCrypto15Min(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2025, 1, 1)
        self.SetCash(100000)
        self.set_brokerage_model(BrokerageName.KRAKEN, AccountType.CASH)


        self.tickers = ['BTCUSD','SOLUSD','XRPUSD','ETHUSD']
        #self.tickers = ['BTCUSD']
        self.symbol_data = {}
        self.lookback_bars = 96  # Approx 1 day of 15-min bars
        self.SetWarmUp(timedelta(days=2))  # Enough for 2 days of 15-min bars

        for ticker in self.tickers:
            symbol = self.AddCrypto(ticker, Resolution.Minute, Market.Kraken).Symbol
            sym_data = SymbolData(symbol)
            self.symbol_data[symbol] = sym_data

            # ✅ Disable trading fees
            self.Securities[symbol].FeeModel = ConstantFeeModel(0)

            consolidator = TradeBarConsolidator(timedelta(minutes=15))
            consolidator.DataConsolidated += self.OnBar
            self.SubscriptionManager.AddConsolidator(symbol, consolidator)
            sym_data.consolidator = consolidator
    
    
    def CalculateOrderQuantityFromDollar(self, symbol, dollar_amount):
        price = self.Securities[symbol].Price
        if price > 0:
            return dollar_amount / price
        return 0

    

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

    def algo_status_debug(self):
        if not self.IsWarmingUp:

            positions = []
            for kvp in self.Portfolio:
                symbol = kvp.Key
                holding = kvp.Value
                if holding.Invested:
                    ticker = symbol.Value
                    avg_price = holding.AveragePrice
                    positions.append(f"{ticker}: ${avg_price:.2f}")

            self.Debug(f"Current Positions: [{', '.join(positions)}]")


    def OnBar(self, sender, bar: TradeBar):

        self.algo_status_debug()
        if self.IsWarmingUp:
            return

        sym_data = self.symbol_data[bar.Symbol]

        new_row = {
            'time': bar.EndTime,
            'open': bar.Open,
            'high': bar.High,
            'low': bar.Low,
            'close': bar.Close,
            'volume': bar.Volume
        }

        sym_data.bar_data = pd.concat([sym_data.bar_data, pd.DataFrame([new_row])], ignore_index=True)
        sym_data.bar_data = sym_data.bar_data.tail(500).reset_index(drop=True)

        if bar.High == bar.Low:
            return

        ibs = (bar.Close - bar.Low) / (bar.High - bar.Low)

 

        invested = self.Portfolio[bar.Symbol].Invested
        target_pct = 1.0 / len(self.symbol_data)

        if ibs < sym_data.lower_threshold and not invested:
            quantity = self.CalculateOrderQuantityFromDollar(bar.Symbol, 20000)
            self.MarketOrder(bar.Symbol, quantity)
        elif ibs >= sym_data.upper_threshold and invested:
            self.Liquidate(bar.Symbol)

        self.Debug(f"{self.Time} | {bar.Symbol.Value} | IBS: {ibs:.2f} | LT: {sym_data.lower_threshold:.2f} | UT: {sym_data.upper_threshold:.2f} | Invested: {invested}")

