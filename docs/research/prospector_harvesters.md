## APPENDIX — the resumable MQL5 slippage harvester (prospector 2026-08-27(c))

Kept here because this seat is frozen to `docs/research/*` + `data/*` and may not write `scripts/`.
Landing it as a wired collector is named in **R0679**. Run: `MQL5_DELAY=3 python harvest.py <pages> <out.jsonl>`.

```python
"""Resumable, polite MQL5 slippage-panel harvester.

Writes ONE JSON line per signal the instant it is parsed, so a kill, a ban or a
timeout costs the current signal and nothing else. Re-running skips every
signal_id already in the file. Single-threaded with a delay: the 4-thread
version got this IP blocked at ~175 signals on 2026-08-27.
"""
import json,os,re,sys,time,urllib.parse
import urllib.request as U
H={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36',
   'Accept-Language':'en-US,en;q=0.9'}
XH=dict(H,**{'X-Requested-With':'XMLHttpRequest'})
DELAY=float(os.environ.get('MQL5_DELAY','2.5'))
def get(url,hdr=H,tries=3):
    for k in range(tries):
        try:
            with U.urlopen(U.Request(url,headers=hdr),timeout=30) as f:
                time.sleep(DELAY); return f.read().decode('utf-8','replace')
        except Exception as e:
            last=e; time.sleep(5*(k+1)*DELAY)
    print(f'FAIL {url}: {last}',file=sys.stderr); return ''
ROW=re.compile(r"LoadBrokerSlippage\(this,'((?:[^'\\]|\\.)*)',\d+\)\">.*?<span>([\d.]+)\s*<em>&times;\s*(\d+)</em>",re.S)
SYM=re.compile(r'symbol-col__wrapper">([^<]+)</div>.*?<span>([\d.]+)\s*<em>&times;\s*(\d+)</em>',re.S)
PROV=re.compile(r'quotes from &quot;([^&]+)&quot;')
def signal(sid):
    h=get(f'https://www.mql5.com/en/signals/{sid}')
    if not h: return None
    brokers=[{'server':m[0],'pips':float(m[1]),'n':int(m[2])} for m in ROW.findall(h)]
    p=PROV.search(h)
    out={'signal_id':sid,'provider_server':p.group(1) if p else None,
         'n_broker_rows':len(brokers),'brokers':brokers,'symbols':{}}
    for b in brokers:
        if 'fusion' not in b['server'].lower(): continue
        q=urllib.parse.urlencode({'id':sid,'to':b['server']})
        t=get('https://www.mql5.com/signals/charts/slippage?'+q,XH)
        out['symbols'][b['server']]=[{'symbol':s[0].strip(),'pips':float(s[1]),'n':int(s[2])}
                                     for s in SYM.findall(t)]
    return out
def main(pages,path):
    done=set()
    if os.path.exists(path):
        for ln in open(path):
            try: done.add(json.loads(ln)['signal_id'])
            except Exception: pass
    print(f'resuming: {len(done)} already on disk',file=sys.stderr)
    ids=[]
    for p in range(1,pages+1):
        h=get(f'https://www.mql5.com/en/signals/mt5/list/page{p}')
        new=[int(x) for x in dict.fromkeys(re.findall(r'/en/signals/(\d{5,9})\b',h))]
        if not new: print(f'page{p} empty -- stopping enumeration',file=sys.stderr); break
        ids+=new
    ids=[i for i in dict.fromkeys(ids) if i not in done]
    print(f'{len(ids)} to fetch',file=sys.stderr)
    with open(path,'a') as f:
        for i,sid in enumerate(ids):
            r=signal(sid)
            if r: f.write(json.dumps(r)+'\n'); f.flush()
            if i%20==0: print(f'{i}/{len(ids)}',file=sys.stderr)
    print('DONE')
if __name__=='__main__': main(int(sys.argv[1]),sys.argv[2])
```
