import os,re,json,collections
ROOT='/tmp/brainclass'
EXT={'.py','.md','.ipynb'}
FAM={
 'multiplicity':[r'bonferroni',r'\bholm\b',r'benjamini',r'\bfdr\b',r'false discovery',r'multiple (?:testing|comparison|hypothes)',r'deflated sharpe',r'\bdsr\b',r'probability of backtest overfit',r'\bpbo\b',r'family[- ]wise',r'\bfwer\b',r'p[- ]hack',r'data snoop',r'white.s reality check',r'\bspa test\b',r'harvey.?liu',r'effective number of trials',r'\bnum_?trials\b'],
 'oos_holdout':[r'out[- ]of[- ]sample',r'\boos\b',r'\bholdout\b',r'hold[- ]out',r'walk[- ]forward',r'train[_ ]test[_ ]split',r'cross[- ]valid',r'purged',r'embargo',r'in[- ]sample'],
 'gen_scale':[r'itertools\.product',r'for .* in .*combinations',r'generate_alphas?\(',r'batch',r'\bpermutations\b',r'random\.choice',r'mutat',r'crossover',r'population'],
 'selection_bar':[r'sharpe\s*[><=]+\s*[\d.]+',r'fitness\s*[><=]+\s*[\d.]+',r'\b1\.25\b',r'\b0\.7\b.*fitness',r'turnover\s*[><=]',r'is_sharpe',r'checks.*PASS',r'submit.*alpha'],
}
COMP={k:[re.compile(p,re.I) for p in v] for k,v in FAM.items()}
out={}
for repo in sorted(os.listdir(ROOT)):
    d=os.path.join(ROOT,repo)
    if not os.path.isdir(d): continue
    hits=collections.defaultdict(collections.Counter); nf=0; nb=0
    for dp,dns,fns in os.walk(d):
        dns[:]=[x for x in dns if x not in ('.git','node_modules','.venv','venv')]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() not in EXT: continue
            p=os.path.join(dp,fn)
            try: t=open(p,encoding='utf-8',errors='ignore').read()
            except Exception: continue
            if len(t)>2_000_000: continue
            nf+=1; nb+=len(t)
            for fam,pats in COMP.items():
                for pat in pats:
                    m=pat.findall(t)
                    if m: hits[fam][pat.pattern]+=len(m)
    out[repo]={'files':nf,'bytes':nb,'hits':{k:dict(v) for k,v in hits.items()}}
json.dump(out,open('/tmp/brainclass/scan.json','w'),indent=1)
for r,v in out.items():
    m=sum(v['hits'].get('multiplicity',{}).values()); o=sum(v['hits'].get('oos_holdout',{}).values())
    g=sum(v['hits'].get('gen_scale',{}).values()); s=sum(v['hits'].get('selection_bar',{}).values())
    print(f"{r[:44]:44} files={v['files']:5} mult={m:4} oos={o:5} gen={g:5} bar={s:5}")
