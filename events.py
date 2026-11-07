import os, sys, json, time, bisect, datetime, statistics as st
import urllib.request, urllib.error
from collections import defaultdict

KEY = os.environ.get("PUBFI_API_KEY") or sys.exit("PUBFI_API_KEY is not set")
nets = sys.argv[1].split(",")
min_usd = sys.argv[2]
pages = int(sys.argv[3]) if len(sys.argv) > 3 else 140
min_ksm = float(sys.argv[4]) if len(sys.argv) > 4 else 0
hdr = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}

def fetch(net, page):
    url = f"https://api.pubfi.ai/v1/gateway/subscan/{net}/api/v2/scan/transfers:free"
    body = {"row": 25, "page": page, "min_amount": min_usd, "asset_symbol": "KSM", "include_total": True}
    for a in range(4):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=hdr)
        try:
            return json.load(urllib.request.urlopen(req, timeout=30)).get("data") or {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(3 * (a + 1))
                continue
            sys.exit("HTTP " + str(e.code) + " " + e.read(300).decode())
    return {}

def side(t, s):
    o = t.get(s + "_account_display") or {}
    pp = o.get("people") or {}
    label = pp.get("display") or (pp.get("parent") or {}).get("display") or o.get("display")
    return o.get("address") or t.get(s) or "?", label

cache = "xfers_" + "_".join(nets) + "_" + str(min_usd) + ".json"
if os.path.exists(cache):
    rows = json.load(open(cache))
    print("loaded", len(rows), "transfers from", cache, "(delete the file to refetch)")
else:
    rows, seen = [], set()
    for net in nets:
        for p in range(pages):
            d = fetch(net, p)
            got = d.get("transfers") or []
            if p == 0:
                print(net, "total matching", d.get("count"))
            for t in got:
                if not t.get("success"):
                    continue
                fa, fl = side(t, "from")
                ta, tl = side(t, "to")
                k = (t.get("hash"), fa, ta, t.get("amount"))
                if k in seen:
                    continue
                seen.add(k)
                rows.append(dict(ts=t["block_timestamp"], amt=float(t["amount"]), frm=fa, to=ta, fl=fl, tl=tl))
            if p % 10 == 0:
                print(net, "page", p, "rows", len(rows))
            if len(got) < 25:
                break
            time.sleep(0.4)
    json.dump(rows, open(cache, "w"))
    print("saved", len(rows), "transfers to", cache)

rows = [r for r in rows if r["amt"] >= min_ksm]
rows.sort(key=lambda r: r["ts"])
print("transfers used", len(rows), "from", datetime.datetime.utcfromtimestamp(rows[0]["ts"]).date(),
      "to", datetime.datetime.utcfromtimestamp(rows[-1]["ts"]).date())

# ---- label addresses ----
cnt, peers, names = defaultdict(int), defaultdict(set), {}
for r in rows:
    for a, b, l in ((r["frm"], r["to"], r["fl"]), (r["to"], r["frm"], r["tl"])):
        cnt[a] += 1
        peers[a].add(b)
        if l:
            names[a] = l
role = {}
for a in cnt:
    n = (names.get(a) or "").lower()
    if "trsry" in n or "modlpy" in n:
        role[a] = "treasury"
    elif cnt[a] >= 15 and len(peers[a]) >= 5:
        role[a] = "hub"
    else:
        role[a] = "wallet"
hubs = [a for a in role if role[a] == "hub"]
json.dump({a: dict(role=role[a], label=names.get(a), events=cnt[a], peers=len(peers[a])) for a in cnt},
          open("addr_labels.json", "w"))
print("hubs found", len(hubs), "(full list in addr_labels.json)")
for a in sorted(hubs, key=lambda a: -cnt[a])[:10]:
    print(" ", a[:8], cnt[a], "events", len(peers[a]), "peers", names.get(a) or "")

# ---- prices ----
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
pts = []
if isinstance(raw, dict):
    pts = list(raw.items())
else:
    for r in raw:
        if isinstance(r, (list, tuple)) and len(r) >= 2:
            pts.append((r[0], r[1]))
        elif isinstance(r, dict):
            t = next((r[k] for k in ("t", "ts", "time", "timestamp", "date", "x") if k in r), None)
            p = next((r[k] for k in ("p", "price", "close", "c", "y") if k in r), None)
            pts.append((t, p))
ser = []
for t, p in pts:
    t, p = tsec(t), num(p)
    if t and p and p > 0:
        ser.append((t, p))
ser.sort()
if len(ser) < 10:
    sys.exit("could not read ksm_prices.json, first 300 chars: " + open("ksm_prices.json").read(300))
T = [x[0] for x in ser]
P = [x[1] for x in ser]
gap = st.median([T[i + 1] - T[i] for i in range(len(T) - 1)])
tol = max(gap * 1.5, 3600)
print("prices", len(ser), "points, median spacing", round(gap / 3600, 1), "h,",
      datetime.datetime.utcfromtimestamp(T[0]).date(), "to", datetime.datetime.utcfromtimestamp(T[-1]).date())

def px(t):
    i = bisect.bisect_right(T, t) - 1
    if i < 0 or t - T[i] > tol:
        return None
    return P[i]

def ret(t, h):
    if t + h * 3600 > T[-1]:
        return None
    a, b = px(t), px(t + h * 3600)
    return (b / a - 1) * 100 if a and b else None

HOR = [h for h in (1, 6, 24, 72) if h * 3600 >= gap]
base = {}
for h in HOR:
    rs = [x for x in (ret(t, h) for t in T) if x is not None]
    base[h] = (st.mean(rs), st.pstdev(rs)) if len(rs) > 20 else (0, 1)

# ---- classify events ----
ev = defaultdict(list)
last = {}
for r in rows:
    f, t = role[r["frm"]], role[r["to"]]
    if f == "hub" and t == "hub":
        continue
    if t == "hub":
        cls = "to_hub"
    elif f == "hub":
        cls = "from_hub"
    elif f == "treasury":
        cls = "treasury_out"
    else:
        cls = "wallet_wallet"
    keys = [cls] + (["big_" + cls] if r["amt"] >= 10000 and cls in ("to_hub", "from_hub") else [])
    for k in keys:
        if r["ts"] - last.get(k, 0) < 3600:
            continue
        last[k] = r["ts"]
        ev[k].append(r["ts"])

print()
print("class, horizon, n, mean/median return after event, % up, baseline mean, t-stat")
for k in sorted(ev):
    for h in HOR:
        rs = [x for x in (ret(t, h) for t in ev[k]) if x is not None]
        if len(rs) < 5:
            continue
        m = st.mean(rs)
        bm, bs = base[h]
        tstat = (m - bm) / (bs / len(rs) ** 0.5) if bs else 0
        up = 100 * sum(1 for x in rs if x > 0) / len(rs)
        print(f"{k:16} {h:>2}h n={len(rs):4d} mean {m:+.2f}% med {st.median(rs):+.2f}% up {up:.0f}% base {bm:+.2f}% t={tstat:+.1f}")
