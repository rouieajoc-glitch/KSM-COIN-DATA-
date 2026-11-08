import numpy as np, pandas as pd, sys, bisect, itertools
FEE = 0.001

def synth(n=12000, seed=1):
    r = np.random.default_rng(seed); p=[20.0]; c=20.0; reg=0
    for i in range(n):
        if r.random() < 1/500: reg = r.choice([0,0,1,2])
        if reg == 0: ret = 0.04*np.log(c/p[-1]) + r.normal(0,.008); c *= np.exp(r.normal(0,.0007))
        elif reg == 1: ret = 0.0006 + r.normal(0,.008)
        else: ret = -0.0006 + r.normal(0,.0096)
        p.append(p[-1]*np.exp(ret))
        if reg: c = p[-1]
    return pd.Series(p[1:], index=pd.date_range("2025-01-01", periods=n, freq="h"))

def run_grid(prices, lo, hi, n, capital=1000.0):
    L = list(np.geomspace(lo, hi, n+1)); cc = capital/n
    qty = [cc/L[i] for i in range(n)]; p0 = prices[0]
    cells=[]; coins=0.0; cash=capital
    for i in range(n):
        if L[i] >= p0:
            cells.append(True); cash -= qty[i]*p0*(1+FEE); coins += qty[i]
        else: cells.append(False)
    eq=[]; prev=p0; trades=0
    for p in prices:
        if p < prev:
            k = bisect.bisect_right(L, prev)-1
            while k >= 0 and L[k] > p:
                if k < n and L[k] <= prev and not cells[k]:
                    cost = qty[k]*L[k]*(1+FEE)
                    if cash >= cost:
                        cash-=cost; coins+=qty[k]; cells[k]=True; trades+=1
                k -= 1
        elif p > prev:
            k = bisect.bisect_right(L, prev)
            while k <= n and L[k] <= p:
                if 0 < k <= n and cells[k-1]:
                    cash += qty[k-1]*L[k]*(1-FEE); coins -= qty[k-1]; cells[k-1]=False; trades+=1
                k += 1
        prev = p; eq.append(cash + coins*p)
    return np.array(eq), trades

def stats(eq, cap=1000.0):
    pk = np.maximum.accumulate(eq)
    return eq[-1]/cap-1, ((eq-pk)/pk).min()

def walk_forward(px, win=720, hold=336, n=20, width=0.15, trend_max=None, stop=None):
    v = px.values; cap=1000.0; curve=[cap]*win; i=win
    while i+hold <= len(v):
        seg=v[i:i+hold]; past=v[i-win:i]; ref=np.median(past)
        lo, hi = ref*(1-width), ref*(1+width)
        trend = past[-1]/past[0]-1
        if seg[0]<lo or seg[0]>hi or (trend_max and abs(trend)>trend_max):
            curve += [cap]*hold
        else:
            eq,_ = run_grid(seg, lo, hi, n, cap)
            if stop:
                bad = np.where(seg < lo*(1-stop))[0]
                if len(bad): eq[bad[0]:] = eq[bad[0]]
            curve += list(eq); cap = eq[-1]
        i += hold
    return np.array(curve[win:]), v[win:]

if __name__ == "__main__":
    px = pd.read_csv(sys.argv[1], index_col=0, parse_dates=True).iloc[:,0] if len(sys.argv)>1 else synth()
    print(f"{len(px)} bars {px.index[0]} -> {px.index[-1]} | price {px.iloc[0]:.2f} -> {px.iloc[-1]:.2f} ({px.iloc[-1]/px.iloc[0]-1:+.1%})")
    half = len(px)//2; train, test = px.iloc[:half], px.iloc[half:]
    print("\nSTATIC GRID, train half")
    for w, n in itertools.product([0.15,0.25,0.40],[10,20,40]):
        ref=train.iloc[0]; lo,hi=ref*(1-w),ref*(1+w)
        eq,t=run_grid(train.values,lo,hi,n); r,d=stats(eq)
        print(f" ±{w:.0%} n={n:<3} step {(hi/lo)**(1/n)-1:.1%}  ret {r:+.1%}  dd {d:.1%}  trades {t}")
    print("\nWALK-FORWARD on test half")
    for name, kw in [("no filter",{}),("stop 5%",{"stop":0.05}),("trend<15%",{"trend_max":0.15}),
                     ("trend<15% + stop 5%",{"trend_max":0.15,"stop":0.05}),
                     ("trend<10% + stop 3%",{"trend_max":0.10,"stop":0.03})]:
        c, v = walk_forward(test, width=0.15, n=20, **kw); r,d = stats(c)
        print(f" {name:<22} ret {r:+.1%}  dd {d:.1%}")
    print(f" buy&hold same period    ret {v[-1]/v[0]-1:+.1%}")
