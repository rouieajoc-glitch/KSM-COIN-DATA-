import os, sys, json, time, urllib.request, itertools, numpy as np, pandas as pd

COINS = ["KSM", "DOT", "ATOM", "AVAX"]

def fetch(coin, bars=12000):
    fn = f"{coin.lower()}1h.csv"
    if os.path.exists(fn): return fn
    rows, after = [], ""
    while len(rows) < bars:
        url = f"https://www.okx.com/api/v5/market/history-candles?instId={coin}-USDT&bar=1H&limit=100"
        if after: url += "&after=" + after
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.load(urllib.request.urlopen(req, timeout=20)).get("data", [])
        if not data: break
        rows += data; after = data[-1][0]; time.sleep(0.15)
    df = pd.DataFrame(rows).iloc[:, :5]; df.columns = ["ts","o","h","l","close"]
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
    df["close"] = df["close"].astype(float)
    df.sort_values("ts").drop_duplicates("ts")[["ts","close"]].to_csv(fn, index=False)
    return fn

def run(p, win, k, stop, fee):
    ma = p.rolling(win).mean(); sd = p.rolling(win).std()
    z = ((p-ma)/sd).values; v = p.values
    eq = 1.0; pos = False; prev = v[0]; n = 0
    for i in range(len(v)):
        if pos: eq *= v[i]/prev
        prev = v[i]
        if pos and (z[i] >= 0 or z[i] <= -stop): eq *= (1-fee); pos = False
        elif (not pos) and z[i] <= -k and z[i] > -stop: eq *= (1-fee); pos = True; n += 1
    return eq-1, n

def folds(px, nf=4):
    s = len(px)//nf
    return [px.iloc[i*s:(i+1)*s] for i in range(nf)]

data = {}
for c in COINS:
    try: data[c] = pd.read_csv(fetch(c), index_col=0).iloc[:,0].astype(float)
    except Exception as e: print(c, "fetch failed:", e)

pct = lambda x: f"{x:+6.1%}"
print("=== 1) KSM: window x k, 4 time folds, fee 0.2%/side ===")
print("(each cell = return in that quarter of the data, oldest -> newest)")
ksm = data["KSM"]; F = folds(ksm)
print(f"{'B&H':<14}", " ".join(pct(f.iloc[-1]/f.iloc[0]-1) for f in F))
for win, k in itertools.product([24,36,48,72,96], [2.0, 2.5]):
    r = [run(f, win, k, 3, 0.002) for f in F]
    print(f"win{win:<3} k{k:<4}   ", " ".join(pct(x[0]) for x in r), f" trades {sum(x[1] for x in r)}")

print("\n=== 2) Other coins: win48 k2.5 stop3, fee 0.2%/side ===")
tot = pos = 0
for c, px in data.items():
    F = folds(px)
    r = [run(f, 48, 2.5, 3, 0.002) for f in F]
    bh = [f.iloc[-1]/f.iloc[0]-1 for f in F]
    tot += 4; pos += sum(x[0] > 0 for x in r)
    print(f"{c:<5} strat", " ".join(pct(x[0]) for x in r), "|  B&H", " ".join(pct(b) for b in bh))
print(f"\nprofitable folds: {pos}/{tot}")

print("\n=== 3) Fee sensitivity, KSM win48 k2.5, full data ===")
for fee in [0.001, 0.002, 0.003]:
    r, n = run(ksm, 48, 2.5, 3, fee); print(f" fee {fee:.1%}/side: {pct(r)} ({n} trades)")
