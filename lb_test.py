import sys, os, json, csv, time, random, datetime, urllib.request

arg = sys.argv[1] if len(sys.argv) > 1 else "730"
CACHE = "btc1h_okx.csv"

def fetch_okx(days):
    limit_ms = int(time.time() * 1000) - days * 86400000
    rows, after = {}, None
    while True:
        url = "https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT-SWAP&bar=1H&limit=100"
        if after:
            url += "&after=" + str(after)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            sys.exit("fetch failed: " + str(e))
        data = d.get("data") or []
        if not data:
            break
        for r in data:
            if len(r) > 8 and r[8] != "1":
                continue
            rows[int(r[0])] = (float(r[1]), float(r[2]), float(r[3]), float(r[4]))
        oldest = min(int(r[0]) for r in data)
        if oldest <= limit_ms:
            break
        after = oldest
        if len(rows) % 1000 < 100:
            print("fetched", len(rows), "bars")
        time.sleep(0.12)
    out = [(t,) + v for t, v in sorted(rows.items())]
    with open(CACHE, "w") as f:
        w = csv.writer(f)
        for r in out:
            w.writerow(r)
    return out

def load(path):
    out = []
    for r in csv.reader(open(path)):
        out.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])))
    return out

if arg.endswith(".csv"):
    bars = load(arg)
elif os.path.exists(CACHE):
    bars = load(CACHE)
    print("loaded cache", CACHE, "(delete it to refetch)")
else:
    bars = fetch_okx(int(arg))

def dstr(ts):
    return datetime.datetime.fromtimestamp(ts / 1000, datetime.timezone.utc).strftime("%Y-%m-%d")

print("bars", len(bars), dstr(bars[0][0]), "to", dstr(bars[-1][0]))

def atr14(b):
    n = len(b)
    tr = [b[0][2] - b[0][3]] + [max(b[i][2] - b[i][3], abs(b[i][2] - b[i - 1][4]), abs(b[i][3] - b[i - 1][4])) for i in range(1, n)]
    a = [None] * n
    s = sum(tr[:14]) / 14
    a[13] = s
    for i in range(14, n):
        s = (s * 13 + tr[i]) / 14
        a[i] = s
    return a

ATR = atr14(bars)

P = dict(tol=0.05, minBodyPct=0.15, doji=0.30, fakeN=5, sweepN=7)

def lb_fills(p):
    act, fills = [], []
    for i in range(15, len(bars)):
        t, o, h, l, c = bars[i]
        keep = []
        for lb in act:
            px, d, age = lb["px"], lb["dir"], i - lb["born"]
            pierced = (l < px) if d == 1 else (h > px)
            closeback = (c >= px) if d == 1 else (c <= px)
            if pierced:
                fills.append(dict(i=i, dir=d, px=px, swept=closeback))
                continue
            fake = age <= p["fakeN"] and ((c < px) if d == 1 else (c > px))
            if fake or age >= p["sweepN"]:
                continue
            keep.append(lb)
        act = keep
        a = ATR[i]
        pc, po = bars[i - 1][4], bars[i - 1][1]
        meet = abs(pc - o) <= p["tol"] * a
        b0, b1 = abs(c - o), abs(pc - po)
        r0, r1 = h - l, bars[i - 1][2] - bars[i - 1][3]
        ok0 = b0 / c * 100 >= p["minBodyPct"] and r0 > 0 and b0 >= p["doji"] * r0
        ok1 = b1 / pc * 100 >= p["minBodyPct"] and r1 > 0 and b1 >= p["doji"] * r1
        if meet and (ok0 or ok1):
            bull = pc < po and c > o
            bear = pc > po and c < o
            if bull or bear:
                act.append(dict(px=(pc + o) / 2, dir=1 if bull else -1, born=i))
    return fills

FEE_IN, FEE_SL, FEE_TP = 0.02, 0.05, 0.02

def simulate(fills, slpct, tpR, fees=True):
    out = []
    n = len(bars)
    for f in fills:
        d, px, i = f["dir"], f["px"], f["i"]
        risk = px * slpct / 100
        sl, tp = px - d * risk, px + d * risk * tpR
        res = None
        if (d == 1 and bars[i][3] <= sl) or (d == -1 and bars[i][2] >= sl):
            res = "sl"
        else:
            for j in range(i + 1, n):
                hh, ll = bars[j][2], bars[j][3]
                if (ll <= sl) if d == 1 else (hh >= sl):
                    res = "sl"
                    break
                if (hh >= tp) if d == 1 else (ll <= tp):
                    res = "tp"
                    break
        if res is None:
            continue
        gross = -1.0 if res == "sl" else float(tpR)
        cost = (FEE_IN + (FEE_SL if res == "sl" else FEE_TP)) / slpct if fees else 0.0
        out.append(dict(ts=bars[i][0], r=gross - cost, swept=f["swept"]))
    return out

def stats(tr):
    r = [t["r"] for t in tr]
    n = len(r)
    if n == 0:
        return None
    gp = sum(x for x in r if x > 0)
    gl = -sum(x for x in r if x < 0)
    eq = pk = dd = 0.0
    for x in r:
        eq += x
        pk = max(pk, eq)
        dd = max(dd, pk - eq)
    return dict(n=n, win=100 * sum(1 for x in r if x > 0) / n, mean=sum(r) / n, tot=sum(r),
                pf=gp / gl if gl > 0 else 9.99, dd=dd)

def show(name, tr):
    s = stats(tr)
    if not s:
        print(name, "no trades")
        return
    print(f"{name:14} n={s['n']:5d} win {s['win']:.0f}% avgR {s['mean']:+.3f} totR {s['tot']:+.0f} PF {s['pf']:.2f} DD {s['dd']:.0f}R")

def boot(tr, N=4000):
    r = [t["r"] for t in tr]
    random.seed(7)
    ms = sorted(sum(random.choices(r, k=len(r))) / len(r) for _ in range(N))
    return ms[int(0.025 * N)], ms[int(0.975 * N)]

SL, TP = 0.5, 3
fills = lb_fills(P)
print("LB fills (limit touched while LB alive):", len(fills), "| of which bar closed back (sweep):", sum(1 for f in fills if f["swept"]))
print(f"setup: LB 1h, limit at LB level, SL {SL}%, TP {TP}R, fees in/SL/TP {FEE_IN}/{FEE_SL}/{FEE_TP}%")
print()
allg = simulate(fills, SL, TP, fees=False)
alln = simulate(fills, SL, TP)
swg = [t for t in allg if t["swept"]]
swn = [t for t in alln if t["swept"]]
show("A sweep gross", swg)
show("A sweep net", swn)
show("B all gross", allg)
show("B all net", alln)
print("A = only fills where the bar closed back (needs hindsight). B = every touch (what a real limit order gets).")

for name, tr in (("A sweep net", swn), ("B all net", alln)):
    if len(tr) > 30:
        lo, hi = boot(tr)
        print(f"{name}: avgR 95% CI [{lo:+.3f}, {hi:+.3f}]")

print()
print("HALVES (net)")
for name, tr in (("A", swn), ("B", alln)):
    m = len(tr) // 2
    show(name + " first half", tr[:m])
    show(name + " 2nd half", tr[m:])

print()
by = {}
for t in alln:
    k = datetime.datetime.fromtimestamp(t["ts"] / 1000, datetime.timezone.utc).strftime("%Y-%m")
    by.setdefault(k, []).append(t["r"])
ms = sorted((sum(v), k, len(v)) for k, v in by.items())
pos = sum(1 for s, k, n in ms if s > 0)
print(f"B net by month: {pos}/{len(ms)} months positive")
print("worst:", ", ".join(f"{k} {s:+.0f}R" for s, k, n in ms[:3]))
print("best: ", ", ".join(f"{k} {s:+.0f}R" for s, k, n in ms[-3:]))

print()
print("SENSITIVITY: B net avgR (n) for TP 1R / 2R / 3R")
for sn in (3, 7, 12):
    f2 = lb_fills(dict(P, sweepN=sn))
    for sl in (0.5, 0.75, 1.0):
        cells = []
        for tp in (1, 2, 3):
            s = stats(simulate(f2, sl, tp))
            cells.append(f"{s['mean']:+.3f} ({s['n']})" if s else "n/a")
        print(f"N{sn:<2} SL{sl:<4} " + " | ".join(cells))
