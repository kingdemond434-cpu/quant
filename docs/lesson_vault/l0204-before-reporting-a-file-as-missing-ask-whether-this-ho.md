---
id: L0204
cost: wasted
tags: ["data-provenance"]
---

# L0204

Before reporting a file as missing, ask whether THIS host holds the whole tree. A provenance stamp is the discriminator a directory walk cannot fake: merge() stamps only symbols it actually opened, so 'stamped today but no file here' means NOT SYNCED, never ABSENT. Report n_unobservable as its own count, never folded into n_dead.

## Evidence

2026-08-28: universe.json records 6,305-26,168 bars for all 54 'bar-less' MT5 symbols with _provenance.bars.source=parquet_on_disk at the same second as the 197 present; stamped_today minus files_here = exactly those 54; mtime census 173 files at 08-26T11:06 vs 24 at today = the partial sync, and 24 was reported as 'the only fresh symbols'

## Tags

#data-provenance

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0042-a-candidate-dropped-before-scoring-is-not-a-small-loss]]
- [[l0050-before-trusting-any-imported-statistical-construction-]]
- [[l0055-a-false-positive-gate-is-self-amplifying-when-its-metr]]
- [[l0057-a-red-pytest-leg-can-mean-zero-tests-ran-a-test-module]]
