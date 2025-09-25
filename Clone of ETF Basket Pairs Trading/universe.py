#region imports
from AlgorithmImports import *
#endregion

class SectorETFUniverseSelectionModel(ETFConstituentsUniverseSelectionModel):
    def __init__(self, universe_settings: UniverseSettings = None) -> None:
        # Select the tech sector ETF constituents to get correlated assets
        symbol = Symbol.create("IYM", SecurityType.EQUITY, Market.USA)
        super().__init__(symbol, universe_settings, self.etf_constituents_filter)

    def etf_constituents_filter(self, constituents: List[ETFConstituentData]) -> List[Symbol]:
        # Get the 10 securities with the largest weight in the index to reduce slippage and keep speed of the algorithm
        selected = sorted([c for c in constituents if c.weight], 
                          key=lambda c: c.weight, reverse=True)
        return [c.symbol for c in selected[:10]]
