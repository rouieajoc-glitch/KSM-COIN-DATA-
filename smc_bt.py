import os, sys, json, time, urllib.request, numpy as np, pandas as pd

SYM = "BTC-USDT"; FEE_RT = 0.001
MAXBARS = {"15m": 150000, "1H": 100000, "4H": 30000}
HOLD = {"15m": 192, "1H": 96, "4H": 60}
MIN = {"15m": 15, "1H": 60, "4H": 240}

def load(bar):
    fn = f"btc_{bar}.csv"
    if os.path.exists(fn): return pd.read_csv(fn)
    rows, after = [], ""
    while len(rows) < MAXBARS[bar]:
        url = f"https://www.okx.com/api/v5/market/history-candles?instId={SYM}&bar={bar}&limit=100" + (f"&after={after}" if after else "")
        try: d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20)).get("data", [])
        except Exception as e: print("retry", e); time.sleep(2); continue
        if not d: break
        rows += d; after = d[-1][0]; time.sleep(0.12)
        print(f"  {bar}: {len(rows)} bars", end="\r")
    df = pd.DataFrame(rows).iloc[:, :5]; df.columns = ["ts", "o", "h", "l", "c"]
    df = df.astype(float).sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    df.to_csv(fn, index=False); return df

def rma(x, n):
    out = np.empty(len(x)); out[0] = x[0]
    for i in range(1, len(x)): out[i] = (out[i-1]*(n-1) + x[i]) / n
    return out

def atr(h, l, c, n):
    pc = np.r_[c[0], c[:-1]]
    return rma(np.maximum.reduce([h-l, abs(h-pc), abs(l-pc)]), n)

def pd_state(df4):
    h, l = df4.h.values, df4.l.values; n = len(h); L = 5
    hiP = loP = np.nan; trH = trL = np.nan; RH = np.full(n, np.nan); RL = np.full(n, np.nan)
    for k in range(n):
        trH = h[k] if np.isnan(trH) else max(trH, h[k]); trL = l[k] if np.isnan(trL) else min(trL, l[k])
        j = k - L
        if j >= L:
            if h[j] == h[j-L:k+1].max(): hiP = h[j]; trH = h[j]
            if l[j] == l[j-L:k+1].min(): loP = l[j]; trL = l[j]
        if not (np.isnan(hiP) or np.isnan(loP)):
            RH[k] = max(hiP, trH); RL[k] = min(loP, trL)
    return RH, RL

def scan(df, tf, df4):
    o, h, l, c = (df[x].values for x in "ohlc"); ts = df.ts.values; n = len(c)
    a14 = atr(h, l, c, 14); a200 = atr(h, l, c, 200)
    RH4, RL4 = pd_state(df4); close4 = df4.ts.values + 240*60*1000
    if tf == "4H": kmap = np.arange(n)
    else: kmap = np.searchsorted(close4, ts + MIN[tf]*60*1000, side="right") - 1
    class Pv: cur = np.nan; bar = 0; crossed = False
    inH, inL, swH, swL = Pv(), Pv(), Pv(), Pv()
    leg = {5: 0, 50: 0}; pH = np.where((h-l) >= 2*a200, l, h); pL = np.where((h-l) >= 2*a200, h, l)
    obs = []; fv = {"bull": [], "bear": []}; bprs = []; lbs = []; sigs = []
    def upd_pivots(i, size, hi, lo):
        if i < size: return
        newH = h[i-size] > h[i-size+1:i+1].max(); newL = l[i-size] < l[i-size+1:i+1].min()
        new = 0 if newH else (1 if newL else leg[size])
        if new != leg[size]:
            if new == 1: lo.cur, lo.bar, lo.crossed = l[i-size], i-size, False
            else:        hi.cur, hi.bar, hi.crossed = h[i-size], i-size, False
            leg[size] = new
    pcur = {"inH": np.nan, "inL": np.nan}
    for i in range(15, n):
        keep = []
        for lb in lbs:
            age = i - lb["born"]
            if age <= 5 and c[i] > lb["px"]: continue
            if h[i] > lb["px"] and c[i] <= lb["px"]:
                lvl = lb["px"]; tol = 0.25*a14[i]
                in_ob = any((not z["dead"]) and z["bias"] == -1 and z["rank"] < 5 and min(z["hi"], z["lo"])-tol <= lvl <= max(z["hi"], z["lo"])+tol for z in obs)
                in_bpr = any(b["bot"]-tol <= lvl <= b["top"]+tol for b in bprs)
                k = kmap[i]; prem = False
                if k >= 0 and not np.isnan(RH4[k]):
                    rh, rl = RH4[k], RL4[k]
                    if tf != "4H":
                        s = np.searchsorted(ts, close4[k]-1, side="right")
                        if s <= i: rh = max(rh, h[s:i+1].max()); rl = min(rl, l[s:i+1].min())
                    prem = lvl > (rh + rl)/2
                stop = max(h[lb["born"]:i+1].max(), h[i]) + 0.1*a14[i]
                sigs.append(dict(i=i, ts=ts[i], lvl=lvl, prem=prem, ob=in_ob, bpr=in_bpr, stop=stop))
                continue
            if age >= 7: continue
            keep.append(lb)
        lbs = keep
        body0, body1 = abs(c[i]-o[i]), abs(c[i-1]-o[i-1])
        ok0 = body0/c[i]*100 >= 0.15 and body0 >= 0.3*(h[i]-l[i]); ok1 = body1/c[i-1]*100 >= 0.15 and body1 >= 0.3*(h[i-1]-l[i-1])
        if c[i-1] > o[i-1] and c[i] < o[i] and abs(c[i-1]-o[i]) <= 0.05*a14[i] and (ok0 or ok1):
            lbs.append(dict(px=(c[i-1]+o[i])/2, born=i))
        for z in obs:
            if not z["dead"] and i > z["cb"] and ((z["bias"] == -1 and h[i] > max(z["hi"], z["lo"])) or (z["bias"] == 1 and l[i] < min(z["hi"], z["lo"]))): z["dead"] = True
        upd_pivots(i, 5, inH, inL); upd_pivots(i, 50, swH, swL)
        up_w = h[i]-max(c[i], o[i]); lo_w = min(c[i], o[i]-l[i])
        bullbar, bearbar = up_w > lo_w, up_w < lo_w
        for bias, p, x_ok in ((1, inH, c[i] > inH.cur and c[i-1] <= pcur["inH"]), (-1, inL, c[i] < inL.cur and c[i-1] >= pcur["inL"])):
            if x_ok and not p.crossed and p.cur != (swH.cur if bias == 1 else swL.cur) and (bullbar if bias == 1 else bearbar):
                p.crossed = True; base = p.bar
                if base < i:
                    idx = base + int(np.argmax(pH[base:i]) if bias == -1 else np.argmin(pL[base:i]))
                    if not any(z["t"] == idx and z["bias"] == bias for z in obs):
                        obs.insert(0, dict(hi=pH[idx], lo=pL[idx], bias=bias, t=idx, cb=i, dead=False))
        pcur["inH"], pcur["inL"] = inH.cur, inL.cur
        del obs[100:]
        obs[:] = [z for z in obs if not z["dead"]]
        for r, z in enumerate(obs): z["rank"] = r
        if i > 25:
            bull = l[i] > h[i-2] and (l[i]-h[i-2]) >= 0.1*a14[i]
            bear = h[i] < l[i-2] and (l[i-2]-h[i]) >= 0.1*a14[i]
            for kind, ok, top, bot, opp in (("bull", bull, l[i], h[i-2], "bear"), ("bear", bear, l[i-2], h[i], "bull")):
                if not ok: continue
                for (gi, gt, gb) in fv[opp][-1:]:
                    if i - gi <= 100:
                        t, b = min(top, gt), max(bot, gb)
                        if t > b and (t-b) >= 0.5*a14[i]: bprs.append(dict(top=t, bot=b, born=i))
                fv[kind].append((i, top, bot)); del fv[kind][:-5]
        bprs[:] = [b for b in bprs if i - b["born"] < 500 and c[i] <= b["top"]]
    return sigs, a14

def trade(o, h, l, c, i, entry, stop, tgtR, hold, cost):
    risk = max(stop-entry, 1e-9); tgt = entry - tgtR*risk
    for j in range(i+1, min(i+1+hold, len(c))):
        if h[j] >= stop: return -1 - cost/risk*entry
        if l[j] <= tgt: return tgtR - cost/risk*entry
    j = min(i+hold, len(c)-1); return (entry-c[j])/risk - cost/risk*entry

def stats_for(sig_list, df, a14, tf):
    o, h, l, c = (df[x].values for x in "ohlc"); out = {}
    for R in (1, 2, 3):
        rs = []
        for s in sig_list:
            entry = c[s["i"]]; stop = max(s["stop"], entry + 0.3*a14[s["i"]])
            rs.append(trade(o, h, l, c, s["i"], entry, stop, R, HOLD[tf], FEE_RT))
        out[R] = np.array(rs)
    return out

def row(name, sl, df, a14, tf):
    if not sl: print(f" {name:<26} n=0"); return
    st = stats_for(sl, df, a14, tf)
    print(f" {name:<26} n={len(sl):<4} win2R {np.mean(st[2] > 0):5.0%}  avgR: 1R {st[1].mean():+.2f}  2R {st[2].mean():+.2f}  3R {st[3].mean():+.2f}")

if __name__ == "__main__":
    tfs = sys.argv[1:] or ["1H", "4H"]
    df4 = load("4H")
    for tf in tfs:
        df = df4 if tf == "4H" else load(tf)
        t0, t1 = pd.to_datetime(df.ts.iloc[0], unit="ms").date(), pd.to_datetime(df.ts.iloc[-1], unit="ms").date()
        print(f"\n===== BTC {tf}  {len(df)} bars  {t0} -> {t1} =====")
        sigs, a14 = scan(df, tf, df4)
        A = sigs; B = [s for s in A if s["prem"]]; OB = [s for s in B if s["ob"]]; BP = [s for s in B if s["bpr"]]
        C = [s for s in B if s["ob"] or s["bpr"]]; D = [s for s in B if s["ob"] and s["bpr"]]
        row("A  LB sweep (any)", A, df, a14, tf); row("B  A + 4H premium", B, df, a14, tf)
        row("C1 B + bearish OB", OB, df, a14, tf); row("C2 B + BPR", BP, df, a14, tf)
        row("C  B + (OB or BPR)", C, df, a14, tf); row("D  B + OB + BPR", D, df, a14, tf)
        h, l, c, o = (df[x].values for x in "hlco"); base = []
        for i in range(30, len(c)-1, 10):
            stop = max(h[i-2:i+1].max(), c[i]+0.3*a14[i]) + 0.1*a14[i]; base.append(dict(i=i, stop=stop))
        row("baseline: random shorts", base, df, a14, tf)
        pd.DataFrame(C).to_csv(f"setups_{tf}.csv", index=False)
        if C:
            yr = pd.to_datetime([s["ts"] for s in C], unit="ms").year; st = stats_for(C, df, a14, tf)[2]
            print(" setup C by year (avgR @2R):", ", ".join(f"{y}: {st[yr == y].mean():+.2f} (n={int((yr == y).sum())})" for y in sorted(set(yr))))
