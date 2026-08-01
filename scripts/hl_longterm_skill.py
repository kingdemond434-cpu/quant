"""LONG-TERM GENUINE SKILL TEST -- the strongest remaining version of the hypothesis.

Prior tests were rightly criticised: holding window was ONE WEEK (noise vs a long-horizon trader's
signal), no track-record filter, and ranking on RAW PnL (rewards one lucky levered bet).

This fixes all three:
  - TRACK RECORD: require a long equity curve (multi-period history), not recent arrivals.
  - RISK-ADJUSTED selection: rank by SHARPE + consistency (% positive periods) + drawdown, not PnL.
  - LONG HORIZON + NATURAL GAP: split each trader's own curve -- formation = first 60%,
    holding = last 40%. No overlap, no lookahead, long measurement on both sides.

Uses pnlHistory (cumulative PnL) normalised by contemporaneous accountValue, so deposits/withdrawals
do not masquerade as returns. Tests whether risk-adjusted long-run skill PERSISTS into the later
period -- the precondition for 'find genuinely good traders and follow them'."""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

INFO="https://api.hyperliquid.xyz/info"; LB="https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
N_TRY=420; MIN_PTS=60          # need a real curve, not a few points

def _get(u,t=180):
    return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"q/1.0"}),timeout=t).read()
def _post(p,t=25):
    r=urllib.request.Request(INFO,data=json.dumps(p).encode(),
        headers={"Content-Type":"application/json","User-Agent":"q/1.0"})
    with urllib.request.urlopen(r,timeout=t) as x: return json.loads(x.read().decode())

rows=json.loads(_get(LB)); rows=rows.get("leaderboardRows",rows) if isinstance(rows,dict) else rows
cand=[]
for r in rows:
    try:
        av=float(r.get("accountValue",0) or 0); a=r.get("ethAddress")
        wp={w:v for w,v in r.get("windowPerformances",[])}
        vlm=float(wp.get("month",{}).get("vlm",0) or 0)
        if a and av>=50_000 and vlm>0: cand.append((av,a))
    except (TypeError,ValueError): continue
cand.sort(reverse=True)
sel=cand[:N_TRY]
print(f"probing {len(sel)} accounts for long equity curves",flush=True)

recs=[]
for i,(av0,a) in enumerate(sel):
    try: pf=_post({"type":"portfolio","user":a})
    except Exception: continue
    if not isinstance(pf,list): continue
    win=dict(pf)
    d=win.get("allTime") or {}
    pnl=d.get("pnlHistory") or []; avh=d.get("accountValueHistory") or []
    if len(pnl)<MIN_PTS or len(avh)<MIN_PTS: continue
    try:
        t=np.array([int(x[0]) for x in pnl]); cum=np.array([float(x[1]) for x in pnl])
        avt=np.array([float(x[1]) for x in avh[:len(cum)]])
    except (TypeError,ValueError,IndexError): continue
    if len(avt)!=len(cum): continue
    base=np.where(avt>1000, avt, np.nan)
    ret=np.zeros(len(cum)); ret[1:]=np.diff(cum)/np.where(np.isnan(base[1:]),np.inf,base[1:])
    ret=np.nan_to_num(ret,nan=0.0,posinf=0.0,neginf=0.0)
    ret=np.clip(ret,-0.5,0.5)                      # kill absurd single-step artifacts
    span=(t[-1]-t[0])/86400_000
    if span<200: continue                          # need a LONG record (>~7 months)
    k=int(len(ret)*0.6)
    f,h=ret[1:k],ret[k:]
    if len(f)<25 or len(h)<15: continue
    fs=float(f.mean()/f.std()*np.sqrt(365)) if f.std()>0 else 0.0     # formation Sharpe
    cons=float((f>0).mean())                                          # consistency
    eq=np.cumprod(1+f); dd=float((eq/np.maximum.accumulate(eq)-1).min())
    recs.append({"a":a,"span":span,"f_sharpe":fs,"f_cons":cons,"f_dd":dd,
                 "f_ret":float(np.prod(1+f)-1),"h_ret":float(np.prod(1+h)-1),
                 "h_sharpe":float(h.mean()/h.std()*np.sqrt(365)) if h.std()>0 else 0.0})
    if (i+1)%100==0: print(f"  {i+1}/{len(sel)} usable={len(recs)}",flush=True)

print(f"\ntraders with LONG usable curves: {len(recs)}")
if len(recs)<40: raise SystemExit("insufficient long-history cohort")
sp=np.array([r["span"] for r in recs])
print(f"track-record span: median {np.median(sp):.0f}d  max {sp.max():.0f}d")

def spear(a,b):
    ra=np.argsort(np.argsort(a)).astype(float); rb=np.argsort(np.argsort(b)).astype(float)
    if ra.std()==0 or rb.std()==0: return 0.0,0.0
    rho=float(np.corrcoef(ra,rb)[0,1]); n=len(a)
    return rho, float(rho*np.sqrt((n-2)/max(1e-12,1-rho**2))) if n>2 and abs(rho)<1 else 0.0

hr=np.array([r["h_ret"] for r in recs]); hs=np.array([r["h_sharpe"] for r in recs])
out={}
for nm,key in (("formation SHARPE","f_sharpe"),("formation CONSISTENCY","f_cons"),
               ("formation RETURN","f_ret"),("formation MAXDD (higher=safer)","f_dd")):
    x=np.array([r[key] for r in recs])
    r1,t1=spear(x,hr); r2,t2=spear(x,hs)
    o=np.argsort(x); k=max(3,len(x)//4)
    top,bot=hr[o[-k:]],hr[o[:k]]
    print(f"\n[{nm}]  -> holding RETURN rho {r1:+.3f} (t {t1:+.2f}) | -> holding SHARPE rho {r2:+.3f} (t {t2:+.2f})")
    print(f"   top-quartile holding ret {top.mean()*100:+.1f}% (median {np.median(top)*100:+.1f}%) vs "
          f"bottom {bot.mean()*100:+.1f}% (median {np.median(bot)*100:+.1f}%)")
    out[nm]={"rho_ret":round(r1,4),"t_ret":round(t1,2),"rho_sharpe":round(r2,4),"t_sharpe":round(t2,2),
             "top_q_mean":round(float(top.mean()),4),"bot_q_mean":round(float(bot.mean()),4)}
print(f"\ncohort holding-period mean {hr.mean()*100:+.1f}% median {np.median(hr)*100:+.1f}% "
      f"| positive {int((hr>0).sum())}/{len(hr)}")
Path("data/hl_longterm_skill.json").write_text(json.dumps(
    {"updated":datetime.now(tz=UTC).isoformat(),"n":len(recs),"median_span_d":float(np.median(sp)),
     "tests":out},indent=1),"utf-8")
