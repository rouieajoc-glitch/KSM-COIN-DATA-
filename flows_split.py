import sys, json, random, datetime
from operator import mul
from collections import defaultdict

net = sys.argv[1] if len(sys.argv) > 1 else "xfers_assethub-kusama_20000.json"
rows = json.load(open(net))
lab = json.load(open("addr_labels.json"))
hub = {a for a, v in lab.items() if v["role"] == "hub"}

def num(v):
    if isinstance(v, dict):
        for x in v.values():
            try:
                return float(x)
            except Exception:
                pass
        return None
    try:
        return float(v)
    except Exception:
        return None

def tsec(t):
    try:
        x = float(t)
        return x / 1000 if x > 1e12 else x
    except Exception:
        pass
    try:
        d = datetime.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return d.timestamp()
    except Exception:
        return None

raw = json.load(open("ksm_prices.json"))
if isinstance(raw, dict):
    for k in ("prices", "data", "price", "values"):
        if isinstance(raw.get(k), list):
            raw = raw[k]
            break
pts = list(raw.items()) if isinstance(raw, dict) else []
if not pts:
    for r in raw:
        if isinstance(r, (list, tuple)) and len(r) >= 2:
            pts.append((r[0], r[1]))
        elif isinstance(r, dict):
            t = next((r[k] for k in ("t", "ts", "time", "timestamp", "date", "x") if k in r), None)
            p = next((r[k] for k in ("p", "price", "close", "c", "y") if k in r), None)
            pts.append((t, p))
D = {}
for t, p in pts:
    t, p = tsec(t), num(p)
    if t and p and p > 0:
        D[int(t // 86400)] = p
d0, d1 = min(D), max(D)
days = [d for d in range(d0, d1 + 1) if d in D]
print("price days", len(days))

# daily flows in USD at the price of that day
F = defaultdict(lambda: [0.0, 0.0])
for r in rows:
    d = int(r["ts"] // 86400)
    if d not in D:
        continue
    f, t = r["frm"] in hub, r["to"] in hub
    if f == t:
        continue
    usd = r["amt"]
    F[d][0 if t else 1] += usd
M = {
    "net_in": lambda d: F[d][0] - F[d][1] if d in F else 0.0,
    "in": lambda d: F[d][0] if d in F else 0.0,
    "out": lambda d: F[d][1] if d in F else 0.0,
    "total": lambda d: sum(F[d]) if d in F else 0.0,
}

def rk(x):
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2
        i = j + 1
    return r

def spear(a, b):
    ra, rb = rk(a), rk(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((p - ma) * (q - mb) for p, q in zip(ra, rb))
    den = (sum((p - ma) ** 2 for p in ra) * sum((q - mb) ** 2 for q in rb)) ** 0.5
    return num / den

def dt(d):
    return datetime.datetime.fromtimestamp(d * 86400, datetime.timezone.utc).date()

xs, ys, ds = [], [], []
for d in days:
    a, b = D.get(d + 1), D.get(d + 2)
    if a and b:
        xs.append(M["out"](d))
        ys.append((b / a - 1) * 100)
        ds.append(d)
n = len(xs)
mid = n // 2
print()
print("HALVES: out flow vs next-day return (lag1, 1d)")
for name, sl in (("first ", slice(0, mid)), ("second", slice(mid, n))):
    x, y = xs[sl], ys[sl]
    thr = sorted(x)[int(0.9 * len(x))]
    top = [b for a, b in zip(x, y) if a > thr and a > 0]
    print(name, dt(ds[sl][0]), "to", dt(ds[sl][-1]), "rho", round(spear(x, y), 3),
          "| top10% mean", round(sum(top) / len(top), 2), "k=" + str(len(top)),
          "| all days mean", round(sum(y) / len(y), 2))

FEE = 0.1
W = 90
tr = []
for i in range(W, n):
    thr = sorted(xs[i - W:i])[int(0.9 * W)]
    if xs[i] > thr and xs[i] > 0:
        tr.append((i, -ys[i] - FEE))
print()
print("RULE: short next day after an outflow day above trailing-90d 90th pct, fee", FEE, "% round trip")
for name, f in (("all    ", lambda i: True), ("first  ", lambda i: i < mid), ("second ", lambda i: i >= mid)):
    t = [r for i, r in tr if f(i)]
    allshort = [-ys[i] - FEE for i in range(W, n) if f(i)]
    if t:
        print(name, "trades", len(t), "mean", round(sum(t) / len(t), 2), "% win", round(100 * sum(1 for r in t if r > 0) / len(t)),
              "% sum", round(sum(t), 1), "% | short-every-day mean", round(sum(allshort) / len(allshort), 2), "%")
