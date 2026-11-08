import sys, os, json, time, random, datetime, urllib.request, statistics as st

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 730
CACHE = "alts_daily.json"
COINS = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "DOT", "AVAX", "LINK", "LTC", "BCH", "ATOM", "NEAR",
         "APT", "ARB", "OP", "INJ", "SUI", "SEI", "TIA", "FIL", "UNI", "AAVE", "ETC", "TRX", "ICP", "HBAR",
         "XLM", "ALGO", "KSM", "CRV", "SAND", "MANA", "ENS", "LDO", "MKR", "SNX", "GALA", "FET", "PEPE",
         "WIF", "BONK", "RENDER", "STX", "RUNE", "IMX", "GRT", "EOS", "NEO", "ZEC"]

def fetch(coin, days):
    inst = coin + "-USDT-SWAP"
    limit_ms = int(time.time() * 1000) - days * 86400000
    rows, after = {}, None
    while True:
        url = "https://www.okx.com/api/v5/market/history-candles?instId=" + inst + "&bar=1Dutc&limit=100"
        if after:
            url += "&after=" + str(after)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            print(" ", coin, "fetch error:", e)
            return []
        data = d.get("data") or []
        if not data:
            break
        for r in data:
            if len(r) > 8 and r[8] != "1":
                continue
            rows[int(r[0])] = float(r[4])
        oldest = min(int(r[0]) for r in data)
        if oldest <= limit_ms or len(data) < 100:
            break
        after = oldest
        time.sleep(0.12)
    time.sleep(0.12)
    return sorted(rows.items())

if os.path.exists(CACHE):
    raw = json.load(open(CACHE))
    print("loaded cache", CACHE, "(delete it to refetch)")
else:
    raw = {}
    for c in COINS:
        s = fetch(c, DAYS)
        if len(s) >= 200:
            raw[c] = s
            print(c, len(s), "days")
        else:
            print(c, "skipped (not listed or too short)")
    json.dump(raw, open(CACHE, "w"))

ser = {}
for c, s in raw.items():
    days = [int(t // 86400000) for t, p in s]
    ser[c] = (days, [p for t, p in s])
print("coins:", len(ser), "|", ", ".join(sorted(ser)))

H = (7, 14, 30)
fwd = {h: {} for h in H}
for c, (days, px) in ser.items():
    for h in H:
        m = {}
        for i in range(len(px) - h):
            if days[i + h] - days[i] == h:
                m[days[i]] = px[i + h] / px[i] - 1
        fwd[h][c] = m
mkt = {}
for h in H:
    acc = {}
    for c in ser:
        for d, r in fwd[h][c].items():
            acc.setdefault(d, []).append(r)
    mkt[h] = {d: sum(v) / len(v) for d, v in acc.items() if len(v) >= 8}
drift = {h: {c: sum(fwd[h][c].values()) / len(fwd[h][c]) for c in ser if fwd[h][c]} for h in H}
print("average coin drift (a random short's tailwind):", " ".join(
    f"{h}d {sum(drift[h].values())/len(drift[h])*100:+.1f}%" for h in H))

def events(X, L, cool=30):
    out = []
    for c, (days, px) in ser.items():
        if c == "BTC":
            continue
        last = -999
        for i in range(L, len(px)):
            if days[i] - days[i - L] != L:
                continue
            if px[i] >= min(px[i - L:i + 1]) * (1 + X / 100) and days[i] - last >= cool:
                out.append((c, days[i], i))
                last = days[i]
    return out

def dstr(d):
    return datetime.datetime.fromtimestamp(d * 86400, datetime.timezone.utc).strftime("%Y-%m-%d")

random.seed(3)
def cluster_ci(items, N=2000):
    wk = {}
    for w, v in items:
        a = wk.setdefault(w, [0.0, 0])
        a[0] += v
        a[1] += 1
    ws = list(wk.values())
    if len(ws) < 5:
        return None
    ms = []
    for _ in range(N):
        pick = random.choices(ws, k=len(ws))
        ms.append(sum(p[0] for p in pick) / sum(p[1] for p in pick))
    ms.sort()
    return ms[int(0.025 * N)], ms[int(0.975 * N)], len(ws)

def evstats(evs, h):
    raw_, ex = [], []
    for c, d, i in evs:
        r = fwd[h][c].get(d)
        m = mkt[h].get(d)
        if r is None or m is None:
            continue
        raw_.append(r)
        ex.append((d // 7, r - m, r))
    if len(ex) < 8:
        return None
    ci = cluster_ci([(w, e) for w, e, r in ex])
    mean_ex = sum(e for w, e, r in ex) / len(ex)
    hit = 100 * sum(1 for w, e, r in ex if e < 0) / len(ex)
    return dict(n=len(ex), raw=sum(raw_) / len(raw_), ex=mean_ex, ci=ci, hit=hit)

print()
print("PRIMARY TEST (fixed before looking): +30% in 14d, 14d horizon, excess = coin return minus the average of all coins that day")
ev = events(30, 14)
s = evstats(ev, 14)
if s:
    lo, hi, wks = s["ci"] if s["ci"] else (float("nan"),) * 2 + (0,)
    print(f"events {s['n']} in {wks} distinct weeks | raw {s['raw']*100:+.1f}% | excess {s['ex']*100:+.1f}% 95% CI [{lo*100:+.1f}, {hi*100:+.1f}] | {s['hit']:.0f}% of events underperformed")
    ev_sorted = sorted(ev, key=lambda e: e[1])
    mid = ev_sorted[len(ev_sorted) // 2][1]
    for name, sub in (("first half", [e for e in ev if e[1] < mid]), ("2nd half", [e for e in ev if e[1] >= mid])):
        t = evstats(sub, 14)
        if t and t["ci"]:
            print(f"  {name}: n={t['n']} excess {t['ex']*100:+.1f}% CI [{t['ci'][0]*100:+.1f}, {t['ci'][1]*100:+.1f}]")

    ups = []
    for c, d, i in ev:
        days, px = ser[c]
        if i + 30 < len(px):
            ups.append((max(px[i + 1:i + 31]) / px[i] - 1, c, d))
    ups.sort()
    if ups:
        v = [u[0] for u in ups]
        print()
        print(f"SHORT-SIDE RISK (highest close in next 30d vs signal close), n={len(v)}:")
        print(f"  median {st.median(v)*100:+.0f}% | 90th pct {v[int(0.9*len(v))]*100:+.0f}% | worst {v[-1]*100:+.0f}%")
        print("  share above +20%: {:.0f}% | above +50%: {:.0f}% | above +100%: {:.0f}%".format(
            *(100 * sum(1 for x in v if x > t) / len(v) for t in (0.2, 0.5, 1.0))))
        print("  worst 5:", ", ".join(f"{c} {dstr(d)} {u*100:+.0f}%" for u, c, d in ups[-5:]))
else:
    print("too few events")

print()
print("EXPLORATORY GRID (18 looks, so a lone * is probably luck): excess vs market in % points [95% CI], * = CI excludes 0")
for X in (20, 30, 50):
    for L in (7, 14):
        evs = events(X, L)
        cells = []
        for h in H:
            t = evstats(evs, h)
            if not t or not t["ci"]:
                cells.append("n/a")
                continue
            lo, hi, w = t["ci"]
            star = "*" if (lo > 0 or hi < 0) else ""
            cells.append(f"{h}d {t['ex']*100:+.1f} [{lo*100:+.1f},{hi*100:+.1f}]{star}")
        print(f"+{X}%/{L}d n={len(evs):3d} | " + " | ".join(cells))
