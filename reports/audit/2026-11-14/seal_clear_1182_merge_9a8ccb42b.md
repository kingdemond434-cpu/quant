# SEAL CLEAR: #1182 LIVE merge 9a8ccb42bc5141154bee535403e8eb2a3faa1646 (promoter.py)

Auditor, 2026-11-14.

- Reproduced independently: `git merge-tree --write-tree` of the CLEARed #1182 head 494e872dd and LIVE (promoter blob 57eb00b19, after #1183) leaves exactly three conflicts: promoter.py, quantbench.py and IMMUTABLE_MANIFEST.json.
- promoter.py's only conflict is the `collections.abc` import line. Resolving it as `from collections.abc import Callable, Iterable` gives blob d8ed6fe696b87999fb781db9c425e1c1fdb079ad, sha256 2e10fc90ef1e9180fc395d1287b60ba1df34eff521c547c3cc224f96af45b272. That is byte-identical to the merge's own blob in 1182_merge_vs_LIVE_9a8ccb42b.diff.
- quantbench.py and IMMUTABLE_MANIFEST.json are taken from LIVE. Both sides changed only seal-train pins there, and sign_train re-signs them for the merged promoter.
- Verdict: CLEAR for promoter.py at that sha256. PROTECTED: the merge still needs a fresh APPROVE MERGES, and the merge head itself needs a re-CLEAR once it is pushed.
