import json, time, urllib.request, pandas as pd
rows, after = [], ""
while len(rows) < 12000:
    url = "https://www.okx.com/api/v5/market/history-candles?instId=KSM-USDT&bar=1H&limit=100"
    if after: url += "&after=" + after
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=20)).get("data", [])
    if not data: break
    rows += data; after = data[-1][0]; time.sleep(0.15)
    print(len(rows), end="\r")
df = pd.DataFrame(rows).iloc[:, :5]
df.columns = ["ts", "open", "high", "low", "close"]
df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
df["close"] = df["close"].astype(float)
df = df.sort_values("ts").drop_duplicates("ts")
df[["ts", "close"]].to_csv("ksm1h.csv", index=False)
print("saved", len(df), df.ts.iloc[0], "->", df.ts.iloc[-1])
