---
id: L0148
cost: blind
tags: ["data-acquisition"]
---

# L0148

Assert content-type and magic bytes on every fetch, never the status code. A JS-rendered site answers 200 with a ~5KB shell for content it does not serve, so a 200 is a THIRD false-null class -- reachable-but-contentless -- byte-identical to an exhausted ground for any pipeline treating 200 as success. And when an archive/export route serves the shell, the file lands with the right NAME and the wrong TYPE.

## Evidence

kaggle.com/c/30894/publicleaderboarddata.zip returns HTTP 200 content-type text/html 5,593 bytes, so curl -o lb.zip succeeds and writes an HTML file called lb.zip (a real zip starts PK); kaggle serves NO robots.txt at all (404 to ClaudeBot/curl/Googlebot) so a robots-only check reads the ground as open. Measured 2026-08-13, OP-068.

## Tags

#data-acquisition

## Related

- [[l0006-an-exit-code-proves-a-process-ended-never-that-it-prod]]
- [[l0009-campaign-width-buys-nothing-and-length-buys-everything]]
- [[l0012-no-economic-mechanism-means-overfit-a-hard-kill-not-a-]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0030-knowledge-that-is-not-injected-at-runtime-does-not-exi]]
- [[l0032-101-real-production-alphas-average-15-9-pairwise-corre]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
