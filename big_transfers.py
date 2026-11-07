import os, sys, json, datetime, urllib.request, urllib.error

KEY = os.environ.get("PUBFI_API_KEY") or sys.exit("PUBFI_API_KEY is not set")
net, idx, min_ksm = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
addr = json.load(open("holders_" + net + ".json"))[idx]["address"]
url = f"https://api.pubfi.ai/v1/gateway/subscan/{net}/api/v2/scan/transfers:free"
body = {"address": addr, "row": int(sys.argv[4]), "page": 0, "min_amount": str(min_ksm)}
hdr = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=hdr)
try:
    d = json.load(urllib.request.urlopen(req, timeout=30)).get("data") or {}
except urllib.error.HTTPError as e:
    sys.exit("HTTP " + str(e.code) + " " + e.read(300).decode())
rows = d.get("transfers") or []
print("wallet:", addr)
print("total matching:", d.get("count"))
n = 0
for t in rows:
    amt = float(t["amount"])
    if amt < min_ksm or not t.get("success"):
        continue
    when = datetime.datetime.fromtimestamp(t["block_timestamp"], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    inc = t["to"] == addr
    o = t["from_account_display"] if inc else t["to_account_display"]
    pp = o.get("people") or {}
    name = pp.get("display") or (pp.get("parent") or {}).get("display") or o.get("display") or o.get("address", "")[:10]
    print(when, "IN " if inc else "OUT", round(amt, 2), name)
    n += 1
print("shown", n, "of", len(rows), "returned")
