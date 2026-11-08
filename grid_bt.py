import numpy as np, pandas as pd, sys, bisect, itertools

FEE = 0.001  # 0.1% per fill (spot taker-ish)

def synth(n=17520, seed=1):
    """Hourly synthetic price: regime switching (range / uptrend / downtrend)."""
    r = np.random.default_rng(seed); p = [20.0]; center = 20.0; reg = 0
    for i in range(n):
        if r.random() < 1/500: reg = r.choice([0,0,1,2])
        vol = 0.008
        if reg == 0:   # mean reverting
            ret = 0.04*(np.log(center/p[-1])) + r.normal(0, vol)
            center *= np.exp(r.normal(0, 0.0007))
        elif reg == 1: ret = 0.0006 + r.normal(0, vol)
        else:          ret = -0.0006 + r.normal(0, vol*1.2)
        p.append(p[-1]*np.exp(ret))
        if reg != 0: center = p[-1]
    return pd.Series(p[1:], index=pd.date_range("2024-01-01", periods=n, freq="h"))

def run_grid(prices, lo, hi, n, capital=1000.0, geo=True):
    L = np.geomspace(lo, hi, n+1) if geo else np.linspace(lo, hi, n+1)
    L = list(L); cash_cell = capital/n
    p0 = prices[0]; cells = []          # True = holds coin
    coins = cash = 0.0; trades = 0; qty = [cash_cell/L[i] for i in range(n)]
    cash = capital
    for i in range(n):
        if L[i] >= p0:
            cells.append(True); cash -= qty[i]*p0*(1+FEE); coins += qty[i]
        else: cells.append(False)
    eq = []; prev = p0; fees = 0
    for p in prices:
        if p < prev:
            k = bisect.bisect_right(L, prev) - 1
            while k >= 0 and L[k] > p:
                if k < n and L[k] <= prev and not cells[k]:
                    cost = qty[k]*L[k]*(1+FEE)
                    if cash >= cost: cash -= cost; coins += qty[k]; cells[k] = True; trades += 1
                k -= 1
