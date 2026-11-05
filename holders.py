import os
import sys
import json
import urllib.request
import urllib.error

KEY = os.environ.get("PUBFI_API_KEY")
if not KEY:
    sys.exit("PUBFI_API_KEY is not set")

network = sys.argv[1] if len(sys.argv) > 1 else "kusama"
rows = int(sys.argv[2]) if len(sys.argv) > 2 else 20
url = f"https://api.pubfi.ai/v1/gateway/subscan/{network}/api/scan/token/holders:free"
body = json.dumps({"row": rows, "page": 0, "unique_id": "KSM"}).encode()
headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
req = urllib.request.Request(url, data=body, method="POST", headers=headers)

try:
    data = json.load(urllib.request.urlopen(req, timeout=30))
except urllib.error.HTTPError as e:
    sys.exit("HTTP " + str(e.code) + ": " + e.read(300).decode())

holders = (data.get("data") or {}).get("list") or []
if not holders:
    sys.exit("No holders found: " + json.dumps(data)[:500])

out = []
for h in holders:
    disp = h.get("account_display") or {}
    people = disp.get("people") or {}
    ksm = int(h["balance"]) / 10**12
    out.append({"address": disp.get("address"), "ksm": ksm, "label": people.get("display")})

out.sort(key=lambda x: x["ksm"], reverse=True)
for i, o in enumerate(out, 1):
    print(i, o["address"], round(o["ksm"], 2), o["label"] or "")

with open("holders_" + network + ".json", "w") as f:
    json.dump(out, f, indent=1)
print("saved", len(out), "holders")
