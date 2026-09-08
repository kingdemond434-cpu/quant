---
id: L0240
cost: told the principal a live book was unaffected by a gate that was refusing it
tags: ["reading-code", "reporting"]
---

# L0240

A guard in the CALLER is invisible from the callee. Before reporting what gates a code path, find every call site of the function that acts -- reading the acting function alone answers a different question than the one asked.

## Evidence

gateway.place_bracket tests st['armed'] and nothing else, so I reported gold unaffected by the release-identity gate and told the principal so twice. Its caller, the bracket loop, checks `if not NEW_RISK_OK` at gateway.py:2116 and logs 'bracket NOT placed: release identity refuses new risk' without ever reaching place_bracket. NEW_RISK_OK had never once been true, so gold placed nothing either -- and matched_fills:0 on an account that has never held a position was the evidence sitting in the same state file I was quoting from.

## Tags

#reading-code #reporting

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0017-a-pre-filter-s-false-negatives-are-structurally-invisi]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0023-never-accept-done-for-a-human-step-verify-with-the-act]]
- [[l0034-never-slide-a-signal-parameter-to-clear-an-observation]]
