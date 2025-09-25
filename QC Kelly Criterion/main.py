# region imports
from AlgorithmImports import *
# endregion

class TradeStatisticsAlgorithm(QCAlgorithm):
    def initialize(self) -> None:
        self.set_start_date(2024, 12, 1)
        # self.set_end_date(2024, 4, 1)
        self.set_cash(100000)

        # Request SPY data to trade.
        self.spy = self.add_equity("SPY").symbol
        # Create an EMA indicator to generate trade signals.
        self._ema = self.ema(self.spy, 5, Resolution.HOUR)
        # Warm-up indicator for immediate readiness.
        self.warm_up_indicator(self.spy, self._ema, Resolution.HOUR)

        # Set up a trade builder to track the trade statistics; we are interested in open-to-close round trade.
        self.set_trade_builder(TradeBuilder(FillGroupingMethod.FLAT_TO_FLAT, FillMatchingMethod.FIFO))

    def on_data(self, slice: Slice) -> None:
        bar = slice.bars.get(self.spy)
        if not bar:
            return
        # Trend-following strategy using price and EMA.
        # If the price is above EMA, SPY is in an uptrend, and we buy it.
        sign = 0
        if bar.close > self._ema.current.value and not self.portfolio[self.spy].is_long:
            sign = 1
        elif bar.close < self._ema.current.value and not self.portfolio[self.spy].is_short:
            sign = -1
        else:
            return

        size = 1
        trades = self.trade_builder.closed_trades

        # This is sort of a momentum
        if len(trades) > 4: 
            # Use the trade builder to obtain the win rate and % return of the last five trades to calculate position size.
            last_five_trades = sorted(trades, key=lambda x: x.exit_time)[-5:]
            prob_win = len([x for x in last_five_trades if x.is_win]) / 5
            win_size = np.mean([x.profit_loss / x.entry_price for x in last_five_trades])
            # Use the Kelly Criterion to calculate the order size.
            size = max(0, prob_win - (1 - prob_win) / win_size)

        self.set_holdings(self.spy, size * sign)
