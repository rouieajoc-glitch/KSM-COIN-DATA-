import sys, numpy as np, pandas as pd
px = pd.read_csv(sys.argv[1], index_col=0).iloc[:,0].astype(float).values
r = np.diff(np.log(px))
print(f"{len(px)} bars | avg |hourly move| {np.abs(r).mean():.3%} (round-trip fee ~0.2%)")
print(f"lag-1 autocorr of hourly returns: {np.corrcoef(r[:-1], r[1:])[0,1]:+.3f}")
print("variance ratio (below 1 = mean-reverting, above 1 = trending):")
for q in [2,4,8,24,72,168]:
    rq = np.log(px[q:]/px[:-q])
    print(f"  {q:>3}h: {rq.var()/(q*r.var()):.2f}")
w = 336
inside = np.mean([(px[i:i+w].max()/px[i]-1 < .10 and px[i]/px[i:i+w].min()-1 < .10) for i in range(0, len(px)-w, 24)])
print(f"share of 2-week windows that stayed within ±10%: {inside:.0%}")
