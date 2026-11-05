import json
import urllib.parse
import urllib.request

BASE = "https://api.pubfi.ai/v1/capabilities"
cursor = None
found = []
while True:
    params = {"provider_key": "subscan"}
    if cursor:
        params["cursor"] = cursor
    url = BASE + "?" + urllib.parse.urlencode(params)
    data = json.load(urllib.request.urlopen(url, timeout=30))
    for c in data["capabilities"]:
        m = c["matcher"]
        if m["kind"] == "exact":
            path = m["path"]
        else:
            parts = []
            for p in m["template"]:
                parts.append(p["value"] if p["kind"] == "literal" else "{" + p["name"] + "}")
            path = "/" + "/".join(parts)
        free = "FREE" if "free_rate_limit" in c else "paid"
        found.append((path, c["methods"][0], free))
    cursor = data.get("next_cursor")
    if not cursor:
        break

words = ("transfer", "holder", "balance")
for path, method, free in sorted(found):
    if "{network}" in path and any(w in path for w in words):
        print(free, method, path)
print("total routes:", len(found))
