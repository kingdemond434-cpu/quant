---
id: L0300
cost: blind
tags: ["wiring", "measurement"]
---

# L0300

Two implementations of one digest will disagree. Put the hash algorithm in a FILE both machines run, never one hasher here and another there -- and if the two checkouts normalise line endings differently by design, fold CRLF to LF before hashing rather than declaring raw bytes the rule.

## Evidence

2026-09-14 check_desk_code_parity hashed sha256(read_bytes()) here and Get-FileHash on the box, and reported 10 of 34 money-path modules DIVERGED. Nine were false: the box's hash equalled origin's exactly while the CRLF checkout's did not. Its own docstring had diagnosed line endings as the cause and prescribed raw bytes, which guarantees it. heal() ships on divergence, so armed healing would have looped forever.

## Tags

#wiring #measurement

## Related

- [[l0001-a-heartbeat-proves-the-loop-is-alive-never-that-the-pi]]
- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0016-any-guard-whose-ambiguous-branch-allows-the-action-is-]]
- [[l0018-one-config-line-drifting-from-its-siblings-kills-organ]]
- [[l0035-volatility-is-predictable-direction-is-not-difficulty-]]
- [[l0036-a-0-guard-does-not-survive-floating-point-dust-use-a-m]]
- [[l0051-an-inert-gate-s-constants-are-never-calibrated-so-wiri]]
