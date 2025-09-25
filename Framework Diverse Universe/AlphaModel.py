# region imports
from AlgorithmImports import *
# endregion

# Your New Python File
class FundamentalFactorAlphaModel(AlphaModel):
    
    def __init__(self):
        self.rebalanceTime = datetime.min
        # Dictionary containing set of securities in each sector
        # e.g. {technology: set(AAPL, TSLA, ...), healthcare: set(XYZ, ABC, ...), ... }
        self.sectors = {}

    def Update(self, algorithm, data):
        '''Updates this alpha model with the latest data from the algorithm.
        This is called each time the algorithm receives data for subscribed securities
        Args:
            algorithm: The algorithm instance
            data: The new data available
        Returns:
            New insights'''

        if algorithm.Time <= self.rebalanceTime:
            return []
        
        # Set the rebalance time to match the insight expiry
        self.rebalanceTime = Expiry.EndOfQuarter(algorithm.Time)
        
        insights = []
        
        for sector in self.sectors:
            securities = self.sectors[sector]
            sortedByROE = sorted(securities, key=lambda x: x.Fundamentals.OperationRatios.ROE.Value, reverse=True)
            sortedByPM = sorted(securities, key=lambda x: x.Fundamentals.OperationRatios.NetMargin.Value, reverse=True)
            sortedByPE = sorted(securities, key=lambda x: x.Fundamentals.ValuationRatios.PERatio, reverse=False)

            # Dictionary holding a dictionary of scores for each security in the sector
            scores = {}
            for security in securities:
                symbol = security.Symbol

                # Ensure we have data for the symbol
                if symbol not in data.Bars:
                    continue  # Skip if no bar data

                if not security.HasData or data[symbol] is None or data[symbol].Price == 0:
                    continue
                
                score = sum([sortedByROE.index(security), sortedByPM.index(security), sortedByPE.index(security)])
                scores[security] = score
                
            # Add best 20% of each sector to longs set (minimum 1)
            length = max(int(len(scores)/5), 1)
            for security in sorted(scores.items(), key=lambda x: x[1], reverse=False)[:length]:
                symbol = security[0].Symbol
                # Use Expiry.EndOfQuarter in this case to match Universe, Alpha and PCM
                insights.append(Insight.Price(symbol, Expiry.EndOfQuarter, InsightDirection.Up))
        
        return insights

    def OnSecuritiesChanged(self, algorithm, changes):
        '''Event fired each time the we add/remove securities from the data feed
        Args:
            algorithm: The algorithm instance that experienced the change in securities
            changes: The security additions and removals from the algorithm'''
        
        # Remove security from sector set
        for security in changes.RemovedSecurities:
            for sector in self.sectors:
                if security in self.sectors[sector]:
                    self.sectors[sector].remove(security)
        
        # Add security to corresponding sector set
        for security in changes.AddedSecurities:
            sector = security.Fundamentals.AssetClassification.MorningstarSectorCode
            if sector not in self.sectors:
                self.sectors[sector] = set()
            self.sectors[sector].add(security)
