---
id: L0211
cost: blind
tags: ["legitimacy"]
---

# L0211

A 5xx robots.txt and a 404 robots.txt give OPPOSITE verdicts and look identical in a terminal. RFC 9309: UNAVAILABLE (5xx) means treat as FULL disallow; ABSENT (404) means unrestricted. Never read an error body as 'no restrictions', and never let another host's robots stand in -- robots is HOST-scoped.

## Evidence

datafeed.dukascopy.com/robots.txt 503 x3 (107B HAProxy body) while www.dukascopy.com/robots.txt is 200 'Allow: /'; www.boj.or.jp/robots.txt 404 = genuinely open. Nearly bulk-pulled a fully-disallowed host.

## Tags

#legitimacy

## Related

- [[l0059-a-guard-that-enumerates-a-hardcoded-subset-of-its-inpu]]
- [[l0092-the-suite-ran-must-mean-n-tests-executed-never-the-com]]
- [[l0093-when-two-lineages-fix-the-same-bug-in-different-places]]
- [[l0096-establish-a-source-s-legitimacy-posture-with-a-ua-matr]]
- [[l0130-when-a-primary-source-is-login-walled-hunt-its-reimple]]
- [[l0140-read-the-producer-s-actual-keys-before-trusting-a-get-]]
- [[l0142-when-a-correction-runs-conservative-nobody-audits-it-s]]
- [[l0143-for-a-pooled-ic-the-breadth-that-sets-the-standard-err]]
