import json, time, urllib.request, pandas as pd

def fetch(inst="KSM-USDT", bar="1H", bars=12000):
    rows, after = [], ""
    while len(rows) < bars:
        url = f"https://www.okx.com/api/v5/market/history-candles?instId={inst}&bar={bar}&limit=100"
        if after: url += f"&after={after}"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
            data = json.load(r).get("data", [])
        if not data: break
        rows += data; after = data[-1][0]; time.sleep(0.15)
        print(len(rows), end="\r")
    df = pd.DataFrame(rows).iloc[:, :5]
    df.columns = ["ts", "open", "high", "low", "close"]
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
    df = df.astype({"close": float}).sort_values("ts").drop_duplicates("ts")
    df[["ts", "close"]].to_csv("ksm1h.csv", index=False)
    print(f"\nsaved {len(df)} bars  {df.ts.iloc[0]} -> {df.ts.iloc[-1]}")

if __name__ == "__main__":
    fetch()
  
