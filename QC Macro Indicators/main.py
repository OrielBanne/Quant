# region imports
from AlgorithmImports import *
# endregion

class EODHDMacroIndicatorsAlgorithm(QCAlgorithm):
    def Initialize(self):
        self.set_start_date(2020, 10, 7)
        self.equity_symbol = self.add_equity("SPY", Resolution.DAILY).symbol

        ticker = EODHD.MacroIndicators.UnitedStates.GDP_GROWTH_ANNUAL
        
        self.dataset_symbol = self.add_data(EODHDMacroIndicators, ticker).Symbol

    def OnData(self, slice):
        indicators = slice.get(EODHDMacroIndicators).get(self.dataset_symbol)
        if indicators:
            gdp = indicators.data[0].value
            self.set_holdings(self.equity_symbol, 1 if gdp > 0 else -1)
