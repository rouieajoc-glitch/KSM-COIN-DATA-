import sys, itertools, numpy as np, pandas as pd
FEE = 0.001
px = pd.read_csv(sys.argv[1], index_col=0).iloc[:,0].astype(float)

def run(p, win, k, stop):
    ma = p.rolling(win).mean(); sd = p.rolling(win).std()
    z = ((p-ma)/sd).values; v = p.values
    eq = 1.0; pos = False; n = 0; curve = []; prev = v[0]
    for i in range(len(v)):
        if pos: eq *= v[i]/prev
        prev = v[i]
        if pos and (z[i] >= 0 or z[i] <= -stop):
            eq *= (1-FEE); pos = False
        elif (not pos) and z[i] <= -k and z[i] > -stop:
            eq *= (1-FEE); pos = True; n += 1
        curve.append(eq)
    c = np.array(curve); dd = (c/np.maximum.accumulate(c)-1).min()
    return c[-1]-1, dd, n

h = len(px)//2; tr, te = px.iloc[:h], px.iloc[h:]
print(f"{len(px)} bars | B&H train {tr.iloc[-1]/tr.iloc[0]-1:+.1%} test {te.iloc[-1]/te.iloc[0]-1:+.1%}")
rows = []
for win, k, stop in itertools.product([48,168,336],[1.5,2,2.5],[3,4]):
    if stop <= k: continue
    a = run(tr, win, k, stop); b = run(te, win, k, stop)
    rows.append((win, k, stop, a[0], a[2], b[0], b[1], b[2]))
d = pd.DataFrame(rows, columns=["win","k","stop","train","trN","test","testDD","teN"])
print(d.sort_values("train", ascending=False).round(3).to_string(index=False))
print(f"\nbest-on-train -> test: {d.sort_values('train').iloc[-1]['test']:+.1%} | avg test across all: {d['test'].mean():+.1%}")
