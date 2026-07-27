"""OUT-OF-SAMPLE VALIDATION of the ELITE filter.
In-sample (n=1062, cohort = top-1800 accounts by value): filter
  profitable AND sharpe>1 AND consistency>55% AND maxDD>-25%
gave n=24, fwd mean +16.2%, median +3.7%, 62% positive vs 37% base rate.
RISK: n=24, ~13 filter combos tried, thresholds hand-picked -> possible specification search.
THIS TEST: same filter, FROZEN, applied to a DISJOINT cohort (accounts ranked 1800-5200 by value,
never probed). No re-tuning. If the lift replicates OOS it is real; if it collapses to base rate it
was overfitting."""
from __future__ import annotations
import json, urllib.request
from datetime import UTC, datetime
from pathlib import Path
import numpy as np

INFO="https://api.hyperliquid.xyz/info"; LB="https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
LO,HI=1800,5200; MIN_PTS=60; MIN_SPAN=200
CACHE=Path("data/hl_oos_rows.json")
# FROZEN filter -- identical to in-sample, no re-tuning
F_SH,F_CONS,F_DD=1.0,0.55,-0.25

def _get(u,t=180):
    return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"q/1.0"}),timeout=t).read()
def _post(p,t=20):
    r=urllib.request.Request(INFO,data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json","User-Agent":"q/1.0"})
    with urllib.request.urlopen(r,timeout=t) as x: return json.loads(x.read().decode())

recs=json.loads(CACHE.read_text()) if CACHE.exists() else []
if not recs:
    rows=json.loads(_get(LB)); rows=rows.get("leaderboardRows",rows) if isinstance(rows,dict) else rows
    cand=[]
    for r in rows:
        try:
            av=float(r.get("accountValue",0) or 0); a=r.get("ethAddress")
            wp={w:v for w,v in r.get("windowPerformances",[])}
            if a and av>=10_000 and float(wp.get("month",{}).get("vlm",0) or 0)>0: cand.append((av,a))
        except (TypeError,ValueError): continue
    cand.sort(reverse=True)
    sel=cand[LO:HI]
    print(f"OOS cohort: accounts ranked {LO}-{HI} by value ({len(sel)}) -- DISJOINT from in-sample",flush=True)
    for i,(av0,a) in enumerate(sel):
        try: pf=_post({"type":"portfolio","user":a})
        except Exception: continue
        if not isinstance(pf,list): continue
        d=dict(pf).get("allTime") or {}
        pnl=d.get("pnlHistory") or []; avh=d.get("accountValueHistory") or []
        if len(pnl)<MIN_PTS or len(avh)<MIN_PTS: continue
        try:
            t=np.array([int(x[0]) for x in pnl]); cum=np.array([float(x[1]) for x in pnl])
            avt=np.array([float(x[1]) for x in avh[:len(cum)]])
        except (TypeError,ValueError,IndexError): continue
        if len(avt)!=len(cum) or (t[-1]-t[0])/86400_000<MIN_SPAN: continue
        base=np.where(avt>1000,avt,np.nan)
        ret=np.zeros(len(cum)); ret[1:]=np.diff(cum)/np.where(np.isnan(base[1:]),np.inf,base[1:])
        ret=np.clip(np.nan_to_num(ret,nan=0.0,posinf=0.0,neginf=0.0),-0.5,0.5)
        k=int(len(ret)*0.6); f,h=ret[1:k],ret[k:]
        if len(f)<25 or len(h)<15: continue
        eq=np.cumprod(1+f)
        recs.append({"f_ret":float(np.prod(1+f)-1),
                     "f_sharpe":float(f.mean()/f.std()*np.sqrt(365)) if f.std()>0 else 0.0,
                     "f_cons":float((f>0).mean()),
                     "f_dd":float((eq/np.maximum.accumulate(eq)-1).min()),
                     "h_ret":float(np.prod(1+h)-1)})
        if (i+1)%200==0:
            print(f"  {i+1}/{len(sel)} usable={len(recs)}",flush=True); CACHE.write_text(json.dumps(recs))
    CACHE.write_text(json.dumps(recs))

fr=np.array([r["f_ret"] for r in recs]); hr=np.array([r["h_ret"] for r in recs])
fs=np.array([r["f_sharpe"] for r in recs]); fc=np.array([r["f_cons"] for r in recs])
fd=np.array([r["f_dd"] for r in recs])
n=len(recs); base=(hr>0).mean()
print(f"\n=== OOS COHORT n={n} | base rate positive {base*100:.0f}% | "
      f"mean {hr.mean()*100:+.1f}% median {np.median(hr)*100:+.1f}% ===")
m=(fr>0)&(fs>F_SH)&(fc>F_CONS)&(fd>F_DD)
k=int(m.sum())
print(f"\nFROZEN ELITE FILTER (prof + Sh>{F_SH} + cons>{F_CONS} + dd>{F_DD}):")
if k>=5:
    s=hr[m]; pos=(s>0).sum()
    sd=np.sqrt(k*base*(1-base)); z=(pos-k*base)/sd if sd>0 else 0
    print(f"  n={k} | fwd mean {s.mean()*100:+.1f}% | median {np.median(s)*100:+.1f}% | "
          f"positive {pos}/{k} = {pos/k*100:.0f}%")
    print(f"  vs base rate {base*100:.0f}%  -> binomial z {z:+.2f}")
    print(f"  VERDICT: {'REPLICATES (lift holds OOS)' if z>=2.0 and s.mean()>hr.mean() else 'FAILS TO REPLICATE (was specification search)'}")
else:
    print(f"  n={k} -- too few to judge")
Path("data/hl_oos_elite.json").write_text(json.dumps(
    {"updated":datetime.now(tz=UTC).isoformat(),"n":n,"base_rate":round(float(base),4),
     "filter_n":k},indent=1),"utf-8")
