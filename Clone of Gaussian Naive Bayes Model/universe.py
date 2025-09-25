#region imports
from AlgorithmImports import *
#endregion

class BigTechUniverseSelectionModel(FundamentalUniverseSelectionModel):
    """
    This universe selection model contain the n largest securities in the technology sector.
    """
    
    def __init__(self, universe_settings, universe_size):
        """
        Input:
         - universe_size
            Maximum number of securities in the universe
        """
        super().__init__(self.select)
        self.universe_size = universe_size
        self.week = -1
        self.hours = None

    def select(self, fundamental):
        tech_stocks = [ f for f in fundamental if f.asset_classification.morningstar_sector_code == MorningstarSectorCode.TECHNOLOGY ]
        sorted_by_market_cap = sorted(tech_stocks, key=lambda x: x.market_cap, reverse=True)
        return [ x.symbol for x in sorted_by_market_cap[:self.universe_size] ]
