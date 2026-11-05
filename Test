"""Step 1: confirm the PubFi key works on a FREE Subscan route.

Usage:
    export PUBFI_API_KEY='your-key'      # never put the key in this file
    python pubfi_test.py                 # tries network "kusama"
    python pubfi_test.py assethub-kusama # try Asset Hub (name is a guess)

It only calls the ':free' variant. If the server answers 402 (payment
needed) the script stops. It never retries on a billed route.
"""
import os
import sys
import urllib.error
import urllib.request

KEY = os.environ.get("PUBFI_API_KEY")
if not KEY:
    sys.exit("Set PUBFI_API_KEY first (export PUBFI_API_KEY='...').")

BASE = "https://api.pubfi.ai"
NETWORK = sys.argv[1] if len(sys.argv) > 1 else "kusama"

# Free variant = exact route path + ':free' (see the Subscan/PubFi tutorial)
url = f"{BASE}/v1/gateway/subscan/{NETWORK}/api/now:free"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {KEY}"})

print("Calling:", url)
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("Status:", resp.status)
        for name, value in resp.headers.items():
            if "limit" in name.lower() or "retry" in name.lower():
                print(f"Header {name}: {value}")
        print("Body:", resp.read(500).decode("utf-8", "replace"))
except urllib.error.HTTPError as e:
    body = e.read(300).decode("utf-8", "replace")
    print("HTTP error:", e.code)
    print("Body:", body)
    if e.code == 402:
        print("402 = this route needs payment. STOP, do not pay or retry.")
    elif e.code == 401:
        print("401 = key missing or wrong.")
    elif e.code == 429:
        print("429 = rate limited. Wait and slow down.")
except Exception as e:  # network problems, timeouts, etc.
