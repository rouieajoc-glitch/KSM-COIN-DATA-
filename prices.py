import json
import datetime
import urllib.request

url = "https://api.kraken.com/0/public/OHLC?pair=KSMUSD&interval=1440"
req = urllib.request.Request(url, headers={"User-Agent": "ksm-research"})
data = json.load(urllib.request.urlopen(req, timeout=30))
if data.get("error"):
    raise SystemExit(data["error"])
key = [k for k in data["result"] if k != "last"][0]
out = []
for r in data["result"][key]:
    day = datetime.datetime.fromtimestamp(r[0], datetime.timezone.utc).strftime("%Y-%m-%d")
    out.append({"date": day, "open": float(r[1]), "high": float(r[2]),
                "low": float(r[3]), "close": float(r[4]), "volume": float(r[6])})
json.dump(out, open("ksm_prices.json", "w"))
print(len(out), "days:", out[0]["date"], "to", out[-1]["date"])
print("last close:", out[-1]["close"])
