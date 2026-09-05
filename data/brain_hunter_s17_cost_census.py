import json, os, re
ROOT='<CLONE_ROOT>'
EXT={'.py','.md','.ipynb'}
# vocabularies
COST=[r'transaction cost',r'\btcost\b',r'\btc\b(?![a-z])',r'\bslippage\b',r'\bcommission\b',r'\bspread\b',
      r'\bfee[s]?\b',r'\bbid[- _]?ask\b',r'\bimpact\b',r'\bhalf[- _]?spread\b',r'\bbps\b',r'\bbasis point',
      r'\bturnover\b',r'\bcost[- _]?model\b',r'net of cost',r'after cost']
# turnover is separate: BRAIN's own fitness penalises churn, so it is NOT a cost model
TURNOVER=[r'\bturnover\b']
CORE=[r'transaction cost',r'\bslippage\b',r'\bcommission\b',r'\bfee[s]?\b',r'\bbid[- _]?ask\b',
      r'\bhalf[- _]?spread\b',r'net of cost',r'after cost',r'\bcost[- _]?model\b']
POS=[r'\bsharpe\b']
def scan(pats, txt):
    n=0
    for p in pats: n+=len(re.findall(p, txt, re.I))
    return n
out={}
for repo in sorted(os.listdir(ROOT)):
    d=os.path.join(ROOT,repo)
    if not os.path.isdir(d) or repo.startswith('.'): continue
    files=0; core=0; turn=0; pos=0; allc=0; hits={}
    for dp,dns,fns in os.walk(d):
        if '.git' in dp: continue
        for f in fns:
            if os.path.splitext(f)[1] not in EXT: continue
            files+=1
            try: t=open(os.path.join(dp,f),encoding='utf-8',errors='ignore').read()
            except Exception: continue
            c=scan(CORE,t)
            if c:
                hits[os.path.relpath(os.path.join(dp,f),d)]=c
            core+=c; turn+=scan(TURNOVER,t); pos+=scan(POS,t); allc+=scan(COST,t)
    out[repo]=dict(files=files,core_cost_hits=core,turnover_hits=turn,sharpe_hits=pos,
                   broad_cost_hits=allc,files_with_core=dict(sorted(hits.items(),key=lambda kv:-kv[1])[:6]))
json.dump(out,open('<CLONE_ROOT>/cost_census.json','w'),indent=1)
for k,v in out.items():
    print(f"{k[:42]:44s} files={v['files']:4d} core={v['core_cost_hits']:4d} turnover={v['turnover_hits']:4d} sharpe={v['sharpe_hits']:5d}")
