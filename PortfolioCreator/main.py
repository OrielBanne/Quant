from AlgorithmImports import *
from utils import (
    StrategyConfig, SECTOR_ETF_MAP, DEFAULT_SECTOR_FILTERS, SECTOR_STOCKS_MAP,
    passes_fundamental_filters, calculate_fundamental_score, build_final_universe,
    get_sector_etf_symbols, log_sector_performance, log_filter_status
)
from SNP_Influencers import (
    IntegratedSP500Tracker
)

class RisingSectorFundamentalUniverse(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_cash(100000)

        self.set_benchmark("SPY")
        self.spy = self.add_equity("SPY", Resolution.DAILY).Symbol
        
        self.lookback_days = StrategyConfig.LOOKBACK_DAYS
        self.num_stocks = StrategyConfig.NUM_STOCKS
        self.num_sectors = StrategyConfig.NUM_SECTORS
        self.sector_returns = {}
     
        self.sector_etf_map = get_sector_etf_symbols(self)

        self.sector_stocks_map = SECTOR_STOCKS_MAP

        self.sector_filters = {}
        self.last_filter_update = datetime.min
        self.filter_update_frequency = StrategyConfig.FILTER_UPDATE_FREQUENCY
        
        self.sector_filters = DEFAULT_SECTOR_FILTERS.copy()

        # Schedules:
        self.schedule.on(self.date_rules.every_day(), self.time_rules.after_market_open(self.spy, 30), self.UpdateUniverse)
        self.schedule.on(self.date_rules.month_start(), self.time_rules.after_market_open(self.spy, 60), self.update_sector_filters)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.every(timedelta(hours=4)), self.check_stop_losses)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.every(timedelta(hours=4)), self.check_portfolio_stop_loss)
        
        self.universe_symbols = []
        self.selected_sectors = []
        
        self.add_universe(self.coarse_selection_function, self.fine_selection_function)
        
        # Risk management
        self.last_rebalance = datetime.min
        self.rebalance_frequency = StrategyConfig.REBALANCE_FREQUENCY
        
        # Stop loss
        self.stop_loss_percentage = StrategyConfig.STOP_LOSS_PERCENTAGE
        self.trailing_stop_percentage = StrategyConfig.TRAILING_STOP_PERCENTAGE
        self.portfolio_stop_loss = StrategyConfig.PORTFOLIO_STOP_LOSS
        self.highest_prices = {} 
        self.highest_portfolio_value = 0
        
        self.max_position_size = StrategyConfig.MAX_POSITION_SIZE
        
        self.need_rebalance = False
        self.rebalance_reason = ""
        
        # blacklist
        self.blacklisted_stocks = set()
        self.blacklist_duration = StrategyConfig.BLACKLIST_DURATION
        self.stock_blacklist_dates = {}  
        
        self.emergency_liquidation = False
        self.emergency_liquidation_date = None
        self.restart_delay_days = StrategyConfig.RESTART_DELAY_DAYS
        
        # Warmup
        self.warmup_period = StrategyConfig.WARMUP_PERIOD
        self.is_warmed_up = False
        self.start_time = self.time 
        
        self.warm_up_historical_data()

        self.sp500_tracker = IntegratedSP500Tracker(self)
        self.sp500_tracker.initialize()
        
        self.analyze_missing_sp500_leaders()
    
        # Schedule monthly analysis
        self.schedule.on(self.date_rules.month_start(), 
                    self.time_rules.after_market_open(self.spy, 60), 
                    self.analyze_missing_sp500_leaders)
        
    
    def analyze_missing_sp500_leaders(self):
        try:
            # Check if sp500_tracker exists and is initialized
            if not hasattr(self, 'sp500_tracker') or self.sp500_tracker is None:
                self.log("S&P 500 tracker not initialized yet")
                return
                
            current_symbols = list(self.universe_symbols) if hasattr(self, 'universe_symbols') else []
            analysis = self.sp500_tracker.analyze_sp500_influence(current_symbols)
            if analysis and analysis['missing_influencers']:
                missing = analysis['missing_influencers']
                self.log(f"Found {len(missing)} influential S&P 500 stocks missing:")
                for stock in missing[:5]:
                    self.log(f"  MISSING: {stock['symbol']} ({stock['sector']}): "
                            f"{stock['performance']:+.1f}% (S&P Impact: {stock['sp500_contribution']:+.3f}%)")
        except Exception as e:
            self.log(f"Error in analyze_missing_sp500_leaders: {str(e)}")

    def warm_up_historical_data(self):
        try:
            # etf_symbols = list(self.sector_etf_map.values())
            available_sectors = set(self.sector_etf_map.keys()) & set(self.sector_stocks_map.keys())
            etf_symbols = [self.sector_etf_map[sector] for sector in available_sectors]
            
            history = self.history(etf_symbols, self.warmup_period, Resolution.DAILY)
            
            if history is not None and not history.empty:
                self.log(f"Warmed up with {len(history)} points")
                
                # Calculate initial sector returns
                temp_sector_returns = {}
                for symbol, df in history.groupby(level=0):
                    if len(df) >= 2:
                        start_price = df.iloc[0]['close']
                        end_price = df.iloc[-1]['close']
                        
                        if start_price > 0:
                            ret = (end_price / start_price) - 1
                            sector_code = next((k for k, v in self.sector_etf_map.items() if v == symbol), None)
                            if sector_code:
                                temp_sector_returns[sector_code] = ret
                
                self.sector_returns = temp_sector_returns
                formatted = {k: f"{v:.2f}" for k, v in self.sector_returns.items()}
                self.log(f"Initial sector returns calculated: {formatted}")
            else:
                self.log("Warning: Could not get historical data for warmup")
                
        except Exception as e:
            self.log(f"Error during warmup: {str(e)}")


    def update_sector_filters(self):
        if not self.is_warmed_up:
            return
            
        if (self.time - self.last_filter_update).days < self.filter_update_frequency:
            return
        
        try:
            for sector in self.sector_stocks_map.keys():
                sector_return = self.sector_returns.get(sector, 0)
                
                current_filter = self.sector_filters.get(sector, DEFAULT_SECTOR_FILTERS[sector]).copy()
                
                if sector_return > 0.10:  # Strong - be more selective
                    current_filter['pe_ratio_max'] *= 0.9
                    current_filter['roe_min'] *= 1.1
                elif sector_return < -0.05:  # Weak - be less restrictive
                    current_filter['pe_ratio_max'] *= 1.1
                    current_filter['roe_min'] *= 0.9
                
                # Ensure filters stay within reasonable bounds
                current_filter['pe_ratio_max'] = max(15.0, min(50.0, current_filter['pe_ratio_max']))
                current_filter['pe_ratio_min'] = max(3.0, min(15.0, current_filter['pe_ratio_min']))
                current_filter['roe_min'] = max(0.05, min(0.25, current_filter['roe_min']))
                
                self.sector_filters[sector] = current_filter
                
                self.log(f"Updated {sector} filters:")
                self.log(f"  P/E: {current_filter['pe_ratio_min']:.1f} - {current_filter['pe_ratio_max']:.1f}")
                self.log(f"  ROE min: {current_filter['roe_min']:.2%}")
                self.log(f"  P/B max: {current_filter['pb_ratio_max']:.1f}")
            
            self.last_filter_update = self.time
            self.log("=== UPDATE COMPLETE ===")
            
        except Exception as e:
            self.log(f"Error updating sector filters: {str(e)}")
            # Fall back to default filters
            self.sector_filters = DEFAULT_SECTOR_FILTERS.copy()

    def OnData(self, data):
        if self.emergency_liquidation:
            self.check_emergency_restart()
            return
        
        self.immediate_stop_loss_check(data)
        
        if self.need_rebalance:
            self.execute_rebalance(data)
            self.log(f'rebalanced  = selected sectors ')
            return
        
        if not self.is_warmed_up:
            if self.time < self.start_time + timedelta(days=self.warmup_period):
                return
            else:
                self.is_warmed_up = True
                self.log(f"Warmup period completed at {self.time}")
                # Initialize highest portfolio value
                self.highest_portfolio_value = self.portfolio.total_portfolio_value
        
        if (self.time - self.last_rebalance).days >= self.rebalance_frequency:
            self.trigger_rebalance("Scheduled rebalancing")
            try:
                self.analyze_missing_sp500_leaders() 
            except Exception as e:
                self.log(f"Error in scheduled S&P 500 analysis: {str(e)}")
            return
        
        if self.portfolio.total_portfolio_value > self.highest_portfolio_value:
            self.highest_portfolio_value = self.portfolio.total_portfolio_value

    def trigger_rebalance(self, reason):
        self.need_rebalance = True
        self.rebalance_reason = reason
        self.log(f"Rebalancing triggered: {reason}")

    def execute_rebalance(self, data):
        self.log(f"=== EXECUTING REBALANCE: {self.rebalance_reason} ===")
        
        self.clean_blacklist()
        
        self.UpdateUniverse()
        
        if not self.universe_symbols:
            self.log("No universe symbols available - liquidating all positions")
            self.liquidate()
            self.reset_rebalance_flags()
            return
        
        if self.portfolio.cash <= 1000:
            self.log(f"Low cash warning: ${self.portfolio.cash:.2f}")
            self.reset_rebalance_flags()
            return
        
        weight_per_stock = min(1.0 / len(self.universe_symbols), self.max_position_size)
        
        valid_symbols = []
        for symbol in self.universe_symbols:
            if (self.securities.contains_key(symbol) and 
                data.contains_key(symbol) and 
                data[symbol] is not None and
                self.securities[symbol].price > 0):
                valid_symbols.append(symbol)
            else:
                self.log(f"Skipping {symbol}: No valid price data available")
                
        if not valid_symbols:
            self.log("No valid symbols with current data - staying in cash")
            self.liquidate()
            self.reset_rebalance_flags()
            return
        
        weight_per_stock = min(1.0 / len(valid_symbols), self.max_position_size)
        
        self.log(f"Rebalancing {len(valid_symbols)} stocks with {weight_per_stock:.2%} each")
        
        # Log the universe being rebalanced
        universe_symbol_names = [s.value for s in valid_symbols]
        self.log(f" REBALANCING - Universe stocks: {universe_symbol_names}")
        
        successful_investments = 0
        for symbol in valid_symbols:
            try:
                if (data.contains_key(symbol) and 
                    data[symbol] is not None and 
                    self.securities[symbol].price > 0):
                    self.set_holdings(symbol, weight_per_stock)
                    self.log(f"Set holdings: {symbol} = {weight_per_stock:.2%}")
                    successful_investments += 1
                else:
                    self.log(f"Skipping {symbol}: Price data not available at execution time")
            except Exception as e:
                self.log(f"Error setting holdings for {symbol}: {str(e)}")
        
        for symbol in list(self.portfolio.keys()):
            if (self.portfolio[symbol].invested and 
                symbol != self.spy and 
                symbol not in valid_symbols):
                self.log(f"Liquidating position not in universe: {symbol}")
                self.liquidate(symbol)
        
        self.last_rebalance = self.time
        self.cleanup_stop_loss_tracking(valid_symbols)
        
        self.log(f"===Rebalancing complete: {successful_investments}/{len(valid_symbols)} successful")

        self.reset_rebalance_flags()


    def reset_rebalance_flags(self):
        self.need_rebalance = False
        self.rebalance_reason = ""

    def check_emergency_restart(self):
        if not self.emergency_liquidation_date:
            return

        days_since_liquidation = (self.time - self.emergency_liquidation_date).days
        
        if days_since_liquidation >= self.restart_delay_days:
            self.log(f"Waited {days_since_liquidation} day(s) - now restarting after portfolio stop loss")
            
            # Reset
            self.emergency_liquidation = False
            self.emergency_liquidation_date = None

            self.highest_prices.clear()
            self.blacklisted_stocks.clear()
            self.stock_blacklist_dates.clear()

            self.highest_portfolio_value = self.portfolio.total_portfolio_value

            self.last_rebalance = datetime.min
            self.trigger_rebalance("Emergency restart")
            
            self.log("Emergency restart complete ")

    def clean_blacklist(self):
        current_time = self.time
        stocks_to_remove = []
        
        for stock, blacklist_date in self.stock_blacklist_dates.items():
            if (current_time - blacklist_date).days >= self.blacklist_duration:
                stocks_to_remove.append(stock)
        
        for stock in stocks_to_remove:
            self.blacklisted_stocks.discard(stock)
            del self.stock_blacklist_dates[stock]
            self.log(f"Removed {stock} from blacklist after {self.blacklist_duration} days")

    def immediate_stop_loss_check(self, data):
        if not self.is_warmed_up or self.emergency_liquidation:
            return
            
        stop_loss_executed = False
        
        for symbol in list(self.portfolio.keys()):
            if not self.portfolio[symbol].invested or symbol == self.spy:
                continue
                
            if not data.contains_key(symbol):
                continue
                
            bar = data[symbol]
            if bar is None:
                continue
            current_price = bar.close
                
            position = self.portfolio[symbol]
            
            if symbol not in self.highest_prices:
                self.highest_prices[symbol] = current_price

            if current_price > self.highest_prices[symbol]:
                self.highest_prices[symbol] = current_price
                
            entry_price = position.average_price
            highest_price = self.highest_prices[symbol]
            
            if highest_price > entry_price * 1.02:
                stop_price = highest_price * (1 - self.trailing_stop_percentage)
            else:
                stop_price = entry_price * (1 - self.stop_loss_percentage)
            
            if current_price <= stop_price:
                self.log(f"IMMEDIATE STOP LOSS: {symbol} at ${current_price:.2f} (stop: ${stop_price:.2f})")
                
                stock_ticker = str(symbol).split()[0]
                self.blacklisted_stocks.add(stock_ticker)
                self.stock_blacklist_dates[stock_ticker] = self.time
                self.log(f"Added {stock_ticker} to blacklist for {self.blacklist_duration} days")
                
                self.liquidate(symbol)
                
                if symbol in self.highest_prices:
                    del self.highest_prices[symbol]
                
                stop_loss_executed = True
        
        if stop_loss_executed:
            self.trigger_rebalance("Stop loss executed")

    def check_portfolio_stop_loss(self):
        if not self.is_warmed_up or self.emergency_liquidation:
            return
            
        current_value = self.portfolio.total_portfolio_value
        
        if current_value > self.highest_portfolio_value:
            self.highest_portfolio_value = current_value
        
        if self.highest_portfolio_value > 0:
            drawdown = (self.highest_portfolio_value - current_value) / self.highest_portfolio_value
            if drawdown >= self.portfolio_stop_loss:
                self.log(f"PORTFOLIO STOP LOSS  Drawdown: {drawdown:.2%} >= {self.portfolio_stop_loss:.2%} - LIQUIDATING")
                
                for symbol in list(self.portfolio.keys()):
                    if self.portfolio[symbol].invested and symbol != self.spy:
                        self.liquidate(symbol)
                        self.log(f"Emergency liquidated: {symbol}")

                self.emergency_liquidation = True
                self.emergency_liquidation_date = self.time

                self.highest_prices.clear()
                self.reset_rebalance_flags()

    def check_stop_losses(self):
        if not self.is_warmed_up or self.emergency_liquidation:
            return
            
        if not self.portfolio.invested:
            return
            
        stop_loss_executed = False
        
        for symbol in list(self.portfolio.keys()):
            if not self.portfolio[symbol].invested or symbol == self.spy:
                continue
                
            try:
                current_price = self.securities[symbol].price
                if current_price <= 0:
                    continue
                    
                position = self.portfolio[symbol]
                
                if symbol not in self.highest_prices:
                    self.highest_prices[symbol] = current_price
                    
                if current_price > self.highest_prices[symbol]:
                    self.highest_prices[symbol] = current_price
                    
                entry_price = position.average_price
                highest_price = self.highest_prices[symbol]
                
                if highest_price > entry_price * 1.02:  # 2% buffer
                    stop_price = highest_price * (1 - self.trailing_stop_percentage)
                else:
                    stop_price = entry_price * (1 - self.stop_loss_percentage)

                if current_price <= stop_price:
                    self.log(f"SCHEDULED STOP LOSS: {symbol} at ${current_price:.2f} (stop: ${stop_price:.2f})")
                    
                    stock_ticker = str(symbol).split()[0]
                    self.blacklisted_stocks.add(stock_ticker)
                    self.stock_blacklist_dates[stock_ticker] = self.time
                    self.log(f"Added {stock_ticker} to blacklist for {self.blacklist_duration} days")

                    self.liquidate(symbol)

                    if symbol in self.highest_prices:
                        del self.highest_prices[symbol]

                    stop_loss_executed = True
                        
            except Exception as e:
                self.log(f"Error in stop loss check for {symbol}: {str(e)}")
        
        if stop_loss_executed:
            self.trigger_rebalance("Scheduled stop loss executed")

    def UpdateUniverse(self):
        if not self.is_warmed_up or self.emergency_liquidation:
            return

        available_sectors = set(self.sector_etf_map.keys()) & set(self.sector_stocks_map.keys())
        etf_symbols = [self.sector_etf_map[sector] for sector in available_sectors]
        
        if not etf_symbols:
            self.log("No sector ETFs defined. Cannot update sector returns.")
            return

        history = self.history(etf_symbols, self.lookback_days, resolution=Resolution.DAILY)
        if history is None or history.empty:
            self.log("ETF history data is empty. 447")
            self.sector_returns = {}
            return

        temp_sector_returns = {}
        for symbol, df in history.groupby(level=0):
            if len(df) < 2: continue
            
            start_price = df.iloc[0]['close']
            end_price = df.iloc[-1]['close']
            
            if start_price > 0:
                ret = (end_price / start_price) - 1
                sector_code = next((k for k, v in self.sector_etf_map.items() if v == symbol), None)
                if sector_code: temp_sector_returns[sector_code] = ret
        
        self.sector_returns = temp_sector_returns
        self.selected_sectors = log_sector_performance(self, self.sector_returns, self.num_sectors)
        
        # Log universe update
        self.log(f"=== UNIVERSE UPDATE COMPLETED ===")
        self.log(f"Selected sectors: {self.selected_sectors}")
        if hasattr(self, 'universe_symbols') and self.universe_symbols:
            universe_names = [s.value for s in self.universe_symbols]
            self.log(f"Current universe: {universe_names}")
        else:
            self.log("No universe symbols set yet")

    def coarse_selection_function(self, coarse):
        if not self.is_warmed_up or self.emergency_liquidation:
            return Universe.UNCHANGED

        # If no sectors selected yet, return empty to avoid processing all stocks
        if not self.selected_sectors:
            self.log("No sectors selected yet, returning empty coarse selection")
            return []

        symbol_names = [s.value for s in self.universe_symbols]
        self.log(f"previous universe = {symbol_names}")
        filtered = [x for x in coarse if x.has_fundamental_data and x.market_cap > StrategyConfig.MIN_MARKET_CAP and x.dollar_volume > StrategyConfig.MIN_DOLLAR_VOLUME and x.price > StrategyConfig.MIN_PRICE]
        # sorted_by_volume = sorted(filtered, key=lambda x: x.dollar_volume, reverse=True)

                
        # Get all stocks from selected sectors
        sector_stocks = set()
        for sector in self.selected_sectors:
            if sector in self.sector_stocks_map:
                sector_stocks.update(self.sector_stocks_map[sector])
        
        self.log(f"Looking for stocks from sectors: {self.selected_sectors}")
        self.log(f"Target stocks: {list(sector_stocks)}")
        
        filtered = []
        for x in coarse:
            if (x.has_fundamental_data and 
                x.market_cap > StrategyConfig.MIN_MARKET_CAP and 
                x.dollar_volume > StrategyConfig.MIN_DOLLAR_VOLUME and 
                x.price > StrategyConfig.MIN_PRICE and
                x.symbol.Value in sector_stocks):
                filtered.append(x)
        
        # Sort by market cap and take top stocks
        sorted_by_market_cap = sorted(filtered, key=lambda x: x.market_cap, reverse=True)
        symbols_to_return = [x.symbol for x in sorted_by_market_cap[:50]]
        # Show first 20 symbol names for debugging
        symbol_names = [s.value for s in symbols_to_return[:20]]
        self.log(f"First 20 symbols from coarse (sector filtered): {symbol_names}")

        return symbols_to_return


    def fine_selection_function(self, fine):
        if not self.selected_sectors or self.emergency_liquidation:
            self.log("No selected sectors available or in emergency mode")
            return []
        
        sector_filtered_stocks = {}

        self.log("*** FINE SELECTION FUNCTION STARTED ***")
        self.log(f"Selected sectors: {self.selected_sectors}")

        if fine:
            # Check if NVDA is in the fine data
            nvda_found = any(str(f.symbol).split()[0] == "NVDA" for f in fine)
            self.log(f"NVDA found in fine data: {nvda_found}")

        # Convert fine data to list so we can use it multiple times
        fine_data_list = list(fine)
        self.log(f"Converted fine data to list with {len(fine_data_list)} stocks")

        # Process fine data for S&P 500 analysis
        if hasattr(self, 'sp500_tracker') and self.sp500_tracker is not None:
            try:
                self.sp500_tracker.process_fine_data_for_sp500(fine_data_list)
            except Exception as e:
                self.log(f"S&P 500 processing error: {str(e)}")

        # Create a lookup dictionary once at the beginning
        fine_data_lookup = {}
        for count, f in enumerate(fine_data_list):
            if hasattr(f, 'symbol'):
                ticker = f.symbol.Value  # Get the actual ticker symbol
                fine_data_lookup[ticker] = f

        
        for sector in self.selected_sectors:
            if sector not in self.sector_stocks_map:
                continue
                
            sector_stocks = self.sector_stocks_map[sector]
            sector_filter = self.sector_filters.get(sector, DEFAULT_SECTOR_FILTERS[sector])
            
            filtered_stocks = []
            
            for stock_ticker in sector_stocks:
                if stock_ticker in self.blacklisted_stocks:
                    self.log(f"{stock_ticker} is still blacklisted")
                    continue
                
                try:
                    stock_fine_data = fine_data_lookup[stock_ticker]
                    try:
                        pe_ratio = stock_fine_data.valuation_ratios.pe_ratio
                        pb_ratio = stock_fine_data.valuation_ratios.pb_ratio
                        roe = stock_fine_data.operation_ratios.roe.one_year
                        revenue = stock_fine_data.financial_statements.income_statement.total_revenue.three_months
                        market_cap = stock_fine_data.market_cap
                        
                        self.log(f"{stock_ticker} * PE: {pe_ratio:.2f}, PB: {pb_ratio:.2f}, ROE: {roe:.3f}, Revenue: ${revenue:,.0f}, MarketCap: ${market_cap:,.0f}")
                    except Exception as e:
                        self.log(f"{stock_ticker} data extraction error: {str(e)}")
                        self.log(f"{stock_ticker} raw data: {stock_fine_data}")
                except:
                    self.log(f" {stock_ticker} has NO FINE DATA")
                    stock_fine_data = None
                    continue

                if not passes_fundamental_filters(stock_fine_data, sector_filter, stock_ticker=stock_ticker, algorithm=self):
                    self.log(f"stock {stock_ticker} did not pass fundamentals filter")

                try:
                    pe_ratio = stock_fine_data.valuation_ratios.pe_ratio
                    roe = stock_fine_data.operation_ratios.roe.one_year
                    score = calculate_fundamental_score((stock_ticker, stock_fine_data, pe_ratio, roe), sector)
                    actual_ticker = stock_fine_data.symbol.Value  
                    filtered_stocks.append((actual_ticker, stock_fine_data, score))
                except Exception as e:
                    continue

            filtered_stocks.sort(key=lambda x: x[2], reverse=True)
            sector_filtered_stocks[sector] = filtered_stocks[:4]
            
            if len(filtered_stocks) > 0:
                msgs = [f"{sector}:",]
                for stock_ticker, _, score in filtered_stocks[:4]:
                    msgs.append(f"{stock_ticker}: {score:.1f}")
                self.log(" ".join(msgs))
        
        final_universe = build_final_universe(self, sector_filtered_stocks, self.num_stocks)
        
        initial_symbol_names = [s.value for s in final_universe]
        self.log(f"Initial universe BEFORE S&P ({len(final_universe)} stocks): {initial_symbol_names}")
        
        if hasattr(self, 'sp500_tracker') and self.sp500_tracker is not None:
            try:
                missing_sp500_stocks = self.sp500_tracker.get_top_missing_sp500_stocks(final_universe, top_n=3)
                if missing_sp500_stocks:
                    self.log(f"Adding {len(missing_sp500_stocks)} S&P 500 stocks to universe")
                    final_universe.extend(missing_sp500_stocks)
                    for symbol in missing_sp500_stocks:
                        self.log(f"  +{symbol.value}")
                else:
                    self.log("No S&P 500 stocks to add")
            except Exception as e:
                self.log(f"S&P 500 error: {str(e)}")
        
        if self.blacklisted_stocks:
            self.log(f"Blacklisted stocks: {list(self.blacklisted_stocks)}")
    
        self.universe_symbols = final_universe

        # Log the final universe
        final_symbol_names = [s.value for s in final_universe]
        self.log(f"Final universe AFTER S&P ({len(final_universe)} stocks): {final_symbol_names}")
        
        return final_universe
    
    def cleanup_stop_loss_tracking(self, new_universe):
        universe_symbols = set(str(s) for s in new_universe)
        
        symbols_to_remove = []
        for symbol in self.highest_prices.keys():
            if str(symbol) not in universe_symbols:
                symbols_to_remove.append(symbol)
                
        for symbol in symbols_to_remove:
            if symbol in self.highest_prices:
                del self.highest_prices[symbol]


    def OnEndOfDay(self):
        self.clean_blacklist()
