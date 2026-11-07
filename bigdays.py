import json

p = json.load(open("ksm_prices.json"))
moves = []
for prev, cur in zip(p, p[1:]):
    pct = (cur["close"] / prev["close"] - 1) * 100
    moves.append((cur["date"], pct))

print("days:", len(moves))
for th in (5, 7, 10, 15):
    up = sum(1 for d, m in moves if m >= th)
    down = sum(1 for d, m in moves if m <= -th)
    print("moves >=", th, "%: up", up, "down", down)
print("price range:", min(x["low"] for x in p), "to", max(x["high"] for x in p))
