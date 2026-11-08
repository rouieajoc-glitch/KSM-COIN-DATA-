import sys, json, datetime, random, statistics as st

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
days = sorted(D)
px = [D[d] for d in days]
n = len(px)
gaps = sum(1 for i in range(1, n) if days[i] - days[i - 1] != 1)
def dt(i):
    return datetime.datetime.fromtimestamp(days[i] * 86400, datetime.timezone.utc).strftime("%Y-%m-%d")
print("days", n, dt(0), "to", dt(n - 1), "| missing-day gaps:", gaps)

H = (7, 14, 30)
fwd = {h: [px[i + h] / px[i] - 1 if i + h < n else None for i in range(n)] for h in H}
base = {h: st.mean(x for x in fwd[h] if x is not None) for h in H}
print("all-days mean fwd return (the drift a short has to beat):",
      " ".join(f"{h}d {base[h]*100:+.1f}%" for h in H))
random.seed(5)

def events(X, L, cool=30):
    out, last = [], -999
    for i in range(L, n):
        if px[i] >= min(px[i - L:i + 1]) * (1 + X / 100) and i - last >= cool:
            out.append(i)
            last = i
    return out

def ev_cell(idx, h):
    r = [fwd[h][i] for i in idx if fwd[h][i] is not None]
    if len(r) < 4:
        return "n/a", None
    valid = [x for x in fwd[h] if x is not None]
    m = st.mean(r)
    lower = sum(1 for _ in range(3000) if st.mean(random.sample(valid, len(r))) <= m)
    return f"{m*100:+.1f}% p{(lower+1)/3001:.2f}", m

print()
print("PUMP EVENTS: mean KSM fwd return after signal (negative = shorting wins); p = chance a random set of days does as well")
for X in (20, 30, 50):
    for L in (7, 14):
        idx = events(X, L)
        cells = [ev_cell(idx, h)[0] for h in H]
        print(f"+{X}% in {L}d  n={len(idx):2d} | 7d {cells[0]} | 14d {cells[1]} | 30d {cells[2]}")
print("6 combos x 3 horizons = 18 looks, so expect ~1 p<0.05 by luck.")

X0, L0 = 30, 14
idx = events(X0, L0)
print()
print(f"DETAIL: +{X0}% in {L0}d, 30d cooldown, n={len(idx)}   (runup = highest later close in next 30d)")
ups = []
for i in idx:
    ru = max(px[i + 1:i + 31]) / px[i] - 1 if i + 1 < n else 0
    ups.append(ru)
    f14 = fwd[14][i]
    f30 = fwd[30][i]
    pump = px[i] / min(px[i - L0:i + 1]) - 1
    a14 = f"{f14*100:+.0f}%" if f14 is not None else "n/a"
    a30 = f"{f30*100:+.0f}%" if f30 is not None else "n/a"
    print(f" {dt(i)} pump {pump*100:+.0f}% | 14d {a14} | 30d {a30} | runup {ru*100:+.0f}%")
if ups:
    print(f"runup after signal: median {st.median(ups)*100:+.0f}%, worst {max(ups)*100:+.0f}%  <- what a short grid has to survive")
m = len(idx) // 2
for name, sub in (("first half", idx[:m]), ("2nd half", idx[m:])):
    c = ev_cell(sub, 14)[0] if len(sub) >= 4 else "n<4"
    print(f"{name}: n={len(sub)} 14d {c}")

pos = [None] * n
for i in range(90, n):
    w = px[i - 90:i + 1]
    lo, hi = min(w), max(w)
    pos[i] = (px[i] - lo) / (hi - lo) if hi > lo else 0.5
print()
print("P/D on pump events (position in 90d range: 1.0 = top):")
for name, sub in (("deep premium >=0.75", [i for i in idx if pos[i] is not None and pos[i] >= 0.75]),
                  ("below 0.75", [i for i in idx if pos[i] is not None and pos[i] < 0.75])):
    print(f" {name}: n={len(sub)} 14d {ev_cell(sub, 14)[0] if len(sub) >= 4 else 'n<4'}")

print()
print("P/D alone (state, every day; p from circular shifts of the state series):")
for thr in (0.75, 0.9):
    mask = [pos[i] is not None and pos[i] >= thr for i in range(n)]
    cells = []
    for h in H:
        sel = [fwd[h][i] for i in range(n) if mask[i] and fwd[h][i] is not None]
        if len(sel) < 20:
            cells.append("n/a")
            continue
        obs = st.mean(sel)
        lower = 0
        N = 1500
        for _ in range(N):
            s = random.randint(40, n - 40)
            mk = mask[s:] + mask[:s]
            sl = [fwd[h][i] for i in range(n) if mk[i] and fwd[h][i] is not None]
            if sl and st.mean(sl) <= obs:
                lower += 1
        cells.append(f"{obs*100:+.1f}% (n={len(sel)}) p{(lower+1)/(N+1):.2f}")
    print(f" pos>={thr}: 7d {cells[0]} | 14d {cells[1]} | 30d {cells[2]}")
