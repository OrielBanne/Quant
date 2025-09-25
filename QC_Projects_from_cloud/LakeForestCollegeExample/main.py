from AlgorithmImports import *
from Indicators import CustomBollingerBands, RSIIndicator, HistoricalVolatility, TrendFilter
from AssetStrategy import AssetArbitrageStrategy

class VolatilityArbitrage(QCAlgorithm):
    def Initialize(self):
        self.set_start_date(2021, 10, 1)
        # self.SetEndDate(2023, 12, 31)
        self.set_cash(100000)

        # Add cryptocurrencies
        self.crypto_symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
        for crypto in self.crypto_symbols:
            self.add_crypto(crypto, Resolution.DAILY)

        # Universe selection for 100 stocks
        self.add_universe(self.CoarseSelectionFunction)

        # Extended warm-up period for better historical volatility data
        self.set_warmup(timedelta(days=60))

        self.symbol_data = {}

    def CoarseSelectionFunction(self, coarse):
        # Select liquid equities with price > $20 and sort by dollar volume in descending order
        filtered = [x for x in coarse if x.Price > 20 and x.DollarVolume > 1e7]
        sorted_by_volume = sorted(filtered, key=lambda x: x.DollarVolume, reverse=True)
        selected = [x.Symbol for x in sorted_by_volume[:100]]  # Top 100 stocks
        return selected + self.crypto_symbols  # Add cryptos to the universe

    def OnSecuritiesChanged(self, changes):
        for added in changes.AddedSecurities:
            symbol = added.Symbol
            if symbol not in self.symbol_data:
                self.symbol_data[symbol] = {
                    "indicators": {
                        "contrarian_bands": CustomBollingerBands(self, symbol),
                        "rsi": RSIIndicator(self, symbol),
                        "hist_vol": HistoricalVolatility(self, symbol),
                        "trend": TrendFilter(self, symbol)
                    },
                    "strategy": AssetArbitrageStrategy(self, symbol)
                }

        for removed in changes.RemovedSecurities:
            symbol = removed.Symbol
            if symbol in self.symbol_data:
                del self.symbol_data[symbol]

    def OnData(self, data):
        if self.is_warming_up:
            return

        for symbol, data_set in self.symbol_data.items():
            if symbol in data:
                indicators = data_set["indicators"]
                indicators["contrarian_bands"].Update(data)
                indicators["rsi"].Update(data)
                indicators["hist_vol"].Update(data)
                indicators["trend"].Update(data)
                data_set["strategy"].Execute(indicators)
