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

def ranks(x):
    idx = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[idx[j + 1]] == x[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2
        i = j + 1
    return r

random.seed(1)
print("metric lag horizon n spearman p-value | top10% flow days mean fwd return vs all days")
for m, fn in M.items():
    for lag in (1, 2):
        for h in (1, 3, 7):
            xs, ys = [], []
            for d in days:
                a, b = D.get(d + lag), D.get(d + lag + h)
                if a and b:
                    xs.append(fn(d))
                    ys.append((b / a - 1) * 100)
            n = len(xs)
            if n < 100 or not any(xs):
                continue
            rx, ry = ranks(xs), ranks(ys)
            mx, my = sum(rx) / n, sum(ry) / n
            cx = [v - mx for v in rx]
            cy = [v - my for v in ry]
            den = (sum(v * v for v in cx) * sum(v * v for v in cy)) ** 0.5
            rho = sum(map(mul, cx, cy)) / den
            big = 0
            N = 1000
            for _ in range(N):
                s = random.randint(30, n - 30)
                if abs(sum(map(mul, cx[s:] + cx[:s], cy)) / den) >= abs(rho):
                    big += 1
            p = (big + 1) / (N + 1)
            thr = sorted(xs)[int(0.9 * n)]
            top = [y for x, y in zip(xs, ys) if x > thr and x > 0]
            tm = sum(top) / len(top) if top else float("nan")
            print(f"{m:7} lag{lag} {h}d n={n} rho={rho:+.3f} p={p:.3f} | top10% {tm:+.2f}% (k={len(top)}) all {sum(ys)/n:+.2f}%")
