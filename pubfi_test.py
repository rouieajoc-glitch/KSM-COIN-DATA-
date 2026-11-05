import os
import sys
import urllib.request
import urllib.error

KEY = os.environ.get("PUBFI_API_KEY")
if not KEY:
    sys.exit("PUBFI_API_KEY is not set")

network = sys.argv[1] if len(sys.argv) > 1 else "kusama"
url = f"https://api.pubfi.ai/v1/gateway/subscan/{network}/api/now:free"
req = urllib.request.Request(url, headers={"Authorization": "Bearer " + KEY})
print("Calling:", url)

try:
    resp = urllib.request.urlopen(req, timeout=20)
    print("Status:", resp.status)
    print("Body:", resp.read(500).decode())
except urllib.error.HTTPError as e:
    print("HTTP error:", e.code)
    print(e.read(300).decode())
except Exception as e:
    print("Failed:", e)
