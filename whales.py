import os, sys, json, time, datetime, urllib.request, urllib.error
from collections import defaultdict

KEY = os.environ.get("PUBFI_API_KEY") or sys.exit("PUBFI_API_KEY is not set")
net, min_usd = sys.argv[1], sys.argv[2]
pages = int(sys.argv[3]) if len(sys.argv) > 3 else 4
url = f"https://api.pubfi.ai/v1/gateway/subscan/{net}/api/v2/scan/transfers:free"
hdr = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}

def fetch(page):
    body = {"row": 25, "page": page, "min_amount": min_usd, "asset_symbol": "KSM", "include_total": True}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=hdr)
    try:
        return json.load(urllib.request.urlopen(req, timeout=30)).get("data") or {}
    except urllib.error.HTTPError as e:
        sys.exit("HTTP " + str(e.code) + " " + e.read(300).decode())

def side(t, s):
    o = t.get(s + "_account_display") or {}
    pp = o.get("people") or {}
    label = pp.get("display") or (pp.get("parent") or {}).get("display") or o.get("display")
    addr = o.get("address") or t.get(s) or "?"
    return addr, label

def nm(a, l):
    return l or a[:8]

def fmt(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%m-%d %H:%M")

rows, seen = [], set()
for p in range(pages):
    d = fetch(p)
    got = d.get("transfers") or []
    if p == 0:
        print("total matching", d.get("count"))
    for t in got:
        if not t.get("success"):
            continue
        k = (t.get("hash"), t.get("from"), t.get("to"), t.get("amount"))
        if k in seen:
            continue
        seen.add(k)
        rows.append(t)
    if len(got) < 25:
        break
    time.sleep(0.3)

rows.sort(key=lambda t: t["block_timestamp"])
chains, labels = [], {}
for t in rows:
    fa, fl = side(t, "from")
    ta, tl = side(t, "to")
    labels[fa] = fl or labels.get(fa)
    labels[ta] = tl or labels.get(ta)
    amt = float(t["amount"])
    ts = t["block_timestamp"]
    usd = float(t.get("current_currency_amount") or 0)
    for c in chains:
        if c["to"] == fa and 0 <= ts - c["ts"] <= 600 and abs(amt - c["amt"]) <= 0.01 * c["amt"]:
            c["to"] = ta
            c["ts"] = ts
            c["hops"] += 1
            break
    else:
        chains.append(dict(start=ts, ts=ts, amt=amt, usd=usd, frm=fa, to=ta, hops=1))

print("raw transfers", len(rows), "-> events after collapsing relays", len(chains))
print("span", fmt(rows[0]["block_timestamp"]), "to", fmt(rows[-1]["block_timestamp"]))
print()
for c in sorted(chains, key=lambda c: -c["start"]):
    print(fmt(c["start"]), round(c["amt"]), "KSM", "$" + str(round(c["usd"])),
          nm(c["frm"], labels.get(c["frm"])), "->", nm(c["to"], labels.get(c["to"])),
          "(" + str(c["hops"]) + " hops)" if c["hops"] > 1 else "")

def rank(key, title):
    agg = defaultdict(lambda: [0, 0.0])
    for c in chains:
        agg[c[key]][0] += 1
        agg[c[key]][1] += c["amt"]
    print()
    print(title)
    for a, (n, s) in sorted(agg.items(), key=lambda x: -x[1][1])[:10]:
        print(" ", nm(a, labels.get(a)), n, "events", round(s), "KSM")

rank("frm", "TOP SENDERS")
rank("to", "TOP RECEIVERS")
