#  --------------------------------------------------------------------
#  The core idea is to use Mean-Variance Portfolio with Dynamic Top-400 Universe
#  • Universe: top-400 U.S. equities by dollar-volume,
#              price > $N, MarketCap > $2 B, HasFundamentalData (refreshed every 'M' calendar days)
#  • Monthly portfolio rebalance with mean-variance optimisation,
#    max XX % per position, ≥YY holdings, ZZ % stop-loss.
# ---------------------------------------------------------------------
#  How the "BARBELL" EFFECT is actually hanessed: 
#  --------------------------------------------------------------------
#  1)  **Momentum‑biased alpha**
#      alpha = 21‑day cumulative log‑return  –  10‑day "fair" return  –  β·SPY.
#      Because we subtract only half the window, each stock’s excess return is
#      inflated ≈ 2×, so recent big winners get very large alpha scores.
#
#  2)  **Risk‑parity sizing**
#      The optimiser receives historical sample *means* (≈0) and a daily covariance matrix.  
#      Maximising Sharpe with µ ≈ 0 collapses to *minimise variance subject to weight caps* → portfolio weight gravitates
#      toward low‑volatility / low‑beta names.
#
#  3)  **Combined result**
#      Stock *selection* = strong **Momentum** factor; position *sizing* = **Low‑Volatility** tilt.  
#      Empirically the two factors are negatively correlated, so the mix delivers high CAGR with milder draw‑downs 
#  --------------------------------------------------------------------
#  CONSTANTS
#  --------------------------------------------------------------------
#  LOOKBACK_DAYS   → momentum horizon (here 21)  ▸ drives alpha numerator.
#  rebalance_period→ ½×LOOKBACK for trading pace ▸ drives intercept term.
#  BETA_REG_WINDOW → sample length for β OLS     ▸ statistical reliability.
#  *Adjust them consciously to keep the intended factor mix.*
# ---------------------------------------------------------------------
from AlgorithmImports import *
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from datetime import timedelta

import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform

TRADING_DAYS_PER_MONTH      = 21
LOOKBACK_DAYS               = TRADING_DAYS_PER_MONTH // 2   # ← momentum / alpha horizon
BETA_REG_WINDOW             = TRADING_DAYS_PER_MONTH        # the minimum number of daily observations you require before estimating β by OLS.
# 252 is the conventionally assumed number of trading days in one calendar year for U.S. markets (≈ 21 days × 12 months)
TRADING_DAYS_PER_YEAR       = TRADING_DAYS_PER_MONTH*12
UNIVERSE_REFRESH_DAYS       = 30

# ======================  PER-SYMBOL STATE  ===========================
class SymbolData:
    """Cache of rolling returns and factor-model parameters."""
    def __init__(self, symbol, log_returns: pd.Series):
        self.symbol      = symbol
        self.df          = pd.DataFrame({'log_return': log_returns})
        self.mean        = self.df['log_return'].mean() if not self.df.empty else 0.0

        # intraperiod buffers (store *log-prices*)
        self.price_buf   = []
        self.time_buf    = []

        # CAPM regression coefficients
        self.intercept   = 0.0
        self.beta        = 0.0

        # one-month (≈21 trading days) cumulative log-return
        # Will be refreshed every day by _refresh_one_month()
        self.one_month   = 0.0

        # custom alpha signal
        self.alpha       = 0.0

# ======================  MAIN ALGORITHM  =============================
class MeanVarianceWithDynamicUniverse(QCAlgorithm):
    # ------------ INITIALISATION ------------------------------------
    def Initialize(self):

        # --- back-test window & cash ---------------------------------
        self.SetStartDate(2022, 1, 1)
        # self.SetEndDate(2024, 1, 1)
        self.SetCash(100_000)

        # --- model parameters ----------------------------------------
        self.num_history_days   = TRADING_DAYS_PER_YEAR         # 12 months of daily bars
        self.rebalance_period   = LOOKBACK_DAYS                 # 21  # ≈1 trading month (or every half month)
        self.final_universe_sz  = 400           # number of stocks in the universe 
        self.min_positions      = 35            # minimum number of stocks to hold in the portfolio  
        self.max_weight         = 0.15          # up to X% cap per name
        self.weight_threshold   = 1e-4
        self.stop_loss_pct      = 0.10          # X% fall is hard stop
        self.min_share_change   = 2
        self.min_ipo_days       = 180           # at least N-months seasoning for new IPO/SPAC
        self.min_share_price    = 5             # in $ (for universe selection)
        self.min_market_cap     = 2_000_000_000 # in $ (for universe selection)
        self.min_total_trade_qty= 5             # ← skip an entire rebalance if we’d move < N shares in total
        self.use_beta_shrink    = False # True  # ← turn ON/OFF "Blume adjustment"

        # --- internal state ------------------------------------------
        self.symbol_data: dict[Symbol, SymbolData] = {}
        self.entry_prices: dict[Symbol, float]     = {}
        self.days_since_rebalance                  = 0
        self.next_universe_refresh                 = self.Time

        # --- benchmark / market factor --------------------------------
        self.spy = self.AddEquity("NVDA", Resolution.Daily).Symbol
        self.SetBenchmark("NVDA")

        # --- universe selection ---------------------------------------
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelection)

    # ------------ UNIVERSE SELECTION ---------------------------------
    def CoarseSelection(self, coarse):
        if self.Time <= self.next_universe_refresh:
            return Universe.Unchanged
        self.next_universe_refresh = self.Time + timedelta(days=30)

        filtered = [c for c in coarse
                    if c.HasFundamentalData
                    and c.Price > self.min_share_price
                    and c.MarketCap > self.min_market_cap
                    # ---- skip symbols younger than N calendar days ----
                    and (self.Time - c.Symbol.ID.Date).days >= self.min_ipo_days]

        selected = sorted(filtered,
                        key=lambda c: c.DollarVolume,
                        reverse=True)[:self.final_universe_sz]
        return [c.Symbol for c in selected]

    # ------------ SECURITIES CHANGED ---------------------------------
    def OnSecuritiesChanged(self, changes: SecurityChanges):
        # ---- remove dropped symbols ---------------------------------
        for sec in changes.RemovedSecurities:
            sym = sec.Symbol
            self.symbol_data.pop(sym, None)
            self.entry_prices.pop(sym, None)
            if self.Portfolio[sym].Invested:
                self.Liquidate(sym)

        # ---- add new symbols ----------------------------------------
        added_syms = [sec.Symbol for sec in changes.AddedSecurities]
        if not added_syms:
            return

        history = self.History(added_syms, self.num_history_days, Resolution.Daily)
        if history.empty:
            return

        for sym in added_syms:
            if sym not in history.index.levels[0]:
                continue
            hist  = history.loc[sym]
            log_p = np.log(hist['close'].astype(float))
            log_r = log_p.diff().dropna()
            self.symbol_data[sym] = SymbolData(sym, log_r)

        # refresh regression coefficients once we have SPY data
        if self.spy in self.symbol_data:
            self._run_regression()


    # ------------ FACTOR REGRESSION ---------------------------------
    def _run_regression(self):
        """
        Vectorised CAPM β/α update.
        • Align every symbol on SPY's calendar
        • Fill missing returns with 0
        • Compute betas & intercepts in a single matrix pass
        """
        spy     = self.spy
        spy_ret = self.symbol_data[spy].df['log_return']

        # ---- 1) build aligned returns matrix (T × N) -------------------
        ret_df = pd.concat(
            {sym: sd.df['log_return'] for sym, sd in self.symbol_data.items()},
            axis=1
        ).reindex(spy_ret.index).fillna(0)      # (T × N) DataFrame

        # ---- 2) prepare matrices --------------------------------------
        x = ret_df[spy].values                  # SPY vector shape (T,)
        y_mat = ret_df.drop(columns=spy).values # all stocks shape (T, M)
        denom = np.dot(x, x)                    # scalar  Σ x²
        if denom == 0:
            return                              # safety guard

        # ---- 3) vectorised β and α ------------------------------------
        # OLS betas
        beta_ols    = (x @ y_mat) / denom       # shape (M,)
        # ---- 4) Optional Blume shrink toward 1.0 (to catch booms of new stuff like AI in 2022)
        if getattr(self, "use_beta_shrink", False):
            w           = 0.6
            target_beta = 1.0
            betas = w * target_beta + (1 - w) * beta_ols
        else:
            betas = beta_ols

        # --- 5) Intercepts
        mean_x      = x.mean()
        means_y     = y_mat.mean(axis=0)              # shape (M,)
        intercepts  = means_y - betas * mean_x        # α₀ for each stock

        # --- 6) write back to SymbolData ------------------------------
        for sym, beta, alpha0 in zip(ret_df.drop(columns=spy).columns, betas, intercepts):
            data = self.symbol_data[sym]
            # optional: keep minimum length check (30 obs) for robustness
            if len(data.df) < BETA_REG_WINDOW: # fewer than N daily returns
                continue # leave existing beta / intercept unchanged
            data.beta      = beta
            data.intercept = alpha0
    
    # -----------------------------------------------------------------
    #  MAIN DAILY LOOP
    # -----------------------------------------------------------------
    def OnData(self, slice: Slice):

        # ---------- 0) stop-loss enforcement -------------------------
        for sym, entry_px in list(self.entry_prices.items()):
            if slice.ContainsKey(sym) and slice[sym] and self.Portfolio[sym].Invested:
                if float(slice[sym].Close) < entry_px * (1 - self.stop_loss_pct):
                    self.Liquidate(sym)
                    self.entry_prices.pop(sym, None)

        # need SPY data for alpha calculation
        if not (slice.ContainsKey(self.spy) and slice[self.spy]):
            return

        # ---------- 1) rebalance day --------------------------------
        if self.days_since_rebalance == 0 and len(self.symbol_data) >= self.min_positions:
            # (a) buffer today’s close
            self._update_buffers(slice)

            # (b) recompute one-month returns
            self._refresh_one_month()

            # ----- compute alpha signal (β-adjusted) -----------------
            spy_data = self.symbol_data[self.spy]
            for sym, data in self.symbol_data.items():
                if sym == self.spy:
                    continue
                data.alpha = (data.one_month
                            - self.rebalance_period * data.intercept
                            - data.beta * spy_data.one_month)

            # ----- pick top-N names ---------------------------------
            candidates = [s for s in self.symbol_data if s != self.spy]
            ranked     = sorted(candidates,
                                key=lambda s: self.symbol_data[s].alpha,
                                reverse=True)

            # old selecttion of at least 35 stocks (no matter what)
            # selected   = ranked[:self.min_positions]

            # --- HYBRID SELECTION LOGIC - only those with positive alpha are used ---
            # First, find all stocks with a positive alpha signal.
            positive_alpha_candidates = [s for s in ranked if self.symbol_data[s].alpha > 0]

            # If there are enough "good" signals, stick to the minimum of 35.
            if len(positive_alpha_candidates) >= self.min_positions:
                # Select the top 35 from the positive alpha list.
                selected = positive_alpha_candidates[:self.min_positions]
            else:
                # Otherwise, if the market is weak and there aren't 35 "good" signals,
                # select only the candidates that have a positive alpha.
                selected = positive_alpha_candidates
            

            # ---------- assemble returns matrix ----------------------
            ret_df = pd.concat({s: self.symbol_data[s].df['log_return']
                                for s in selected}, axis=1).dropna()

            if ret_df.empty or ret_df.shape[1] < self.min_positions:
                self.days_since_rebalance += 1
                return

            means = ret_df.mean().values               # µ vector
            cov   = ret_df.cov().values                # Σ matrix

            # ---------- optimise weights -----------------------------
            opt     = Optimizer(selected, means, cov,
                                long_only=True,
                                max_weight=self.max_weight)
            weights = np.array(opt.optimize())

            # post-process weights
            weights[np.abs(weights) < self.weight_threshold] = 0
            if weights.sum() > 0:
                weights = np.minimum(weights, self.max_weight)
                weights /= weights.sum()

            # ---------- build trade list & aggregate Δshares ---------
            port_val      = self.Portfolio.TotalPortfolioValue
            trades        = []      # (sym, target_weight, Δqty)
            total_shares  = 0

            for sym, w in zip(selected, weights):
                if w <= 0:
                    continue
                price       = float(self.Securities[sym].Price)
                target_qty  = int((w * port_val) / price)
                current_qty = self.Portfolio[sym].Quantity
                delta       = target_qty - current_qty

                # honour per-symbol minimum change first
                if abs(delta) >= self.min_share_change:
                    trades.append((sym, w, delta))
                    total_shares += abs(delta)

            # ---------- portfolio-level guard ------------------------
            if total_shares < self.min_total_trade_qty:
                self.Debug(f"Rebalance skipped: only {total_shares} shares "
                        f"would change (<{self.min_total_trade_qty}).")
                self.days_since_rebalance += 1
                return

            # ---------- execute trades ------------------------------
            for sym, w, _ in trades:
                self.SetHoldings(sym, w)
                self.entry_prices[sym] = float(self.Securities[sym].Price)

            # *now* advance the clock for the rebalance window
            self.days_since_rebalance += 1
            return

        # ---------- 2) collect buffers between rebalances ----------
        if self.days_since_rebalance < self.rebalance_period:
            self._update_buffers(slice)
            self.days_since_rebalance += 1
            return

        # ---------- 3) end-of-period maintenance -------------------
        if self.days_since_rebalance == self.rebalance_period:
            self._roll_history()           # commit buffered data
            self._run_regression()         # refresh β / α
            self.Liquidate()               # clear residual positions
            self.entry_prices.clear()
            self.days_since_rebalance = 0


    # ------------ UTILITIES -----------------------------------------
    def _update_buffers(self, slice: Slice):
        """Append today’s log-price to each SymbolData buffer."""
        for sym, data in self.symbol_data.items():
            if slice.ContainsKey(sym) and slice[sym]:
                data.price_buf.append(np.log(float(slice[sym].Close)))
                data.time_buf.append(slice[sym].EndTime)

    def _roll_history(self):
        """Commit buffered data and keep last N days."""
        for data in self.symbol_data.values():
            if not data.price_buf:
                continue
            buf_df = pd.DataFrame({'log_price': data.price_buf},
                                  index=data.time_buf)
            ret    = buf_df['log_price'].diff().dropna()
            data.df = (pd.concat([data.df['log_return'], ret])
                       .iloc[-self.num_history_days:]
                       .to_frame('log_return'))
            data.mean      = data.df['log_return'].mean()
            data.price_buf = []
            data.time_buf  = []

    # ------------ one-month refresh --------------------
    def _refresh_one_month(self):
        """
        Re-compute rolling 21-day (≈1 month) cumulative log-return
        for every symbol, using both committed history and intraperiod
        buffers. Ensures the alpha signal includes today's return and
        removes the 1-day lag.
        """
        for data in self.symbol_data.values():

            # committed history
            hist_returns = data.df['log_return'].values

            # convert buffered log-prices to intraday returns
            if len(data.price_buf) >= 2:
                buf_returns = np.diff(data.price_buf)
                returns = np.concatenate([hist_returns, buf_returns])
            else:
                returns = hist_returns

            # 21-day rolling sum (shorter if insufficient history)
            data.one_month = returns[-TRADING_DAYS_PER_MONTH:].sum() if returns.size else 0.0

class Optimizer:
    """Mean-variance optimiser with optional long-only cap."""
    def __init__(self, symbols, means, cov,
                 long_only=True, max_weight=1.0):
        self.symbols    = symbols
        self.means      = means
        self.cov        = cov
        self.long_only  = long_only
        self.max_weight = max_weight

    # We minimizing the inverse Sharpe (annualised) (equivalent to maximising the annualised Sharpe ratio)
    def _objective(self, w):
        # self.cov and self.means are based on daily returns
        # Multiplying the mean by number of trading days within a year converts average daily return to expected annual return
        var = w.T @ self.cov @ w * TRADING_DAYS_PER_YEAR
        ret = w @ self.means * TRADING_DAYS_PER_YEAR
        return np.sqrt(var) / ret if ret != 0 else 1e6

    def optimize(self):
        n        = len(self.symbols)
        x0       = np.ones(n) / n
        cons     = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds   = [(0, self.max_weight)] * n if self.long_only \
                   else [(-self.max_weight, self.max_weight)] * n

        res = minimize(self._objective, x0,
                       method='SLSQP',
                       bounds=bounds, constraints=cons)
        return res.x if res.success else x0
