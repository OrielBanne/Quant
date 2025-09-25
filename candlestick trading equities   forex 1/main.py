# region imports
from AlgorithmImports import *
# endregion

class CreativeApricotShark(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 8, 28)
        # self.set_end_date(2024, 12, 30)
        self.set_cash(100000)
        #self.AddEquity("SPY", Resolution.Daily)
        self.tickers = ['NVDA','AAPL','MSFT','GOOGL','AMZN', 'META','TSLA', 'SPY']#: 287% # winners
        #self.tickers = ['XOM','JNJ','KO','MCD', 'MDT','SHW', 'CTAS'] #182.98 % # high dividend
        # self.tickers = ['FIVE','GPCR','STRL','NVMI', 'ONTO','ASML', 'VKTX'] # losers: 1,050.50 %
        self.candles = {}
        self.percent = 0.25
        self.open_positions = []

        # Positions to keep track of the short positions we enter
        self.open_short_positions = []

        
        self.transactions_history = pd.DataFrame(columns=['Date', 'Stock', 'Type of Transaction', 'Candle', 'Buy Price', 'Qty', 'Sell Price', 'Buy Price', 'P/L'])
        
        # determines the investment percentage of the totalCash
        self.percent = 0.05

        # We are also going to have a stop-loss metric associated with each position
        # to reduce the drawdown
        self.stop_loss_threshold = -0.2

        # We will see if trailing stop loss works better
        self.trailing_stop_loss_percent = 0.2

       
        self.set_warm_up(2, Resolution.DAILY)

        # # Initialize moving averages
        for ticker in self.tickers:
            equity = self.add_equity(ticker, Resolution.DAILY)
            self.candles[ticker] = Candle(self, ticker)
            
        #     # Create the moving averages
        #     self.fast_moving_averages[ticker] = self.SMA(ticker, 50, Resolution.Daily)
        #     self.slow_moving_averages[ticker] = self.SMA(ticker, 200, Resolution.Daily)

        #     self.mv_state[ticker] = None  # Initialize the state to None

        

    def OnData(self, data):
        if self.IsWarmingUp:
            return
        # self.debug('Here')
        for ticker, candle in self.candles.items():
            if ticker not in data.Bars:
                self.debug(ticker)
                continue
            bar = data.Bars[ticker]
            candle.Update(bar)

            #######################################################
            #                                                     #
            #                   LONG                              #
            #                POSITIONS                            #
            #                                                     #
            #######################################################

            if candle.shouldExit():
                self.close_positions([position for position in self.open_positions if position['Stock'] == ticker], data[ticker].Close, 'SELL', candleStick=candle.getPatternName())
            elif candle.shouldEnter():
                portfolio_value = self.Portfolio.TotalPortfolioValue
                allocation = portfolio_value * self.percent  # Allocate self.percent of portfolio value to each position
                quantity = allocation // data[ticker].Close
                # quantity = (10000 / data[ticker].Close + 1)
                self.Debug(f"Buying {quantity} shares of {ticker} at {data[ticker].Close} on {self.Time}")
                self.MarketOrder(ticker, quantity)
                self.open_positions.append(
                    {'Date': self.Time, 
                    'Qty': quantity, 
                    'Buy Price': data[ticker].Close, 
                    'Stock': ticker, 
                    'Paper P/L': 0, 
                    'Paper P/L %': 0,
                    'TrailingStopLoss': data[ticker].Close * (1 - self.trailing_stop_loss_percent)
                    }
                )
            
            #######################################################
            #                                                     #
            #                  SHORT                              #
            #                POSITIONS                            #
            #                                                     #
            #######################################################
            #We will also look at entering/exiting short positions:
            if candle.shouldExitShortPositions():
                # Exiting short positions
                self.Debug(f"Exiting the short position for the stock :{ticker}")
                self.close_positions([position for position in self.open_short_positions if position['Stock'] == ticker], data[ticker].Close, 'BUY TO COVER', candleStick=candle.getPatternName())
            elif candle.shouldEnterShortPositions():
                # Enter the short positions:
                self.Debug(f"Entering the short position for the stock :{ticker}")
                portfolio_value = self.Portfolio.TotalPortfolioValue
                allocation = portfolio_value * self.percent  # Allocate self.percent of portfolio value to each position
                quantity = allocation // data[ticker].Close
                self.MarketOrder(ticker, -quantity)
                self.open_short_positions.append(
                    {'Date': self.Time, 
                    'Qty': quantity, 
                    'Sell Price': data[ticker].Close, 
                    'Stock': ticker, 
                    'Paper P/L': 0, 
                    'Paper P/L %': 0,
                    'TrailingStopLoss': data[ticker].Close * (1 + self.trailing_stop_loss_percent)
                    }
                )

        # Everyday we will calculate the Paper profit of each open position
        self.calculate_paper_pl(data)

        # Everyday we will also need to calculate the Paper Profit of each open short positions

        # Each day we will calculate to see if our stop-loss thresholf is being hit
        # self.check_stop_loss(data)
        # Each day we will calculate to see if our trailing stop-loss thresholf is being hit
        self.check_trailing_stop_loss(data)

        #self.check_and_sell_every_30_days(data)

        
    def close_positions(self, open_positions, price, heading, candleStick=""):
        '''
            We sell 25% of each open position whenever our exit position candle occurs
        '''
        for o in open_positions:
            qty = o['Qty']
            sellQty = self.percent * qty
            if qty <= 4:
                sellQty = qty

            leftQty = qty - sellQty

            if heading == 'SELL':  # Closing long positions
                paperValue = sellQty * price 
                PL = paperValue - sellQty * o['Buy Price']
            elif heading == 'BUY TO COVER':  # Closing short positions
                paperValue = sellQty * o['Sell Price']
                PL = paperValue - sellQty * price

            # paperValue = sellQty * price 
            # PL = paperValue - sellQty * o['Buy Price']

            transaction = {
                'Date': o["Date"],
                'Stock': o['Stock'],
                'Type of Transaction': heading,
                'Candle': candleStick,
                'Buy Price' if heading == 'SELL' else 'Sell Price': o['Buy Price'] if heading == 'SELL' else o['Sell Price'],
                'Sell Price' if heading == 'SELL' else 'Buy Price': price,
                'Qty': sellQty,
                'P/L': PL
            }
            #self.Debug(f"{transaction}")
            #transaction = {'Date': o["Date"], 'Stock' : o['Stock'],'Type of Transaction' : heading, 'Candle': candleStick, 'Buy Price' : o['Buy Price'], 'Sell Price' : price, 'Qty': sellQty , 'P/L': PL}
            self.transactions_history.loc[len(self.transactions_history)] = transaction
            #self.Debug(f"Transacton {transaction}")

            if heading == 'SELL':
                self.MarketOrder(o['Stock'], -sellQty)  # Selling for long position
                self.open_positions = [o for o in open_positions if o['Qty'] > 0]
            elif heading == 'BUY TO COVER':
                self.MarketOrder(o['Stock'], sellQty)   # Buying to cover short position
                self.open_short_positions = [o for o in open_positions if o['Qty'] > 0]
        
            o['Qty'] = leftQty
            # self.MarketOrder(o['Stock'], -sellQty)
            # o['Qty'] = leftQty
        
        
    
    # def close_short_positions(self, open_short_positions, price, heading, candleStick = ""):
    #     '''
    #         We sell 25% of each open short position whenever our exit position candle occurs
    #     '''
    #     for o in open_short_positions:
    #         qty = abs(o['Qty'])
    #         sellQty = self.percent * qty
    #         if qty <= 4:
    #             sellQty = qty

    #         leftQty = qty - sellQty
    #         paperValue = sellQty * price 
    #         PL = paperValue - sellQty * o['Buy Price']
    #         transaction = {'Date': o["Date"], 'Stock' : o['Stock'],'Type of Transaction' : heading, 'Candle': candleStick, 'Buy Price' : o['Buy Price'], 'Sell Price' : price, 'Qty': sellQty , 'P/L': PL}
    #         self.transactions_history.loc[len(self.transactions_history)] = transaction
    #         #self.Debug(f"Transacton {transaction}")
    #         self.MarketOrder(o['Stock'], -sellQty)
    #         o['Qty'] = leftQty
        
    #     self.open_positions = [o for o in open_positions if o['Qty'] > 0]
    


    def calculate_paper_pl(self, data):
        '''
            We regularly take out profits, if a current open position has a unrealized profit of greater than 30%
        '''

        #######################################################
        #                                                     #
        #                   LONG                              #
        #                POSITIONS                            #
        #                                                     #
        #######################################################

        getProfit = []
        for position in self.open_positions:
            ticker = position['Stock']
            if ticker not in data.Bars:
                continue

            # Calculating the paper profit
            price = data.Bars[ticker].Open
            qty = position['Qty']
            paperValue = qty * price
            paperPL = paperValue - qty * position['Buy Price']
            paperPLPercentage = paperPL / (qty * position['Buy Price'])

            if paperPLPercentage > 0.3:
                # Selling 25% of the position if paper profit is > 30%
                sellQty = 0.25 * qty
                if qty <= 4:
                    sellQty = qty
                position['Qty'] -= sellQty
                transaction = {'Date': self.Time, 'Stock': ticker, 'Type of Transaction': 'SELL FRAC', 'Buy Price': position['Buy Price'],
                               'Sell Price': price, 'Qty': sellQty, 'P/L': paperPL * (sellQty / qty)}
                getProfit.append(transaction)
        
        for transaction in getProfit:
            ticker = transaction['Stock']
            self.transactions_history.loc[len(self.transactions_history)] = transaction
            #self.Debug(f"Transacton {transaction}")
            #self.transactions_history = self.transactions_history.append(transaction, ignore_index=True)
            # Selling a part of the position
            self.MarketOrder(ticker, -transaction['Qty'])  

        self.open_positions = [p for p in self.open_positions if p['Qty'] > 0]

        #######################################################
        #                                                     #
        #                  SHORT                              #
        #                POSITIONS                            #
        #                                                     #
        #######################################################
        getProfit = []
        for position in self.open_short_positions:
            ticker = position['Stock']
            if ticker not in data.Bars:
                continue

            # Calculating the paper profit
            price = data.Bars[ticker].Open
            qty = position['Qty']
            paperValue = qty * position['Sell Price']
            paperPL = paperValue - qty * price
            paperPLPercentage = paperPL / (qty * position['Sell Price'])

            if paperPLPercentage > 0.3:
                # Selling 25% of the position if paper profit is > 30%
                sellQty = 0.25 * qty
                self.Debug(f"Selling {sellQty} stocks of {position['Stock']} from {position['Qty']}")
                if qty <= 4:
                    sellQty = qty
                position['Qty'] -= sellQty
                transaction = {
                    'Date': self.Time,
                    'Stock': ticker,
                    'Type of Transaction': 'BUY TO COVER FRAC',
                    'Sell Price': position['Sell Price'],
                    'Buy Price': price,  # For short positions, Sell Price is the opening price
                    'Qty': sellQty,
                    'P/L': paperPL * (sellQty / qty)
                }
                getProfit.append(transaction)
        
        for transaction in getProfit:
            ticker = transaction['Stock']
            self.transactions_history.loc[len(self.transactions_history)] = transaction
            #self.Debug(f"Transacton {transaction}")
            #self.transactions_history = self.transactions_history.append(transaction, ignore_index=True)
            # Selling a part of the position
            self.MarketOrder(ticker, transaction['Qty'])  

        self.open_short_positions = [p for p in self.open_short_positions if p['Qty'] > 0]

    def check_stop_loss(self, data):
        '''
            This function iterates through all the open positions and liquidates
            the entire position if our stop-loss is hit
        '''

        positions_to_liquidate = []
        for position in self.open_positions:
            ticker = position['Stock']
            if ticker not in data.Bars:
                continue

            price = data.Bars[ticker].Open
            qty = position['Qty']
            paperValue = qty * price
            paperPL = paperValue - qty * position['Buy Price']
            paperPLPercentage = paperPL / (qty * position['Buy Price'])

            if paperPLPercentage <= self.stop_loss_threshold:
                self.Debug(f"Stop loss hit for position: {position}, current price = {price}, loss = {paperPL} ,loss per = {paperPLPercentage}")
                positions_to_liquidate.append(position)
        
        for position in positions_to_liquidate:
            ticker = position['Stock']
            # Liquidating the entire position
            self.MarketOrder(ticker, -qty)
            #self.close_positions([position], data[ticker].Close, 'STOP LOSS')
            # We need to remove the position from open positions since we have liquidated
            # the entire position
            self.open_positions.remove(position)
    
    def check_trailing_stop_loss(self, data):
        '''
            This function iterates through all the open positions and liquidates
            the entire position if our trailing stop-loss is hit
        '''

        #######################################################
        #                                                     #
        #                   LONG                              #
        #                POSITIONS                            #
        #                                                     #
        #######################################################


        positions_to_liquidate = []
        for position in self.open_positions:
            ticker = position['Stock']
            if ticker not in data.Bars:
                continue

            price = data.Bars[ticker].Open
            qty = position['Qty']

            # Update trailing stop loss if current price is higher than the previous highest price
            if price > position['TrailingStopLoss'] / (1 - self.trailing_stop_loss_percent):
                position['TrailingStopLoss'] = price * (1 - self.trailing_stop_loss_percent)

            # Check if current price hits trailing stop loss
            if price <= position['TrailingStopLoss']:
                self.Debug(f"Trailing stop loss hit for {ticker} at {price}")
                positions_to_liquidate.append(position)
                continue

            paperValue = qty * price
            paperPL = paperValue - qty * position['Buy Price']
            paperPLPercentage = paperPL / (qty * position['Buy Price'])

            if paperPLPercentage <= self.stop_loss_threshold:
                self.Debug(f"Stop loss hit for position: {position}, current price = {price}, loss = {paperPL} ,loss per = {paperPLPercentage}")
                positions_to_liquidate.append(position)
        
        for position in positions_to_liquidate:
            ticker = position['Stock']
            # Liquidating the entire position
            self.MarketOrder(ticker, -qty)
            #self.close_positions([position], data[ticker].Close, 'STOP LOSS')
            # We need to remove the position from open positions since we have liquidated
            # the entire position
            self.open_positions.remove(position)
        

        #######################################################
        #                                                     #
        #                  SHORT                              #
        #                POSITIONS                            #
        #                                                     #
        #######################################################
        positions_to_liquidate = []
        # Check short positions
        for position in self.open_short_positions:
            ticker = position['Stock']
            if ticker not in data.Bars:
                continue

            price = data.Bars[ticker].Open
            qty = position['Qty']

            # Update trailing stop loss if current price is lower than the previous lowest price
            if price < position['TrailingStopLoss'] / (1 + self.trailing_stop_loss_percent):
                position['TrailingStopLoss'] = price * (1 + self.trailing_stop_loss_percent)

            # Check if current price hits trailing stop loss
            if price >= position['TrailingStopLoss']:
                self.Debug(f"Trailing stop loss hit for short position {ticker} at {price}")
                positions_to_liquidate.append(position)
                continue

        # Liquidate short positions that hit the trailing stop loss
        for position in positions_to_liquidate:
            ticker = position['Stock']
            qty = position['Qty']
            self.MarketOrder(ticker, qty)  # Buying back to cover the short position
            self.open_short_positions.remove(position)

'''
def check_trailing_stop_loss(self, data):
       

        #######################################################
        #                                                     #
        #                   LONG                              #
        #                POSITIONS                            #
        #                                                     #
        #######################################################


        positions_to_liquidate = []
        for position in self.open_positions:
            ticker = position['Stock']
            if ticker not in data.Bars:
                continue

            price = data.Bars[ticker].Open
            qty = position['Qty']

            # Update trailing stop loss if current price is higher than the previous highest price
            if price > position['TrailingStopLoss'] / (1 - self.trailing_stop_loss_percent):
                position['TrailingStopLoss'] = price * (1 - self.trailing_stop_loss_percent)

            # Check if current price hits trailing stop loss
            if price <= position['TrailingStopLoss']:
                self.Debug(f"Trailing stop loss hit for {ticker} at {price}")
                positions_to_liquidate.append(position)
                continue

            paperValue = qty * price
            paperPL = paperValue - qty * position['Buy Price']
            paperPLPercentage = paperPL / (qty * position['Buy Price'])

            if paperPLPercentage <= self.stop_loss_threshold:
                self.Debug(f"Stop loss hit for position: {position}, current price = {price}, loss = {paperPL} ,loss per = {paperPLPercentage}")
                positions_to_liquidate.append(position)
        
        for position in positions_to_liquidate:
            ticker = position['Stock']
            # Liquidating the entire position
            self.MarketOrder(ticker, -qty)
            #self.close_positions([position], data[ticker].Close, 'STOP LOSS')
            # We need to remove the position from open positions since we have liquidated
            # the entire position
            self.open_positions.remove(position)
'''



class Candle:
    def __init__(self, algorithm, ticker, frac=0.9):
        self.algorithm = algorithm
        self.ticker = ticker
        self.frac = frac
        self.bb = BollingerBands(20, 2, MovingAverageType.Simple)
        self.bb2 = BollingerBands(20, 1, MovingAverageType.Simple)
        self.rsi = RelativeStrengthIndex(14, MovingAverageType.Simple)
        self.macd = MovingAverageConvergenceDivergence(12, 26, 9, MovingAverageType.Simple)
        self.sma = SimpleMovingAverage(50)
        self.data = []
        self.pattern_name = ""

    def Update(self, bar):
        self.data.append(bar)
        if len(self.data) > 2:
            self.data.pop(0)
        self.bb.Update(bar.EndTime, bar.Close)
        self.bb2.Update(bar.EndTime, bar.Close)
        self.rsi.Update(bar.EndTime, bar.Close)
        self.macd.Update(bar.EndTime, bar.Close)
        self.sma.Update(bar.EndTime, bar.Close)

    def return_OHLC(self, candle):
        return candle.Open, candle.High, candle.Low, candle.Close

    def return_stats(self, candle):
        delta_v = candle.Close - candle.Open
        max_vi = max(candle.Close, candle.Open)
        min_vi = min(candle.Close, candle.Open)
        return delta_v, max_vi, min_vi

    def shouldEnter(self):
        if len(self.data) < 2:
            return False
        if self.isHangingMan() or self.isBullishEngulfing() or self.isDragonFlyDoji():
            return True
        return False

    def shouldExit(self):
        if len(self.data) < 2:
            return False
        if self.isInvertedHammer() : # look into why no. of trades is decreasing on more candle sticks
            return True
        return False
    
    def shouldEnterShortPositions(self):
        '''
            We want to enter short positions when we are going to see a change from
            uptrend to downtrend
        '''
        if len(self.data) < 2:
            return False
        if self.isInvertedHammer(): # look into why no. of trades is decreasing on more candle sticks
            return True
        return False
    
    def shouldExitShortPositions(self):
        '''
            We want to exit short positions when we are going to see a change from
            downtrend to uptrend
        '''

        if len(self.data) < 2:
            return False
        if self.isHangingMan() or self.isBullishEngulfing() or self.isDragonFlyDoji(): 
            return True
        return False

    def isHangingMan(self):
        candle = self.data[-1]
        curr_open, curr_high, curr_low, curr_close = self.return_OHLC(candle)
        curr_delta_v, curr_max_vi, curr_min_vi = self.return_stats(candle)
        if ( (curr_high - curr_low) > -4 * curr_delta_v) and \
               ((curr_close - curr_low)/(0.001 + curr_high - curr_low ) > 0.6) and \
               (curr_open - curr_low)/(0.001 + curr_high - curr_low ) > 0.6 and \
               (curr_close >= self.bb.UpperBand.Current.Value * self.frac or curr_close <= self.bb.LowerBand.Current.Value):
            self.pattern_name = "Hanging Man"
            return True
        return False
    
    def isInvertedHammer(self):
        candle = self.data[-1]
        curr_open, curr_high, curr_low, curr_close = self.return_OHLC(candle)
        curr_delta_v, curr_max_vi, curr_min_vi = self.return_stats(candle)
        if ( (curr_high - curr_low) > -3 * curr_delta_v) and \
               ((curr_high - curr_close)/(0.001 + curr_high - curr_low ) > 0.6) and \
               (curr_high - curr_open)/(0.001 + curr_high - curr_low ) > 0.6 and \
               (curr_close >= self.bb.UpperBand.Current.Value or curr_close <= self.bb.LowerBand.Current.Value) and \
               (curr_close >= self.bb.UpperBand.Current.Value * self.frac or curr_close <= self.bb.LowerBand.Current.Value):
            self.pattern_name = "Inverted Hammer"
            return True
        return False
    
    def isDragonFlyDoji(self):
        candle = self.data[-1]
        curr_open, curr_high, curr_low, curr_close = self.return_OHLC(candle)
        curr_delta_v, curr_max_vi, curr_min_vi = self.return_stats(candle)
        if ( curr_open == curr_close or (abs(curr_delta_v) / (curr_high - curr_low) < 0.1 )) and \
               ((curr_high - curr_max_vi) < (3 * abs(curr_delta_v))  ) and \
               ((curr_min_vi - curr_low) > (3 * abs(curr_delta_v)) ) and \
               (curr_close >= self.bb.UpperBand.Current.Value * self.frac or curr_close <= self.bb.LowerBand.Current.Value):
            self.pattern_name = "DragonFly Doji"
            return True
        return False
    
    def isGravestoneDoji(self):
        candle = self.data[-1]
        curr_open, curr_high, curr_low, curr_close = self.return_OHLC(candle)
        curr_delta_v, curr_max_vi, curr_min_vi = self.return_stats(candle)
        if ( curr_open == curr_close or(abs(curr_delta_v) / (curr_high - curr_low) < 0.1 )) and \
               ((curr_high - curr_max_vi) > (3 * abs(curr_delta_v))   ) and \
               ((curr_min_vi - curr_low) <= (3 * abs(curr_delta_v)) ) and \
               (curr_close >= self.bb.UpperBand.Current.Value * self.frac or curr_close <= self.bb.LowerBand.Current.Value):
            self.pattern_name = "Gravestone Doji"
            return True
        return False

    def isBullishEngulfing(self):
        if len(self.data) < 2:
            return False
        candle = self.data[-1]
        prev_candle = self.data[-2]
        curr_open, curr_high, curr_low, curr_close = self.return_OHLC(candle)
        prev_open, prev_high, prev_low, prev_close = self.return_OHLC(prev_candle)
        curr_delta_v, curr_max_vi, curr_min_vi = self.return_stats(candle)
        prev_delta_v, prev_max_vi, prev_min_vi = self.return_stats(prev_candle)
        if curr_close >= prev_open and prev_open > prev_close and \
                curr_close > curr_open and prev_close >= curr_open and \
                (curr_close - curr_open) > (prev_open - prev_close) and \
               (curr_close >= self.bb.UpperBand.Current.Value * self.frac or curr_close <= self.bb.LowerBand.Current.Value):
            self.pattern_name = "Bullish Engulfing"
            return True
        return False
    
    def isBearishEngulfing(self):
        if len(self.data) < 2:
            return False
        candle = self.data[-1]
        prev_candle = self.data[-2]
        curr_open, curr_high, curr_low, curr_close = self.return_OHLC(candle)
        prev_open, prev_high, prev_low, prev_close = self.return_OHLC(prev_candle)
        curr_delta_v, curr_max_vi, curr_min_vi = self.return_stats(candle)
        prev_delta_v, prev_max_vi, prev_min_vi = self.return_stats(prev_candle)
        if curr_open >= prev_close and prev_close > prev_open and \
                curr_close < curr_open and prev_open >= curr_close and \
                (curr_open - curr_close) > (prev_close - prev_open) and \
               (curr_close >= self.bb.UpperBand.Current.Value * self.frac or curr_close <= self.bb.LowerBand.Current.Value):
            self.pattern_name = "Bearish Engulfing"
            return True
        return False

    def getPatternName(self):
        return self.pattern_name
