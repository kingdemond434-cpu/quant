"""BRAIN HUNTER s19 -- is the generator class's EVALUATION layer independent, or one copied harness?

s16 recorded 13 independent zeros on multiplicity control. That count is only meaningful if the
13 evaluation layers are independently authored. This measures it two ways:
  (A) function-level cross-repo duplication over AST-normalised bodies (identifiers erased),
  (B) does the repo COMPUTE a factor score locally at all, or only READ the platform's numbers?
Run against /tmp/bc19 shallow clones (14 permissive repos, s15 licence split).
"""
import ast, hashlib, json, pathlib, re, sys, collections

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/bc19")

EVAL_VOCAB = re.compile(r"\b(sharpe|information[_ ]?coeff|\bic\b|fitness|turnover|drawdown|"
                        r"backtest|pnl|returns?|evaluate|score|metric)", re.I)
# does the repo compute a score, or read one from the platform response?
LOCAL_COMPUTE = re.compile(r"(np\.|numpy|pandas|\.mean\(|\.std\(|\.corr\(|spearman|pearson)")
PLATFORM_READ = re.compile(r"(is\.sharpe|\"sharpe\"|'sharpe'|\bis\[|/alphas/|simulations|"
                           r"api\.worldquantbrain\.com)", re.I)


class Norm(ast.NodeTransformer):
    """erase identifiers/constants so copy-with-rename still collides"""
    def visit_Name(self, n):
        return ast.copy_location(ast.Name(id="_", ctx=n.ctx), n)
    def visit_arg(self, n):
        return ast.copy_location(ast.arg(arg="_", annotation=None), n)
    def visit_Attribute(self, n):
        self.generic_visit(n)
        return ast.copy_location(ast.Attribute(value=n.value, attr="_", ctx=n.ctx), n)
    def visit_Constant(self, n):
        return ast.copy_location(ast.Constant(value=None), n)


def fn_hashes(path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.get_source_segment("", "") # placeholder
            n_stmt = sum(1 for _ in ast.walk(node))
            if n_stmt < 25:          # skip trivial wrappers -- they collide by chance
                continue
            norm = Norm().visit(ast.parse(ast.unparse(node)))
            h = hashlib.sha1(ast.dump(norm).encode()).hexdigest()[:16]
            out.append((node.name, h, n_stmt))
    return out


repos, by_hash = {}, collections.defaultdict(set)
hash_names = {}
for repo in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    pys = [p for p in repo.rglob("*.py") if ".git" not in p.parts]
    eval_files = [p for p in pys
                  if EVAL_VOCAB.search(p.read_text(encoding="utf-8", errors="replace"))]
    txt = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in eval_files)
    fns = []
    for p in eval_files:
        for name, h, n in fn_hashes(p):
            fns.append((name, h))
            by_hash[h].add(repo.name)
            hash_names.setdefault(h, name)
    repos[repo.name] = {
        "py_files": len(pys), "eval_files": len(eval_files),
        "eval_fns_ge25nodes": len(fns),
        "local_compute_hits": len(LOCAL_COMPUTE.findall(txt)),
        "platform_read_hits": len(PLATFORM_READ.findall(txt)),
        "_hashes": {h for _, h in fns},
    }

shared = {h: sorted(r) for h, r in by_hash.items() if len(r) > 1}
print(f"repos: {len(repos)}   shared normalised eval-functions: {len(shared)}")
for h, rs in sorted(shared.items(), key=lambda kv: -len(kv[1]))[:25]:
    print(f"  {hash_names[h]:38s} {len(rs)} repos: {', '.join(rs)}")

# pairwise jaccard over eval-function hash sets
names = sorted(repos)
pairs = []
for i, a in enumerate(names):
    for b in names[i + 1:]:
        A, B = repos[a]["_hashes"], repos[b]["_hashes"]
        if not A or not B:
            continue
        inter = len(A & B)
        if inter:
            pairs.append((round(inter / len(A | B), 3), inter, a, b))
print("\npairwise overlap (jaccard, shared_fns):")
for j, n, a, b in sorted(pairs, reverse=True):
    print(f"  {j:.3f}  {n:4d}  {a}  ~  {b}")

print("\nper-repo local-compute vs platform-read:")
for r, d in repos.items():
    print(f"  {r:42s} py={d['py_files']:4d} evalf={d['eval_files']:4d} "
          f"fn={d['eval_fns_ge25nodes']:4d} local={d['local_compute_hits']:6d} "
          f"platform={d['platform_read_hits']:5d}")

for d in repos.values():
    d.pop("_hashes")
json.dump({"measured_at": "2026-08-29", "seat": "brain_hunter_s19",
           "per_repo": repos,
           "shared_fn_count": len(shared),
           "shared_fns": {hash_names[h]: rs for h, rs in shared.items()},
           "pairwise_overlap": [{"jaccard": j, "shared": n, "a": a, "b": b} for j, n, a, b in sorted(pairs, reverse=True)]},
          open("data/brain_hunter_s19_evaluation_axis.json", "w"), indent=1)
