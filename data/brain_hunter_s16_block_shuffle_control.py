"""CONTROL: does QuantGPT/adversarial_validator.test_temporal_shuffle actually break the
temporal structure it claims to break? Their defaults: block_size=20, holding_period=5,
pass bar = real|IC| / shuffled|IC| > 1.5.  Matrix form, same logic."""
import numpy as np
rng=np.random.RandomState(0)
NS,ND,HP=60,500,5

def make(strength):
    daily=rng.normal(0,0.01,(ND,NS)); fac=rng.normal(0,1,(ND,NS))
    for t in range(ND-HP):
        daily[t+1:t+1+HP,:]+=strength*0.01*fac[t,:]/HP
    return fac,daily

def fwd(daily):                       # sum of next HP daily returns, aligned to day t
    c=np.cumsum(np.vstack([np.zeros((1,NS)),daily]),axis=0)
    out=np.full((ND,NS),np.nan)
    out[:ND-HP,:]=c[1+HP:ND+1,:]-c[1:ND-HP+1,:]
    return out

def rank(a):
    o=a.argsort(axis=1); r=np.empty_like(o,dtype=float)
    np.put_along_axis(r,o,np.arange(NS,dtype=float),axis=1); return r

def ic(fac,f):
    m=~np.isnan(f).any(axis=1)
    x,y=rank(fac[m]),rank(f[m])
    x=x-x.mean(1,keepdims=True); y=y-y.mean(1,keepdims=True)
    per=(x*y).sum(1)/np.sqrt((x*x).sum(1)*(y*y).sum(1))
    return abs(float(np.nanmean(per)))

def their_shuffle(fac,daily,bs,n=20):
    r=np.random.RandomState(42); nb=ND//bs; out=[]
    for _ in range(n):
        order=np.arange(nb); r.shuffle(order)
        idx=np.concatenate([np.arange(b*bs,(b+1)*bs) for b in order])
        # block-order shuffle: rows move together, fwd returns RECOMPUTED after remap (their code)
        d2=daily[idx]; f2=fac[idx]
        out.append(ic(f2,fwd(d2)))
    return float(np.mean(out))

for s in (0.0,3.0):
    fac,daily=make(s); real=ic(fac,fwd(daily))
    print(f"\n=== injected strength {s} | real |IC| = {real:.4f} ===")
    for bs in (20,10,5,2,1):
        sh=their_shuffle(fac,daily,bs)
        ratio=real/sh if sh>1e-6 else 999.0
        print(f"  block_size={bs:3}  shuffled|IC|={sh:.4f}  ratio={ratio:6.2f}  "
              f"their bar(ratio>1.5) => {'PASS' if ratio>1.5 else 'FAIL'}")
