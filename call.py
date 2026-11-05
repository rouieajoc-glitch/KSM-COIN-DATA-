import os
import sys
import urllib.request
import urllib.error

KEY = os.environ.get("PUBFI_API_KEY")
if not KEY:
    sys.exit("PUBFI_API_KEY is not set")

network = sys.argv[1]
route = sys.argv[2]
body = sys.argv[3] if len(sys.argv) > 3 else "{}"
url = f"https://api.pubfi.ai/v1/gateway/subscan/{network}/{route}:free"
headers = {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"}
req = urllib.request.Request(url, data=body.encode(), method="POST", headers=headers)
print("Calling:", url)

try:
    r = urllib.request.urlopen(req, timeout=30)
    print("Status:", r.status)
    print(r.read(1500).decode())
except urllib.error.HTTPError as e:
    print("HTTP error:", e.code)
    print(e.read(500).decode())
    if e.code == 402:
        print("402 = needs payment. STOP.")
except Exception as e:
    print("Failed:", e)
