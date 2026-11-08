import sys, numpy as np, pandas as pd
from smc_bt import load, atr, pd_state, MIN, FEE_RT
SYM = next((x[4:] for x in sys.argv[1:] if x.startswith("sym=")), "BTC")
if SYM != "BTC":
    def load(tf):
        return pd.read_csv(f"{SYM.lower()}_{tf}.csv")[["ts","o","h","l","c"]].reset_index(drop=True)
HOLD = {"15m": 192, "1H": 96, "4H": 60}; WAIT = {"15m": 48, "1H": 24, "4H": 12}; MINRR = [1.0]

def scan2(df, tf, df4, conf=True):
    o, h, l, c = (df[x].values for x in "ohlc"); ts = df.ts.values; n = len(c)
    a14 = atr(h, l, c, 14); a200 = atr(h, l, c, 200)
    RH4, RL4 = pd_state(df4); close4 = df4.ts.values + 240*60*1000
    kmap = np.arange(n) if tf == "4H" else np.searchsorted(close4, ts + MIN[tf]*60*1000, side="right") - 1
    rh = np.full(n, np.nan); rl = np.full(n, np.nan)
    if tf == "4H": rh, rl = RH4.copy(), RL4.copy()
    else:
        S = np.searchsorted(ts, close4[np.maximum(kmap, 0)]-1, side="right"); rm, rn, last = -np.inf, np.inf, -1
        for i in range(n):
            k = kmap[i]
            if k < 0 or np.isnan(RH4[k]): continue
            if S[i] != last: rm, rn, last = -np.inf, np.inf, S[i]
            if S[i] <= i: rm = max(rm, h[i]); rn = min(rn, l[i])
            rh[i] = max(RH4[k], rm); rl[i] = min(RL4[k], rn)
    eq = (rh + rl)/2
    class Pv: cur = np.nan; bar = 0; crossed = False; scr = False
    inH, inL, swH, swL = Pv(), Pv(), Pv(), Pv()
    leg = {5: 0, 50: 0}; pH = np.where((h-l) >= 2*a200, l, h); pL = np.where((h-l) >= 2*a200, h, l)
    obs = []; fv = {"bull": [], "bear": []}; bprs = []; lbs = []; sigs = []
    chb = np.zeros(n, bool); chl = np.zeros(n, bool); trend = 0; pcur = {"H": np.nan, "L": np.nan}
    def upd(i, size, hi, lo):
        if i < size: return
        newH = h[i-size] > h[i-size+1:i+1].max(); newL = l[i-size] < l[i-size+1:i+1].min()
        new = 0 if newH else (1 if newL else leg[size])
        if new != leg[size]:
            if new == 1: lo.cur, lo.bar, lo.crossed, lo.scr = l[i-size], i-size, False, False
            else:        hi.cur, hi.bar, hi.crossed, hi.scr = h[i-size], i-size, False, False
            leg[size] = new
    for i in range(15, n):
        keep = []
        for lb in lbs:
            age = i - lb["born"]; d = lb["d"]
            if age <= 5 and ((d == -1 and c[i] > lb["px"]) or (d == 1 and c[i] < lb["px"])): continue
            if (d == -1 and h[i] > lb["px"] and c[i] <= lb["px"]) or (d == 1 and l[i] < lb["px"] and c[i] >= lb["px"]):
                lvl = lb["px"]; tol = 0.25*a14[i]
                in_ob = any(z["bias"] == d and z["rank"] < 5 and min(z["hi"], z["lo"])-tol <= lvl <= max(z["hi"], z["lo"])+tol for z in obs)
                in_bpr = any(b["bot"]-tol <= lvl <= b["top"]+tol and (b["up"] if d == -1 else b["dn"]) for b in bprs)
                pdok = (not np.isnan(eq[i])) and ((lvl > eq[i]) if d == -1 else (lvl < eq[i]))
                sigs.append(dict(d=d, i=i, born=lb["born"], ts=ts[i], pd=pdok, ob=in_ob, bpr=in_bpr)); continue
            if age >= 7: continue
            keep.append(lb)
        lbs = keep
        b0, b1 = abs(c[i]-o[i]), abs(c[i-1]-o[i-1])
        ok0 = b0/c[i]*100 >= 0.15 and b0 >= 0.3*(h[i]-l[i]); ok1 = b1/c[i-1]*100 >= 0.15 and b1 >= 0.3*(h[i-1]-l[i-1])
        if abs(c[i-1]-o[i]) <= 0.05*a14[i] and (ok0 or ok1):
            if c[i-1] > o[i-1] and c[i] < o[i]: lbs.append(dict(px=(c[i-1]+o[i])/2, born=i, d=-1))
            if c[i-1] < o[i-1] and c[i] > o[i]: lbs.append(dict(px=(c[i-1]+o[i])/2, born=i, d=1))
        for z in obs:
            if i > z["cb"] and ((z["bias"] == -1 and h[i] > max(z["hi"], z["lo"])) or (z["bias"] == 1 and l[i] < min(z["hi"], z["lo"]))): z["dead"] = True
        upd(i, 5, inH, inL); upd(i, 50, swH, swL)
        up_w = h[i]-max(c[i], o[i]); lo_w = min(c[i], o[i]-l[i]); bullbar, bearbar = up_w > lo_w, up_w < lo_w
        xH = c[i] > inH.cur and c[i-1] <= pcur["H"]; xL = c[i] < inL.cur and c[i-1] >= pcur["L"]
        if xH and not inH.scr and inH.cur != swH.cur and (bullbar or not conf):
            if trend == -1: chl[i] = True
            trend = 1; inH.scr = True
        if xL and not inL.scr and inL.cur != swL.cur and (bearbar or not conf):
            if trend == 1: chb[i] = True
            trend = -1; inL.scr = True
        for bias, p, x in ((1, inH, xH), (-1, inL, xL)):
            if x and not p.crossed and p.cur != (swH.cur if bias == 1 else swL.cur) and (bullbar if bias == 1 else bearbar):
                p.crossed = True; base = p.bar
                if base < i:
                    idx = base + int(np.argmax(pH[base:i]) if bias == -1 else np.argmin(pL[base:i]))
                    if not any(z["t"] == idx and z["bias"] == bias for z in obs):
                        obs.insert(0, dict(hi=pH[idx], lo=pL[idx], bias=bias, t=idx, cb=i, dead=False))
        pcur["H"], pcur["L"] = inH.cur, inL.cur
        del obs[100:]; obs[:] = [z for z in obs if not z.get("dead")]
        for r, z in enumerate(obs): z["rank"] = r
        if i > 25:
            bull = l[i] > h[i-2] and (l[i]-h[i-2]) >= 0.1*a14[i]; bear = h[i] < l[i-2] and (l[i-2]-h[i]) >= 0.1*a14[i]
            for kind, ok, top, bot, opp in (("bull", bull, l[i], h[i-2], "bear"), ("bear", bear, l[i-2], h[i], "bull")):
                if not ok: continue
                for (gi, gt, gb) in fv[opp][-1:]:
                    if i - gi <= 100:
                        t, b = min(top, gt), max(bot, gb)
                        if t > b and (t-b) >= 0.5*a14[i]: bprs.append(dict(top=t, bot=b, born=i, up=True, dn=True))
                fv[kind].append((i, top, bot)); del fv[kind][:-5]
        for b in bprs:
            if c[i] > b["top"]: b["up"] = False
            if c[i] < b["bot"]: b["dn"] = False
        bprs[:] = [b for b in bprs if i - b["born"] < 500 and (b["up"] or b["dn"])]
    return sigs, a14, eq, chb, chl

def sim(h, l, c, j, entry, stop, tgt, hold, d):
    risk = abs(entry-stop); cost = FEE_RT*entry/risk
    for t in range(j+1, min(j+1+hold, len(c))):
        if (d == -1 and h[t] >= stop) or (d == 1 and l[t] <= stop): return -1 - cost
        if (d == -1 and l[t] <= tgt) or (d == 1 and h[t] >= tgt): return abs(entry-tgt)/risk - cost
    t = min(j+hold, len(c)-1); return d*(c[t]-entry)/risk - cost

def process(sl, d, df, a14, eq, ch, tf):
    h, l, c = (df[x].values for x in "hlc"); W = WAIT[tf]; out = []; nch = 0
    for s in sl:
        i = s["i"]; js = np.nonzero(ch[i+1:i+1+W])[0]
        if len(js) == 0 or np.isnan(eq[i+1+js[0]]): continue
        j = i+1+js[0]; entry = c[j]; nch += 1
        stop = (h[s["born"]:j+1].max() + 0.1*a14[j]) if d == -1 else (l[s["born"]:j+1].min() - 0.1*a14[j])
        stop = max(stop, entry + 0.3*a14[j]) if d == -1 else min(stop, entry - 0.3*a14[j])
        risk = abs(entry-stop); rr = ((entry-eq[j]) if d == -1 else (eq[j]-entry))/risk
        if rr < MINRR[0]: continue
        out.append((s["ts"], rr, sim(h, l, c, j, entry, stop, eq[j], HOLD[tf], d), sim(h, l, c, j, entry, stop, entry + d*2*risk, HOLD[tf], d)))
    return out, nch

def show(name, sl, d, df, a14, eq, ch, tf):
    r, nch = process(sl, d, df, a14, eq, ch, tf)
    if not r: print(f" {name:<24} sig={len(sl):<5} choch={nch:<4} trades=0"); return r
    a = np.array([[x[1], x[2], x[3]] for x in r])
    print(f" {name:<24} sig={len(sl):<5} choch={nch:<4} trd={len(r):<4} RR {a[:,0].mean():.1f}  win(EQ) {np.mean(a[:,1] > 0):4.0%}  avgR: EQ {a[:,1].mean():+.2f}  2R {a[:,2].mean():+.2f}")
    return r

if __name__ == "__main__":
    conf = "loose" not in sys.argv; tfs = [a for a in sys.argv[1:] if a in ("15m", "1H", "4H")] or ["1H", "4H"]; df4 = load("4H")
    for a in sys.argv[1:]:
        if a.startswith("rr="): MINRR[0] = float(a[3:])
    for tf in tfs:
        df = df4 if tf == "4H" else load(tf); n = len(df)
        print(f"\n===== {SYM} {tf}  {n} bars  min RR {MINRR[0]}  structure filter {'ON' if conf else 'OFF (loose)'} =====")
        sigs, a14, eq, chb, chl = scan2(df, tf, df4, conf); c = df.c.values
        for d, nm, ch in ((-1, "SHORT (bear LB, premium)", chb), (1, "LONG (bull LB, discount)", chl)):
            S = [s for s in sigs if s["d"] == d]; print(f"-- {nm}: CHoCH entry, target = 4H equilibrium")
            show("A  LB sweep", S, d, df, a14, eq, ch, tf)
            B = [s for s in S if s["pd"]]; show("B  + P/D zone", B, d, df, a14, eq, ch, tf)
            C = [s for s in B if s["ob"] or s["bpr"]]; rc = show("C  B + OB/BPR", C, d, df, a14, eq, ch, tf)
            show("D  B + OB + BPR", [s for s in B if s["ob"] and s["bpr"]], d, df, a14, eq, ch, tf)
            base = [dict(d=d, i=b, born=b-3, ts=df.ts.values[b]) for b in range(30, n-1, 10) if not np.isnan(eq[b]) and ((c[b] > eq[b]) if d == -1 else (c[b] < eq[b]))]
            show("baseline: random in P/D", base, d, df, a14, eq, ch, tf)
            if rc:
                yr = pd.to_datetime([x[0] for x in rc], unit="ms").year; v = np.array([x[2] for x in rc])
                print("   C by year (avgR EQ):", ", ".join(f"{y}: {v[yr == y].mean():+.2f}({int((yr == y).sum())})" for y in sorted(set(yr))))
