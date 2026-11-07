import os
import sys
import json
import urllib.request
import urllib.error

KEY = os.environ.get("PUBFI_API_KEY")
if not KEY:
    sys.exit("PUBFI_API_KEY is not set")

network = sys.argv[1] if len(sys.argv) > 1 else "assethub-kusama"
idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
holders = json.load(open("holders_" + network + ".json"))
addr = holders[idx]["address"]
print("wallet:", addr, holders[idx]["label"])

url = f"https://api.pubfi.ai/v1/gateway/subscan/{network}/api/v2/scan/transfers:free"
body = json.dumps({"address": addr, "row": 5, "page": 0}).encode()
headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
req = urllib.request.Request(url, data=body, method="POST", headers=headers)
try:
    data = json.load(urllib.request.urlopen(req, timeout=30))
except urllib.error.HTTPError as e:
    sys.exit("HTTP " + str(e.code) + ": " + e.read(300).decode())

d = data.get("data") or {}
print("count:", d.get("count"))
rows = d.get("transfers") or []
if rows:
    print("fields:", list(rows[0].keys()))
print(json.dumps(rows[:2])[:1500])
