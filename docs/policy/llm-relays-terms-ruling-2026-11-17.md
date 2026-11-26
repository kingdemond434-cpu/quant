# Ruling: three LLM relays (hcnsec, AgentRouter, YJS) — 2026-11-17

**Ruling: all three are REFUSED for now. No organ, seat or session sends a request to them.** Each can be re-heard once the conditions at the end are met.

Evidence comes from pages fetched on 2026-11-17 18:30Z, with an honest client.

| Relay | What it showed | Verdict |
|---|---|---|
| api.hcnsec.cn | It describes itself as a free "public-benefit large-model security gateway" that pools Chinese models (GLM, DeepSeek, Qwen, Kimi, Step) behind "一个密钥调用全部模型" (one key calls all models), with free quota for signups and daily check-ins. It publishes **no terms, no privacy or logging policy, and no statement of where its keys come from**. Its robots.txt says `Disallow: /api/`. | REFUSED. robots disallows the API path, and fetching fails closed (robots ruling, LAWS 5e as amended 11-17). There are no terms and no data policy. |
| agentrouter.org | Every path, including /terms and /robots.txt, returned an Aliyun WAF JavaScript challenge. No terms or robots file could be read. | REFUSED (fail closed). Terms and robots are unreadable, and the bot wall is not worked around (hard rule). |
| api.yjs.im ("Jasper") | A JavaScript-only shell describing a "unified AI API gateway: one key connects multiple model providers". It names no upstream vendors and shows no terms. Its robots.txt returned an error. | REFUSED (fail closed). Terms and robots are unreadable, and the upstream is undisclosed. |

## Why this matters beyond robots

- **Key provenance.** A free or cheap gateway that resells several vendors' models through "one key" usually runs on pooled or shared upstream keys. Most vendors forbid sharing or reselling keys. Using such a gateway makes the desk party to that breach, and access can vanish without warning when the keys are revoked. None of the three claims to be an authorised reseller.
- **Data.** Every prompt the desk sends carries research context, such as hypotheses, sleeve logic and sometimes account state. None of the three says what it logs or keeps, and all are run by unidentified operators. Sending desk IP to them is an unbounded leak.
- **Consistency.** These rulings apply the same rule: FRED (11-13), Wayback/YouTube mirrors (11-14) and prop showcases (11-14).

## What would let one be re-heard

A relay can be re-heard when all of these hold:
1. It publishes readable terms that allow API use by automated clients.
2. Its robots does not disallow the API path.
3. It names its upstream models and is the vendor itself or an authorised reseller or partner.
4. It publishes a data and logging policy.

Directly using the underlying vendors' own free tiers (DeepSeek, Qwen/DashScope, Zhipu GLM, Moonshot Kimi, StepFun) under their own terms is the lawful route to the same models.

Governance thread, 2026-11-17. Journal row to follow in the next Governance PR once the LIVE law gate is green again (#1244).

---

## OWNER OVERRIDE, 2026-11-17 18:34:53Z: the three relays are ALLOWED

zuck wrote "js let me do it theyre all verified" (message cmsg_012XFUfE12Rvggnu86fDb8prUH3jm6Vr5Pc1j5yCdxkRGi). He checked the three relays himself, will add the keys himself, and accepts the key-provenance risk described above. This replaces the refusal for hcnsec, AgentRouter and YJS only. It sets no precedent for other sources, and the general robots and terms rule (LAWS 5e as amended) stands. Governance reads hcnsec's `Disallow: /api/` as aimed at crawlers rather than at an account holder's keyed API calls. On that reading, this use does not breach the robots rule.

The protections that remain are conditions of the ALLOWED ruling. Breaking one returns a relay to REFUSED:
1. **Public prompts only.** `assert_public` runs before every relay call and fails closed. No account state, balances, sleeve parameters, failed-rule near-misses, edge content or desk-private rows ever go to a relay. Critic and mutation inputs built from the desk's own near-misses stay on non-relay seats.
2. **Proposals only.** Relay output lands in data/intelligence/ in the discovery contract and goes through the gauntlet like any other donation. Nothing from a relay reaches sizing, capital, promotion or orders, and no relay is ever on a live or money path.
3. **Keys are the owner's.** Keys live in data/secrets/** on the box only. No agent signs up for a relay, creates a key or stores one.
4. **Fail closed.** If a relay changes its terms to forbid this use, or starts returning a bot wall to the API path, its seat goes DARK.

ops/relay_terms_rulings.json (#1245) records each as `{"ruling": "ALLOWED", "ref": "governance/llm-relays-terms-ruling-2026-11-17.md#owner-override (zuck 2026-11-17 18:34:53Z)"}`.
