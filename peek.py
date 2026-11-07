import os, sys, json, datetime, urllib.request, urllib.error

KEY = os.environ.get("PUBFI_API_KEY") or sys.exit("PUBFI_API_KEY is not set")
net, idx, min_ksm, row = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
addr = json.load(open("holders_" + net + ".json"))[idx]["address"]
url = f"https://api.pubfi.ai/v1/gateway/subscan/{net}/api/v2/scan/transfers:free"
body = {"address": addr, "row": row, "page": 0, "min_amount": min_ksm}
hdr = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=hdr)
try:
    d = json.load(urllib.request.urlopen(req, timeout=30)).get("data") or {}
except urllib.error.HTTPError as e:
    sys.exit("row " + str(row) + " -> HTTP " + str(e.code))
rows = d.get("transfers") or []
print("row", row, "-> returned", len(rows), "total matching", d.get("count"))
for t in rows:
    when = datetime.datetime.fromtimestamp(t["block_timestamp"], datetime.timezone.utc).strftime("%Y-%m-%d")
    side = "IN " if t["to"] == addr else "OUT"
    print(when, side, t["amount"], t["asset_symbol"], "ok" if t.get("success") else "FAILED", "usd", t.get("current_currency_amount"))
