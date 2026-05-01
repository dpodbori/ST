import backtrader as bt
import numpy as np
import streamlit as st


def show_parameters():
    return {
        'vol_period': st.number_input("Volatility Period", value=20, min_value=1, step=1),
        'delta': st.number_input("Delta (Q/R Adaptation)", value=1e-4, min_value=0.0, step=1e-5),
        'R_base': st.number_input("Base R", value=0.1, min_value=0.0, step=0.01),
        'R_scale': st.number_input("R Scale Factor", value=1.0, min_value=0.0, step=0.1),
        'Q_scale_factor': st.number_input("Q Scale Factor", value=0.5, min_value=0.0, step=0.1),
        'initial_cov': st.number_input("Initial Covariance", value=1.0, min_value=0.0, step=0.1),
    }
    
# ─── 1) Custom LogReturns Indicator ─────────────────────────────────────────────
class LogReturns(bt.Indicator):
    lines = ('logret',)
    params = (('period', 1),)

    def __init__(self):
        # ensure we have at least period+1 bars before next() runs
        self.addminperiod(self.p.period + 1)

    def next(self):
        price_now  = self.data[0]
        price_prev = self.data[-self.p.period]
        if price_prev and not np.isnan(price_prev):
            self.lines.logret[0] = np.log(price_now / price_prev)
        else:
            self.lines.logret[0] = np.nan

# ─── 2) Adaptive Kalman Filter Strategy ──────────────────────────────────────────
class AdaptiveKalmanFilterStrategy(bt.Strategy):
    # declare plot‐lines and subplots
    lines = (
        'kf_price',
        'kf_velocity',
        'adaptive_R',
        'adaptive_Q0',
        'adaptive_Q1',
    )
    plotlines = dict(
        kf_price    = dict(_name='KF Price',    subplot=False),
        kf_velocity = dict(_name='KF Velocity', subplot=True),
        adaptive_R  = dict(_name='R',           subplot=True),
        adaptive_Q0 = dict(_name='Q[0,0]',      subplot=True),
        adaptive_Q1 = dict(_name='Q[1,1]',      subplot=True),
    )

    params = dict(
        vol_period     = 20,
        delta          = 1e-4,
        R_base         = 0.1,
        R_scale        = 1.0,
        Q_scale_factor = 0.5,
        initial_cov    = 1.0,
        printlog       = False,
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def __init__(self):
        # data
        self.data_close = self.datas[0].close

        # ——— Kalman state & matrices ———
        self.x = np.zeros(2)  # [level, velocity]
        self.P = np.eye(2) * self.params.initial_cov
        self.F = np.array([[1., 1.],
                           [0., 1.]])
        self.H = np.array([[1., 0.]])
        self.I = np.eye(2)
        self.initialized = False

        # Initialize Q and R so they'll exist before first next()
        self.Q = np.eye(2) * self.params.delta
        self.R = self.params.R_base

        # ——— Indicators ———
        # 1-bar log returns
        self.log_returns = LogReturns(self.data_close, period=1)
        # rolling volatility
        self.volatility  = bt.indicators.StandardDeviation(
            self.log_returns.logret,
            period=self.params.vol_period
        )

    def _initialize_kalman(self, price):
        self.x[:] = [price, 0.0]
        self.P    = np.eye(2) * self.params.initial_cov
        self.initialized = True
        self.log(f'KF initialized at price={price:.2f}')

    def next(self):
        price = self.data_close[0]

        # —— wait for enough bars to init KF & vol —— 
        if not self.initialized:
            if len(self) > self.params.vol_period and not np.isnan(self.volatility[0]):
                self._initialize_kalman(price)
            return

        vol = self.volatility[0]
        # if vol or price is NaN, push NaNs to keep plot aligned
        if np.isnan(vol) or np.isnan(price):
            for ln in self.lines:
                getattr(self.lines, ln)[0] = np.nan
            return

        # ——— Predict ———
        self.x = self.F.dot(self.x)
        self.P = self.F.dot(self.P).dot(self.F.T) + self.Q

        # ——— Adapt Q & R ———
        vol = max(vol, 1e-8)
        self.R = self.params.R_base * (1 + self.params.R_scale * vol)
        qvar = self.params.delta * (1 + self.params.Q_scale_factor * vol**2)
        self.Q = np.diag([qvar, qvar])

        # ——— Update ———
        y = price - (self.H.dot(self.x))[0]
        S = (self.H.dot(self.P).dot(self.H.T))[0, 0] + self.R
        K = self.P.dot(self.H.T) / S
        self.x = self.x + (K.flatten() * y)
        self.P = (self.I - K.dot(self.H)).dot(self.P)

        # ——— Record lines ———
        self.lines.kf_price[0]    = self.x[0]
        self.lines.kf_velocity[0] = self.x[1]
        self.lines.adaptive_R[0]  = self.R
        self.lines.adaptive_Q0[0] = self.Q[0, 0]
        self.lines.adaptive_Q1[0] = self.Q[1, 1]

        # ——— Trading: full long & short ———
        vel = self.x[1]
        if not self.position:
            if vel > 0:
                self.log(f'BUY (vel={vel:.4f})')
                self.buy()
            elif vel < 0:
                self.log(f'SELL SHORT (vel={vel:.4f})')
                self.sell()
        elif self.position.size > 0 and vel < 0:
            self.log(f'CLOSE LONG & SELL SHORT (vel={vel:.4f})')
            self.close(); self.sell()
        elif self.position.size < 0 and vel > 0:
            self.log(f'CLOSE SHORT & BUY LONG (vel={vel:.4f})')
            self.close(); self.buy()

    def stop(self):
        self.log(f'Ending Portfolio Value: {self.broker.getvalue():.2f}')
