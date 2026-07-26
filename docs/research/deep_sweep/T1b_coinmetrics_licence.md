# [T1-b] Coin Metrics Community data — LICENCE RULING DOSSIER

**Status:** COMPLETE — awaiting principal ratification (opened & closed 2026-07-26)
**Author:** literature deep-miner, research-only under hard freeze
**Not legal advice.** This is a DESK RECOMMENDATION with primary text quoted so a human principal
can ratify or overturn it. No agent self-approval.

---

## ⏱ BOTTOM LINE (the rest of this document is the evidence)

**1. OPERATIVE DOCUMENT.** Coin Metrics **Terms of Use §4.1** — not the GitHub repo LICENSE, and not
the "Coin Metrics Master Terms" PDF (that one is a paid Order-Form contract with **zero** mentions
of Community / Creative Commons / non-commercial). The ToU has been **deleted from the live web**:
Coin Metrics was acquired by Talos and `coinmetrics.io/terms-of-use/` now **301s to a marketing
page**. Recovered from the Internet Archive's last capture (2026-02-06) and confirmed **stable
across four captures spanning 18 months**. The grant:

> *"…a limited non-exclusive, non-transferable, worldwide right (i) to access and use the Services
> **solely for non-commercial internal business purposes**, and (ii) to access, copy, display,
> perform, and use Coin Metrics Content **for non-commercial internal business purposes** pursuant
> to the terms of the Creative Commons Attribution-Non Commercial 4.0 International (CC BY-NC 4.0)
> License…"*

**2. RULING: 🔴 EXCLUDE for production. 🟡 RESEARCH-ONLY (winding down) for what's already done.**
Confidence HIGH on the production half. Three reasons the "but it's purely internal" defence fails:
CM's own gloss says *non-commercial **internal business** purposes* — it pre-empts that exact
argument; the NC test is about **primary purpose**, and a trading signal's only purpose is money;
and **CM's licence — unlike Upbit's — contains no affirmative permission to backtest or develop
strategies.** **Do not rule on Upbit by analogy: Upbit is on the line, Coin Metrics is over it.**

**3. ⚠️ A SECOND BLOCKER THE DESK HAS NEVER FLAGGED — ToU §6(iii) bans using the Services "TO INPUT
INTO, DEVELOP, TRAIN, IMPROVE, GENERATE OUTPUT FROM, OR OTHERWISE USE IN RELATION TO, ANY AI SYSTEM
… [including] MACHINE MODELS."** This is **not** a NonCommercial question, so **a favourable NC
ruling would not clear it.** Any fitted/learned model on this data is exposed regardless.

**4. THE DESK LOSES A FEED, NOT ITS FINDINGS.** The negative result — *the exchange-flow/MVRV metric
class carries no daily-horizon edge over 15 years* — is the desk's **own measurement**. It survives
EXCLUDE intact. The $799/mo × 2 question stays answered at $0.

**5. RECONSTRUCTION IS VIABLE — this is the real deliverable.**
- **The methodology is fully published by the vendor, with a worked numeric example** (§4.2). Nothing
  to reverse-engineer, and it yields a free unit test.
- **The metric telescopes into a stateless cumulative sum** — no UTXO set needed. ~1 week of work.
- **Substrate: AWS Public Blockchain, genesis → today, keyless — and it is *more* permissive than
  the desk's registry says (MIT-0, no citation duty, not "Apache-2.0 + citation"). Registry
  corrected this run.**
- **Honest residual:** no free+clean+full-history *hosted* source exists (11 candidates, all
  graded); and the **price leg has a real ~13.5-month gap (2010-07-17 → 2011-08-29)** with a
  documented $0-convention workaround.

**6. CHEAPEST UNBLOCK, and it is Creative Commons' own advice: ASK.** One email to Coin Metrics /
Talos could convert EXCLUDE → ADOPT in a single reply. **Human action — an agent must not send it.**

---

## THE QUESTION, STATED EXACTLY

> May this desk use **Coin Metrics Community** data to build signals that **eventually trade real
> capital** (own account, no redistribution, no client advice)?

## WHY IT IS BLOCKING

- `docs/graveyard.md` → `cm_mvrv_btc_daily_level` was Stage-A screened on this data; the entry ends
  *"Data: free CM community CSV (CC BY-NC — licence ruling pending for production use)."*
- `docs/research/data_axis_watchlist.md` card 7 (Glassnode/CryptoQuant replacement) is
  `needs-legitimacy-review`, routed to GAP_REGISTER #67, and is WIRED to
  `data/coinmetrics_flows.jsonl` (9,866 daily rows, btc 2010-07-18 → 2026-07-25).
- A 15-year keyless daily backfill axis is gated on the answer.

## PRIOR STATE / RUN-1 GAP (read before searching)

1. Run 1 read the **GitHub repo** `LICENSE` → CC BY-NC 4.0.
2. Run 1 did NOT read the **community API** terms — the page *"redirects; read the current terms
   before any ruling."*
3. Inbox note: `coinmetrics/data` GitHub repo **went stale 2026-05-24**; the live path is the
   community API. So the repo LICENSE may not be the governing document any more.

## PLAN (append results below as each resolves)

- [x] §1 Follow the redirect → current primary terms for the Community API. Quote operative clauses.
- [x] §2 Reconcile repo CC BY-NC 4.0 vs API terms. Which governs? Does staleness change it?
- [x] §3 Rule on the NonCommercial crux (CC's own NC guidance + any CM statement). ADOPT /
      RESEARCH-ONLY / EXCLUDE.
- [x] §4 FREE-FRONTIER RECONSTRUCTION: realized-cap / MVRV / cost-basis from raw chain data or a
      cleanly-licensed alternative. Licence + history depth for each candidate.

---

# §1 — WHERE THE REDIRECT GOES, AND WHAT THE OPERATIVE DOCUMENT SAYS

## 1.0 THE HEADLINE RUN 1 MISSED: **COIN METRICS NO LONGER EXISTS AS AN INDEPENDENT VENDOR**

The "terms page redirects" note in run 1 was not a broken link. It is a **corporate event**.
Talos announced its acquisition of Coin Metrics on **2025-07-16**; by the time of this run the
entire `coinmetrics.io` marketing + legal estate has been folded into `talos.com`.

Probed 2026-07-26 (exact `curl` first-hop results, not memory):

| URL requested | first-hop | Location |
|---|---|---|
| `https://coinmetrics.io/` | 301 | `https://www.talos.com/our-solutions/data/overview` |
| `https://coinmetrics.io/terms-of-use/` | **301** | `https://www.talos.com/our-solutions/data/overview` |
| `https://coinmetrics.io/privacy-policy/` | 301 | `https://www.talos.com/our-solutions/data/overview` |
| `https://coinmetrics.io/cm-labs/` | 301 | `https://www.talos.com/our-solutions/data/overview` |
| `https://coinmetrics.io/community-network-data-license-agreement/` | 301 | `https://www.talos.com/our-solutions/data/overview` |
| `https://coinmetrics.io/community-network-data/` | 301 | `https://www.talos.com/our-solutions/data/community-resources` |
| `https://docs.coinmetrics.io/` | 200 | (live, still Coin Metrics-branded) |

**The critical structural fact: `coinmetrics.io/terms-of-use/` does not redirect to a replacement
terms page. It redirects to a product marketing page.** The governing document for free/Community
users has been **removed from the live web without a successor** being published in its place.
That is the single most important finding in §1 and it changes the shape of the ruling
(see §3.5 — "no live terms" is a risk, not a permission).

Acquisition sources opened: `https://www.talos.com/spotlight/coinmetrics` (200),
`https://www.talos.com/insights/talos-to-acquire-coin-metrics`. The archived Labs page footer
confirms it in Coin Metrics' own words: *"Coin Metrics has been acquired by Talos."*

## 1.1 THE LIVE FIRST-PARTY STATEMENT (docs, 200, current)

`https://gitbook-docs.coinmetrics.io/packages/coin-metrics-community-data` (200) — and its raw
markdown twin `.../coin-metrics-community-data.md` (200, 3,097 B), which is the cleanest verbatim
source. Page states *"Last updated 1 month ago"* (≈ June 2026), i.e. it is **live and maintained
post-acquisition**. Verbatim:

> ```
> # Coin Metrics Community Data
>
> {% hint style="info" %}
> Available to the community under the [Creative Commons](https://creativecommons.org/licenses/by-nc/4.0/) license.
> {% endhint %}
> ```

> "**Coin Metrics Community Metrics** (Community API, Data Visualization) is a subset of our
> Network Data Pro and Market Data Pro data available for free for community use."

> "For more info on our Community terms and offerings see our [Labs](https://coinmetrics.io/cm-labs/) page."

> "The Community HTTP API root endpoint URL is `https://api.coinmetrics.io/v4`. API key is not
> required when accessing community endpoints." / "10 requests per 6 seconds sliding window for an
> IP address."

**Two things follow.** (a) The live, maintained, first-party doc **explicitly and currently**
places Community data under **CC BY-NC 4.0** — the hyperlink target is literally
`creativecommons.org/licenses/by-nc/4.0/`. The NC question is therefore *not* an artefact of a
stale repo. (b) The doc's own pointer to the fuller Community terms — the Labs page — **is a dead
link** (301 to Talos marketing). The vendor is pointing users at terms it has taken down.

## 1.2 THE FULL OPERATIVE TERMS — RECOVERED FROM ARCHIVE, AND VERSION-STABLE

Since the live page is gone, the operative text was read from the Internet Archive (a public
archive of a public page — no circumvention, no paywall, no credential):

- **`http://web.archive.org/web/20260206210011/https://coinmetrics.io/terms-of-use/`** (200)
  — the **most recent capture that exists**. CDX shows **no capture after 2026-02-06**.

**§4.1 Grant of Rights to All Users — THE OPERATIVE CLAUSE, quoted verbatim:**

> "Subject to your compliance with the terms and conditions of this Agreement, Coin Metrics hereby
> grants to each Service User, under Coin Metrics' intellectual property rights, a limited
> non-exclusive, non-transferable, worldwide right (i) to access and use the Services **solely for
> non-commercial internal business purposes**, and (ii) to access, copy, display, perform, and use
> Coin Metrics Content **for non-commercial internal business purposes** pursuant to the terms of
> the Creative Commons Attribution-Non Commercial 4.0 International (CC BY-NC 4.0) License
> (available at creativecommons.org/licenses/by-nc/4.0/)."

**§2 Our Services: Overview — why this document, and not the Master Terms, governs free users:**

> "We may also offer paid subscriptions for products from time to time – if we do so, your use of
> such products will be subject to a separate license agreement between you and Coin Metrics and
> **will not be subject to these Terms**."

**§1 Your Agreement — the ToU binds the desk as an entity, by access alone:**

> "PLEASE READ THIS DOCUMENT CAREFULLY BEFORE YOU ACCESS THE SERVICES. **BY ACCESSING SERVICES, YOU
> AGREE TO BE BOUND BY THE TERMS AND CONDITIONS SET FORTH BELOW.**"
> "If you are agreeing to these Terms … on behalf of a company or other legal entity (your
> 'Organization') … the terms 'you' and 'your' means your Organization on whose behalf you are acting."

Note the definition sweeps the whole surface the desk actually used:
> "Coin Metrics Inc. … has created this website …, its associated applications and plugins, **API
> data feeds** and any Coin Metrics Content … (collectively, the 'Services')".
So the **keyless community API is squarely inside "the Services"** — no argument that an
unauthenticated endpoint is outside the ToU.

### ⚠️ 1.3 SECOND BLOCKER — **THE AI-SYSTEM CLAUSE. THE DESK HAS NEVER FLAGGED THIS. IT IS ARGUABLY MORE BINDING THAN THE NC CLAUSE.**

**§6 Restrictions**, verbatim (capitalisation is the original's):

> "EXCEPT AS EXPRESSLY PROVIDED HEREIN OR IF OTHERWISE EXPRESSLY PERMITTED BY COIN METRICS (e.g.,
> to the extent made available by Coin Metrics **through GitHub** or subject to separate license
> from Coin Metrics), YOU AGREE NOT TO (i) DUPLICATE, PUBLISH, DISPLAY, DISTRIBUTE, MODIFY, OR
> CREATE DERIVATIVE WORKS FROM THE MATERIAL PRESENTED THROUGH THE SERVICES UNLESS SPECIFICALLY
> AUTHORIZED IN WRITING BY COIN METRICS; (ii) REVERSE ENGINEER, DECOMPILE, DISASSEMBLE, OR OTHERWISE
> SEEK TO DISCOVER THE SOURCE CODE OF THE COIN METRICS SERVICES AND UNDERLYING SOFTWARE; OR **(iii)
> UTILIZE THE SERVICES TO INPUT INTO, DEVELOP, TRAIN, IMPROVE, GENERATE OUTPUT FROM, OR OTHERWISE
> USE IN RELATION TO, ANY AI SYSTEM. AI SYSTEM MEANS (I) ANY ARTIFICIAL INTELLIGENCE MODELS, MACHINE
> MODELS OR LARGE LANGUAGE MODELS, OR (II) ANY OTHER SOFTWARE, TOOL, OR SYSTEM THAT PERFORMS A
> SIMILAR PURPOSE.**"

Why this matters more than it looks:
- It is **not** a NonCommercial restriction, so **it binds even if the NC question resolves in the
  desk's favour**. A research-only ruling does not clear it.
- "**MACHINE MODELS**" is not defined narrowly. Read plainly it reaches a fitted statistical /
  ML model — which is what a systematic signal is. A hand-written arithmetic threshold on MVRV is
  a weaker fit for "AI System" than a trained model, but the clause also says "**OR OTHERWISE USE
  IN RELATION TO**", which is about as broad as drafting gets.
- The `libs/research/axis_screen` Stage-A screen the desk already ran (IC, z-scores, regressions) is
  best characterised as statistics rather than an "AI System" — but any escalation to a fitted or
  learned model walks straight into §6(iii).
- **And a live one the desk should notice about itself:** this desk is operated by LLM agents that
  read Coin Metrics documentation and handle Coin Metrics data. On a literal reading, §6(iii)
  reaches that too. *(Discipline note: GitBook offers an `?ask=` LLM query endpoint on these very
  docs and expressly invites agent use — "designed so that both humans and AI agents can read,
  navigate, and reason over technical content." It was **deliberately not used** in this run. The
  needed methodology provenance was obtainable from ordinary page reads, and there was no reason to
  push on a clause the desk is in the middle of ruling on.)*

**§7 Code of Conduct** also contains a clause the desk's own framing rubs against — the whole
`data_axis_watchlist.md` card 7 is titled *"Glassnode / CryptoQuant vendor-replacement"*:

> "Access the Services to develop or implement a product or service that will act as a **substitute
> for or otherwise compete with** the Services."

Desk read: a purely internal, never-distributed signal is not a "product or service", so this is
probably not triggered — but it is a live consideration a principal should see, not one an agent
should quietly resolve.

**§7 also bars** *"'data harvesting,' 'web scraping,' or … other means we have not intentionally
made available"* and *"Use VPNs, proxy servers, or other means to … circumvent any rate limits"*.
The desk's collector used the documented public endpoint within the published 10-req/6-s limit, so
this is clean — worth recording that it is clean.

**§10 Termination for Cause:** breach → written notice → **five (5) day cure period**.

## 1.4 VERSION STABILITY — THIS IS NOT A DRAFTING ACCIDENT

The three load-bearing strings were checked across four independent archive captures:

| Capture | §4.1 "Grant of Rights to All Users" | "non-commercial internal business" | "AI SYSTEM" |
|---|---|---|---|
| `20240826203253` | FOUND | FOUND | FOUND |
| `20251221134925` | FOUND | FOUND | FOUND |
| `20260119091920` | FOUND | FOUND | FOUND |
| `20260206210011` (latest) | FOUND | FOUND | FOUND |

§4.1's wording is **byte-stable over ~18 months** (only a bare-URL vs full-URL formatting change).
Conclusion: the NC restriction and the AI-System ban are **settled, deliberate, long-standing
terms**, not transitional text that an acquisition might have left behind by mistake.

## 1.5 THE DOCUMENT THAT IS **NOT** OPERATIVE — "Coin Metrics Master Terms"

Chased because `https://www.talos.com/terms-of-use` (200, "Last Updated January 4, 2024") links out
to a document literally named *"Coin Metrics Master Terms"*:
`https://cdn.prod.website-files.com/637e4cd92c6f22a30d5225fc/6a0c9c3a966cd03e62a26599_Master-Terms-Jan-6-2025.pdf`
(200, application/pdf, 195,031 B, dated **Jan 6 2025**).

Text extracted and searched. **It does NOT govern Community users, and the document says so itself:**

- Keyword scan of the full extracted text: **`Community` 0 hits · `Creative Commons` 0 hits ·
  `non-commercial` 0 hits · `free of charge` 0 hits · `trial` 0 hits · `redistribut` 0 hits ·
  `Attribution` 0 hits.**
- Scope is Order-Form-bound: *"**Customer** means the customer entity identified on the **Order
  Form**."* · *"**Order Form** means a written document … **signed by both Parties** detailing the
  specific Services to be provided, the applicable **Fees** …"* · §1.1 *"CM will provide to Customer
  the Services described on the applicable Order Form."*
- A keyless Community user has no Order Form and is not a "Customer" ⇒ **not bound by, and gets no
  rights from, the Master Terms.** This also matches ToU §2's own split (paid ⇒ separate agreement,
  "will not be subject to these Terms").

Recorded for completeness — its §5.1(iv) *"use the Services only for Customer's own internal
business purposes"* and its §1.3 Derived Data definition are the **paid** tier's shape, and are a
useful preview of what a paid licence would buy (see §3.6).

> **METHOD NOTE / CAPABILITY FINDING FOR THE DESK (worth keeping).** `data_axis_watchlist.md` card 8
> records *"no PDF tooling on this box"* as a hard limit that left the Kaiko rulebook interior
> unread. **That limit is now refuted for text-based PDFs.** `pdftotext`/`poppler`/`pypdf`/`pymupdf`
> are all absent, and the Read tool's PDF path needs `pdftoppm`, but a ~20-line pure-stdlib Python
> extractor (regex the `stream…endstream` blocks → `zlib.decompress` → pull the `(...)` text-show
> operands) recovered **116,875 characters** from this PDF with zero installs. The Kaiko rulebook
> is re-openable by the same route.

---

# §2 — RECONCILING THE TWO DOCUMENTS

## 2.1 What the GitHub repo actually says (re-read this run, not from run 1's memory)

`https://raw.githubusercontent.com/coinmetrics/data/master/LICENSE` (200), in full:

> "This work by Coin Metrics, Inc is licensed under the Creative Commons
> Attribution-NonCommercial 4.0 International License. To view a copy of this license, visit
> http://creativecommons.org/licenses/by-nc/4.0/ or send a letter to Creative Commons, PO Box 1866,
> Mountain View, CA 94042, USA."

`https://raw.githubusercontent.com/coinmetrics/data/master/README.md` (200), §License:

> "This data is published in the hope it will be useful, but without any warranty. You are using it
> at your own risk."
> "Data is made available under the [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) license."

Repo state via `https://api.github.com/repos/coinmetrics/data` (200): **`archived: false`**,
`pushed_at: 2026-05-24T13:38:09Z`, latest commits `f1a36afb 2026-05-24 "Update CSV 2026-05-24"`,
then nothing. So it is **abandoned-in-place, not formally archived** — ~2 months dark as of today.
(GitHub's licence detector reports `NOASSERTION` only because the LICENSE file is a pointer, not
the full CC legal code; the human-readable text is unambiguous.)

## 2.2 DO THEY CONFLICT? — **NO. AND THAT IS THE IMPORTANT ANSWER.**

Run 1 framed this as "repo says X, API might say Y". It doesn't. **Both documents independently
land on CC BY-NC 4.0**, and the live docs page makes it three:

| Surface | Document | Licence stated | Read this run? |
|---|---|---|---|
| GitHub bulk CSV | repo `LICENSE` + `README.md` | CC BY-NC 4.0 | ✅ 200 |
| Community API | ToU §4.1 (archived, latest capture) | CC BY-NC 4.0 **+ "non-commercial internal business purposes"** | ✅ 200 |
| Community API | live docs `coin-metrics-community-data` | CC BY-NC 4.0 (hyperlinked) | ✅ 200 |

**There is no conflict to resolve, and therefore no route by which the desk gets a better answer
from one surface than the other.** The prior state's hope — that the API terms might turn out
looser than the repo's CC BY-NC — is **closed out negative**. This is a real deliverable: the
"read the current terms before any ruling" gap is now closed, and it closed *against* the desk.

## 2.3 Which governs, and does the 2026-05-24 staleness change it?

**Which governs: the ToU governs the API; the repo LICENSE governs the repo files. Both apply,
because the desk used both surfaces** (`data/coinmetrics_flows.jsonl` was built from the live API;
the earlier `btc.csv` pull came from the repo).

**Does staleness change which document is operative? — Materially, no, and in two directions:**

1. **It does not soften anything.** An abandoned repo does not relicense itself. The CC BY-NC 4.0
   grant on the files already published stays exactly as granted; CC 4.0 licences are irrevocable
   for what was already released. Staleness changes *freshness*, not *permission*.
2. **It shifts the desk's exposure to the stricter document.** Because the repo stops at
   2026-05-24, the only way to get current data is the **API** — which is the surface carrying the
   *extra* restrictions the repo does not have: the ToU's "**non-commercial internal business
   purposes**" gloss (§4.1), the **AI-System ban** (§6(iii)), and the **compete/substitute**
   clause (§7). So the practical effect of the repo going stale is that the desk is pushed onto
   the **more restrictive** of the two paths, not the looser one.
3. **One genuine asymmetry, in the desk's favour, worth noting:** ToU §6's own preamble carves out
   *"to the extent made available by Coin Metrics **through GitHub**"* from the §6 restrictions.
   Read literally, **material obtained from the GitHub repo is exempted from §6 — including the
   AI-System ban in §6(iii)** — and is governed by bare CC BY-NC 4.0 alone. That is a narrow but
   real distinction between the two surfaces. It is also a wasting asset: the repo ends 2026-05-24,
   so this exemption covers a **frozen** archive (btc 2009-01-03 → 2026-05-23) and nothing newer.
   **Flagged as a question for the principal, not resolved by this agent** — it turns on whether
   "made available through GitHub" was meant as a licence carve-out or merely as an
   acknowledgement that the repo exists.

---

# §3 — THE CRUX: DOES "NonCommercial" BAR A PROP DESK TRADING ITS OWN CAPITAL?

## 3.1 Did Coin Metrics ever publish its own gloss on Community/commercial use? — **SEARCHED, NULL**

Negative result, logged as first-class:
- `https://gitbook-docs.coinmetrics.io/resources/faqs` (200) — **no** entry on licence, commercial
  use, redistribution or attribution. Technical FAQ only.
- `https://www.talos.com/our-solutions/data/community-resources` (200, the content-preserving
  successor of `coinmetrics.io/community-network-data/`) — markets Studio and the Community API,
  states **no** licence, commercial-use or attribution terms at all.
- The live docs point to `https://coinmetrics.io/cm-labs/` for *"more info on our Community terms"*.
  That page is now a 301. **And it was already empty before the redirect**: the archived capture
  `http://web.archive.org/web/20251206071501/https://coinmetrics.io/cm-labs/` (200) renders the
  string **"It seems we can't find what you're looking for."** — a blog-category page with zero
  matching posts, not a terms document.
- `https://www.talos.com/terms-of-use` → `https://www.talos.com/legals/terms` (200) — lists exactly
  five documents: *Talos Terms of Service · Coin Metrics Master Terms · Cboe Terms · CME Terms ·
  datonomy Terms* (LAST UPDATED: JANUARY 4, 2024). Keyword scan of the whole page:
  **`Community` 0 hits · `Creative Commons` 0 hits · `non-commercial` 0 hits.**
- **Exhaustive check, not a spot check:** `https://www.talos.com/sitemap.xml` (200) — the acquirer's
  *entire* legal estate is four URLs (`/legals/{terms,privacy,employee-privacy-policy,
  data-processing-addendums}`). **There is no Community, licence, or Creative Commons page anywhere
  on the successor's site.**

> Side observation from the same page, relevant to §3.5: Talos's own published client segments
> include **"Proprietary Trading Firms"**. The successor rights-holder sells commercial data
> products directly into the exact segment this desk occupies.

**Conclusion: there is no Coin Metrics statement anywhere that expands, softens, or clarifies NC
for internal/research/commercial use.** The ToU §4.1 sentence is the entire body of vendor guidance
in existence. The desk must rule on that sentence plus CC's generic guidance — there is no
vendor-specific escape hatch to find. That closes a search, it does not leave one open.

## 3.2 What Creative Commons actually says (primary text, opened this run)

**The definition itself** — `https://creativecommons.org/licenses/by-nc/4.0/legalcode.en` §1 and
`https://wiki.creativecommons.org/wiki/NonCommercial_interpretation`:

> "**NonCommercial means not primarily intended for or directed towards commercial advantage or
> monetary compensation.**"

**CC's interpretation guide** (`https://wiki.creativecommons.org/wiki/NonCommercial_interpretation`),
verbatim — note it opens with its own disclaimer, which this document mirrors:

> "THIS PAGE IS FOR INFORMATIONAL PURPOSES ONLY. CREATIVE COMMONS DOES NOT PROVIDE LEGAL ADVICE OR
> REPRESENTATION. CONSULT YOUR OWN LEGAL COUNSEL FOR LEGAL ADVICE."

> "The definition is **intent-based** and intentionally flexible … The inclusion of '**primarily**'
> in the definition recognizes that no activity is completely disconnected from commercial activity;
> **it is only the primary purpose of the reuse that needs to be considered.**"

> "**NonCommercial turns on the use, not the identity of the reuser.** The definition of
> NonCommercial depends on the primary purpose for which the work is used, not on the category or
> class of reuser. … A reuser that is not obviously noncommercial in nature may use NC-licensed
> content **if its use is NonCommercial in accordance with the definition**. … no class of reuser is
> per se permitted or excluded."

> "**NonCommercial licenses are non-exclusive.** … an NC licensor is free to offer the material
> under other terms, including on commercial terms. … **licensees are always free to contact
> licensors to ask permission to use the work for commercial purposes.**"

> "**Explanations of NC do not modify the CC license.** Some licensors or website providers state
> expectations or interpretations about what NC means. Those explanations never form part of the CC
> license, even if included in terms of service or another resource designed to contractually bind
> reusers. CC strongly discourages the practice when such statements carve back (rather than expand)
> on reuses allowed by the NC definition…"

**CC's FAQ** (`https://creativecommons.org/faq/`, entry *"Does my use violate the NonCommercial
clause of the licenses?"*), verbatim:

> "CC's NonCommercial (NC) licenses prohibit uses that are 'primarily intended for or directed
> toward commercial advantage or monetary compensation.' … Please note that **CC's definition does
> not turn on the type of user**: if you are a nonprofit or charitable organization, your use of an
> NC-licensed work could still run afoul of the NC restriction, and **if you are a for-profit
> entity, your use of an NC-licensed work does not necessarily mean you have violated the term.
> Whether a use is commercial will depend on the specifics of the situation and the intentions of
> the user.** … **CC cannot advise you on what is and is not commercial use. If you are unsure, you
> should either contact the rights holder for clarification, or search for works that permit
> commercial uses.**"

**CC on NC-licensed data specifically** (same FAQ, "Data" section) — CC criticising the very choice
Coin Metrics made:

> "Sui generis database rights prevent copying and reusing of substantial parts of a database …
> **CC does not recommend use of its NonCommercial (NC) or NoDerivatives (ND) licenses on databases
> intended for scholarly or scientific use.**"

> "When a CC license is applied to a database … The license terms and conditions apply to the
> database structure (its selection and arrangement, **to the extent copyrightable**), its contents
> (**if copyrightable**), and in those instances where the database maker has **sui generis database
> rights** then the rights that are granted those makers."

**CC's 2008/2009 empirical study** (`https://wiki.creativecommons.org/wiki/Defining_Noncommercial`):
both creators and users "generally consider uses that earn users money … to be commercial", and
uses by for-profit companies are "typically considered more commercial". CC itself cautions the
study is "not intended to serve as CC's official interpretation."

## 3.3 APPLYING IT — the honest two-sided read

**The strongest case FOR the desk (stated fairly, not strawmanned):**
1. CC is explicit that being a for-profit is not disqualifying — "**turns on the use, not the
   identity of the reuser**."
2. The desk **redistributes nothing, publishes nothing, sells nothing, advises no one.** No
   Share/adaptation is made public, so the CC §3 attribution obligations (which attach on Sharing)
   are not even triggered.
3. Under **US law the raw numbers are probably not protected by copyright at all** (facts are
   uncopyrightable; the US has **no sui generis database right**, unlike the EU). CC's own FAQ
   concedes the licence reaches contents only "**if copyrightable**."
4. A CC licence's NC term restricts *copyright* acts. Merely *reading a number and acting on it* is
   arguably not a copyright act.

**Why that case FAILS anyway — four independent reasons, in order of force:**

**(i) The test is disjunctive, and the desk's purpose sits on the wrong side of BOTH limbs.**
"Not primarily intended for or directed towards **commercial advantage OR monetary compensation**."
The "primarily" qualifier is a shield for uses that are *incidentally* commercial. Here, generating
a trading signal that allocates real capital has **no purpose other than monetary gain** — it is
not primarily commercial, it is *exclusively* commercial. There is no available reading of §4.1 on
which "trade real capital with it" is NonCommercial. **This is not a gray-area case; the desk should
not talk itself into believing it is one.** The genuinely gray version of this question is the Upbit
card's — a licence that *affirmatively permits* "developing one's own strategy and backtesting."
CM's licence contains **no such permission**, which is exactly what makes the two cards different
and why they should NOT be ruled on identically.

**(ii) CM did not merely adopt CC BY-NC — it added a gloss that closes the "but it's internal"
door by name.** ToU §4.1 grants use "**solely for non-commercial internal business purposes**".
CM plainly contemplated *internal business* use and still wrote *non-commercial* in front of it.
So the desk's central argument — "it's purely internal, we distribute nothing" — is the precise
argument §4.1 pre-empts. *(Nuance, stated because it cuts the other way and the principal deserves
it: CC's guide says such glosses "never form part of the CC license." True — but that is about the
copyright licence. The gloss still operates as an ordinary **contract term**, and ToU §1 says
"**BY ACCESSING SERVICES, YOU AGREE TO BE BOUND**." So the desk faces both: a copyright licence and
a contract. CC's "facts aren't copyrightable" escape hatch may defeat the first and leave the
second entirely intact.)*

**(iii) `CapMVRVCur` is the vendor's curated product, not a raw fact.** Realized cap / MVRV is not
an observable on the blockchain — it is a **constructed metric with methodology choices**, and it
was introduced by Coin Metrics itself (Nic Carter / Antoine Le Calvez, 2018). Of everything in the
Community feed, the MVRV series is the single **weakest** candidate for "this is just an
uncopyrightable fact." The "facts are free" argument is strong for `PriceUSD` and weak-to-absent
for `CapMVRVCur`. This is exactly why §4's answer is *reconstruct from chain*, not *the numbers are
free so keep the file*.

**(iv) §6(iii) bites independently and is not an NC question at all.** The AI-System ban
(§1.3 above) prohibits using the Services to "**INPUT INTO, DEVELOP, TRAIN, IMPROVE, GENERATE OUTPUT
FROM, OR OTHERWISE USE IN RELATION TO, ANY AI SYSTEM**", where AI System includes "**MACHINE
MODELS**". **A favourable NC ruling would not clear this.** Any fitted/learned signal model on CM
Community data is exposed under §6(iii) regardless of how the commercial question resolves.

## 3.4 ⚠️ THE UNCOMFORTABLE PART — RESEARCH-ONLY IS NOT AS CLEAN AS THE DESK HAS BEEN ASSUMING

`data_axis_watchlist.md` card 7 states the interim scope as *"internal research/verification/diff
use by a private desk that redistributes nothing — the defensible interim scope."* That is the
**most** defensible scope available, and it is not nothing. But the desk should stop describing it
as clean, for a reason it has not yet written down:

**The NC test is about PRIMARY PURPOSE, and a prop desk's research has exactly one purpose.**
Alpha research at a proprietary trading firm is not scholarship that happens to occur inside a
company; it is **instrumentally directed toward commercial advantage** — that is its entire
justification and budget line. On CC's own intent-based test, "we only used it to *look for* a way
to make money" is a weaker distinction than it feels like.

Where research-only genuinely does hold up better:
- **Verification / diffing** (using CM as a ground-truth cross-check on the desk's *own*
  independently-collected series) is materially more defensible than **signal generation**. Its
  purpose is data-quality assurance, and it is the classic "reference/comparison" use.
- The **published negative result** — the desk measured this metric class FLAT (all four
  constructions SCREEN-WEAK; `cm_mvrv_btc_daily_level` graveyarded as TIMING-ARTIFACT) — is
  closer to research in the ordinary sense than to commercial exploitation.

**Grading honestly: production = RED. Signal-hunting research = AMBER. Verification/diff = AMBER-GREEN.**
None of them is GREEN.

## 3.5 THE ACQUISITION MAKES THIS WORSE, NOT BETTER

A tempting (wrong) reading is: "the terms page is gone, so no terms bind us." Reject it explicitly.

- **Removal of a terms page is not a grant of rights.** It is the *opposite* of a permission: the
  desk now cannot even read its obligations on the live web. §13-style discipline treats
  "unreadable licence" as *unresolved*, never as *permitted* — this is precisely the standard the
  desk already applied to bitFlyer (card 3: *"nothing prohibits use, nothing permits it"* → no
  recorder started). **Same standard, same outcome, applied consistently.**
- **The counterparty has changed.** Rights sit with an acquirer whose own business is an
  order/execution management platform sold to trading firms. A commercial-use claim against a
  trading desk is *more* commercially interesting to Talos than it was to a data vendor, not less.
- **Silent-repricing risk is now live and unhedged.** The GitHub feed already stopped (2026-05-24).
  A free community tier is the most natural thing to retire post-acquisition. Any production signal
  wired to `api.coinmetrics.io/v4` community endpoints carries an **un-notified single-vendor
  shutdown risk on top of the licence risk** — and the desk holds no contract entitling it to
  notice. That is a dependency argument for reconstruction even if the licence question vanished.

## 3.6 ✅ RECOMMENDED RULING

> ### **EXCLUDE** — for any use on a path that leads to trading real capital.
> ### **RESEARCH-ONLY, WINDING DOWN** — for what has already been done, with verification/diff as the only scope that should continue, and only until a reconstruction lands.

**Confidence: HIGH on the production half** (§3.3(i)–(ii) — a licence granting rights "solely for
non-commercial internal business purposes" cannot be read to permit generating money-making trading
signals). **MODERATE on the research half** — genuinely arguable, and deliberately not
self-approved.

**Operationally, what this means:**
1. **Do NOT wire any CM Community series into a production signal, ever, under the current licence.**
   Answering the blocking question directly: the 15-year keyless daily backfill axis **must not be
   built on Coin Metrics Community data**.
2. **`data/coinmetrics_flows.jsonl` (9,866 rows) — quarantine, do not delete.** It is evidence for
   the completed screen and for reproducibility. Recommend a `licence_quarantine` flag and no
   production read path. *(Not touched by this agent — freeze.)*
3. **The desk keeps its deliverable.** The negative result — *the aggregate exchange-flow /
   MVRV metric class carries no daily-horizon edge over 15 years* — is the **desk's own measurement
   and its own conclusion**, not Coin Metrics content. **It survives an EXCLUDE ruling intact.**
   That $799/mo × 2 question stays answered at $0. The licence problem costs the desk a *data feed*,
   not its *findings*.
4. **Do NOT generalise this ruling to Upbit (GAP_REGISTER #67's other half).** They were routed as
   one ruling session; they are **not the same question**. Upbit's guide *expressly permits*
   "developing one's own strategy and backtesting"; CM's licence expressly permits only
   "non-commercial internal business purposes". **Upbit is genuinely on the line; Coin Metrics is
   over it.** Recommend splitting #67 into two rows.

**TWO UNBLOCKING ROUTES, in priority order:**

- **ROUTE A (the real one) — RECONSTRUCT.** See §4. Facts aren't copyrightable and MVRV is
  computable from public chain data. This removes the licence question rather than litigating it,
  and simultaneously kills the vendor-shutdown dependency in §3.5.
- **ROUTE B (cheap, one email, run it in parallel) — ASK.** This is **Creative Commons' own
  recommended step** ("contact the rights holder for clarification"), and CC notes NC licences are
  non-exclusive so the licensor *can* simply grant more. A single email to
  `info@coinmetrics.io` (or the Talos data team) asking whether internal, non-redistributed use of
  Community data by a proprietary trading firm is permitted, and whether §6(iii) reaches statistical
  models, is **zero-risk, legitimacy-positive, and could close this permanently in one reply.**
  A written "yes" converts EXCLUDE → ADOPT. A "no" or silence costs nothing and confirms Route A.
  **This is a human action item — an agent must not send it.**

**What is NOT recommended, explicitly:** no scraping around the terms, no arguing the redirect
voided the ToU, no "the data is public so it's free", no VPN/rate-limit evasion (§7 bars it by
name), no re-hosting. The legitimacy gate holds.

---

# §4 — THE FREE-FRONTIER FOLLOW-THROUGH: RECONSTRUCTING REALIZED CAP / MVRV

## 4.0 WHY RECONSTRUCTION IS THE RIGHT MOVE, AND WHY IT IS LEGITIMATE

> **THE DESK'S OWN CHARTER ALREADY DECIDED THIS. `docs/DIGGING_CHARTER.md` §13, verbatim:**
> *"Raw **FACTS** a vendor merely repackages (on-chain, exchange APIs) are **free to collect
> directly** (facts are not copyrightable; the vendor's curated product is) **-> reconstruct**."*
>
> and, on why an EXCLUDE ruling costs nothing to take now rather than later:
> *"a signal built on data the desk has no right to use is **UN-DEPLOYABLE** at live/commercial
> scale — it must be ripped out later, **so it is worthless now**."*
>
> §13 also requires: *"Adopt ONLY sources with a **clear permitted-usage license**."* CM Community's
> licence is clear — and what it clearly permits is *non-commercial* use. It therefore **fails §13
> for the production purpose and passes it only for a non-commercial one.** The ruling in §3 is not
> a new policy; it is §13 applied to a document run 1 had not yet read.

The ruling in §3 costs the desk a *feed*, not a *capability* — provided the metric can be rebuilt
from unencumbered inputs. The legal frame, stated plainly so the principal can check it:

1. **Facts are not copyrightable.** MVRV on any given day is a number about the Bitcoin ledger.
   Under US law (*Feist*), facts carry no copyright, and the US has **no sui generis database
   right**. CC's own FAQ concedes the licence reaches database contents only "**if copyrightable**."
2. **Methods and formulas are not copyrightable either** (idea/expression; 17 USC 102(b)). A
   published methodology can be re-implemented. **The desk has already ruled this way once and
   acted on it** — `data_axis_watchlist.md` card 8: Kaiko's benchmark rulebook was read from the
   public page and the VWM+TWAP rule **re-implemented** in
   `scripts/reconstruct_kaiko_reference_rate.py`, with the explicit note *"nothing rehosted … the
   rule was read from the public page and re-implemented."* **§4 here is the same manoeuvre applied
   to MVRV.** Ruling consistently across the two cards matters more than either individual answer.
3. **What is NOT clean, and must not be done:** copying CM's *series* and calling it reconstructed;
   using CM's numbers to fit/calibrate the reimplementation; or using CM's series as the training
   target. The reconstruction must be **input-independent** of Coin Metrics.
4. **The one legitimate residual use of CM: none.** Even the tempting "use CM only to *validate* the
   reconstruction" is contaminated under a strict reading — and the desk does not need it. Validate
   against a *different* free source (see the candidate table) or against internal consistency.
   **Stated explicitly so nobody re-imports the dependency through the back door**, which is exactly
   the fuzzy-credit laundering failure mode card 1 already names.

## 4.1 THE SPECIFIC HOLE TO FILL (measured, not assumed)

Confirmed by reading the desk's own artifacts this run:

- `data/coinmetrics_flows.jsonl` — 9,866 rows, fields
  `asset, date, flow_in_ntv, flow_out_ntv, netflow_ntv, sply_ex_ntv, price_usd`; first record
  `btc 2010-07-18 … price_usd 0.08584`.
- **`grep` across every `data/*.jsonl`: this is the ONLY file on the desk carrying any date before
  2015.** So an EXCLUDE ruling does not just cost the MVRV axis — **it costs the desk its sole
  pre-2015 BTC price history.** That was not previously written down anywhere and it materially
  raises the value of finding a clean deep price series.
- **Blast radius is small and contained:** `grep -rl coinmetrics scripts/ libs/` returns exactly
  **one** file, `scripts/collect_coinmetrics_flows.py`. Nothing in `libs/` imports it; no executor
  or risk path touches it. A quarantine is a one-file change, not a refactor.
- Note also that CM's `price_usd` is **CM Reference Rate** output — one of Coin Metrics' flagship
  *commercial* products. Of every field in the file it is the **least** defensible as "just a fact",
  and it is the field the desk is most quietly dependent on.

## 4.2 ✅ THE METHODOLOGY IS FULLY PUBLISHED BY THE VENDOR — WITH A WORKED EXAMPLE

**This is the single most actionable finding in §4.** The desk does not have to reverse-engineer
anything. Coin Metrics publishes the exact construction on a live, keyless docs page:
`https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/market/market-capitalization.md`
(200, 24,512 B). Verbatim:

**Realized Market Cap (USD) — `CapRealUSD`:**
> **Definition:** "The sum USD value based on the USD closing price on the day that a native unit
> last moved (i.e., last transacted) for all native units."
>
> **Details:** "This metric takes the ledger state of the asset, assigns a date of last movement for
> each account/unspent output, multiplies the balance of the account/value of the output by the
> price at the date of last movement and sums all of those numbers for the asset's ledger."
> · "The state of the ledger is the one at the last available block for that day."
> · "Only the native units balance is considered, L2 tokens (ERC-20, etc.) are not taken into account."
> · "**For UTXO chains, last activity is the date of creation of the output.**"
> · "For account-based chains, last activity is either the last date the account was the sender of a
> ledger change, or its time of creation, whichever is more recent."
>
> **And CM even publishes a worked example:**
> | Account | Balance | Time of last movement | Price at last movement | Realized balance |
> |---|---|---|---|---|
> | A | 100 | 2010-01-01 | $0 | $0 |
> | B | 1000 | 2016-01-01 | $10 | $10,000 |
> | C | 500 | 2019-01-01 | $100 | $50,000 |
> "The realized cap would be $0 + $10,000 + $50,000 = $60,000"

**MVRV — `CapMVRVCur`:**
> **Definition:** "The ratio of the sum USD value of the current supply to the sum 'realized' USD
> value of the current supply." · **Details:** "**Computed as CapMrktCurUSD / CapRealUSD**"

**Why this matters:** a **published spec + a worked numeric example** is the strongest possible
position for a clean-room reimplementation. It removes the two things that usually make vendor
replacement fail — ambiguity about the convention, and no way to unit-test. The desk can now write
`realized_cap()` and **assert it reproduces $60,000 on CM's own published toy ledger**, using zero
Coin Metrics data. That is a legitimate spec-conformance test, not data copying.

**SELF-CORRECTION (§3.3(iii) refined, flagged rather than quietly patched):** I wrote earlier that
MVRV "was introduced by Coin Metrics itself." **The vendor's own docs say otherwise** and the
distinction matters:
- **Realized cap** — a Coin Metrics origination (Nic Carter / Antoine Le Calvez, 2018); CM's docs
  link `https://coinmetrics.io/realized-capitalization/` (now redirected).
- **MVRV, the ratio** — CM's docs credit *"Conceptualized by **Adaptive Capital**"*, linking
  `https://medium.com/adaptivecapital/bitcoin-market-value-to-realized-value-mvrv-ratio-3ebc914dbaee`
  (i.e. David Puell / Murad Mahmudov, 2018) — **not** Coin Metrics.

So the *ratio* is a third party's published idea and the *ingredient* is a published CM
methodology. Either way both are **ideas/methods, not protected expression** — but the correction
strengthens the reconstruction case rather than weakening it, and the earlier overstatement should
not stand in a document a principal will rely on.

**Bonus discovered on the same page:** CM also documents `Capitalization, realized, USD, **age
bands**` — i.e. realized cap split by coin age. If the desk ever builds the UTXO pipeline, age-band
cost basis (the HODL-waves / STH-LTH cost-basis family) falls out of the *same* index for free.
That is a materially larger axis than the single MVRV series that was screened.

## 4.3 NON-ENGLISH FRONTIER (charter §28 FOREIGN FRONTIER) — SEARCHED, HONEST NULL

CN-language search run (`比特币 已实现市值 MVRV 数据 开源 免费 API 历史数据`). **No free,
cleanly-licensed Chinese-language realized-cap/MVRV source or reconstruction was found.** Every
CN-side result routes back to the same Western vendors or to price-only data:
- `coinglass.com/zh/pro/i/mvrv-ratio` and `.../bitcoin-mvrv-zscore` — vendor charts, no licence
  grant, no bulk export.
- `cryptoquant.com/asset/btc/chart/market-indicator/mvrv-ratio` — the very vendor being replaced.
- `bitget.com/price/bitcoin/historical-data` — **price only**, not realized cap.
- TradingView Pine scripts (e.g. `/script/259f1BXU-MVRV-Ratio-Momentum`) — the *script* is
  open-source, but it consumes a **vendor-supplied MVRV feed** inside TradingView. Open code over
  closed data is not a data source. **Do not mistake an open indicator for an open dataset** — this
  is the same trap as the earlier "Dune replicates CryptoQuant" claim that graded UNVERIFIED.

**Logged as a documented search that failed (§28 requires evidence, not a shrug): the CN ecosystem
does not carry an independent realized-cap reconstruction.** Retry next cycle with UTXO-specific
native terms (`UTXO 成本基础`, `链上 成本基准`) rather than the metric's marketing name.

## 4.4 HOSTED / API / DATASET CANDIDATES — ALL OPENED, ALL GRADED

**Headline: no hosted source is simultaneously (free) AND (cleanly licensed) AND (full history).
Every single candidate fails at least one axis.** That is the honest answer, and it is what makes
§4.5's reconstruction path the recommendation rather than a fallback.

| # | Source | Realized cap / MVRV? | History depth (verified) | Licence | Key? | Grade |
|---|---|---|---|---|---|---|
| 1 | **Blockchain.com charts API** | **NO** — `market-cap`/`market-price` yes, `mvrv` **404** on API (rendered on site only) | mkt cap **2009-01-03 → 2026-07-24**, full | ⛔ **hostile** | keyless in practice | **EXCLUDE** |
| 2 | **Blockchair bulk dumps** `gz.blockchair.com` | **substrate — `value_usd` IS per-UTXO cost basis** | **2009-01-03 → 2026-07-25**, 6,408 daily files | ⚠️ **UNSTATED** | keyless but **10 kB/s throttle** | **BEST SUBSTRATE, licence must be obtained** |
| 3 | **Glassnode** | yes (product) | ⛔ **4 years even on the $49 Advanced tier** | proprietary | pay | **EXCLUDE — no free tier exists** |
| 4 | **bitcoin-data.com** (BGeometrics) | **YES** — `mvrv`, `realized-cap`, `realized-price` keyless | ⛔ **hard 4-year rolling window** (1,461 rows, 2022-07-26 →) | restrictive | free tier **15 req/day** | **sanity-check only** |
| 5 | **Checkonchain** | **YES** — `Price`, `Realised Price`, `MVRV` | ✅ **6,415 pts, 2009-01-01 → 2026-07-25** | ⛔ **NONE — all rights reserved** | none | **EXCLUDE without written licence** |
| 6 | **Bitbo charts/API** | yes (+ LTH/STH realized price, cost-basis heatmap) | n/a | ⛔ none stated | **API key required**, 428 bot-wall | **EXCLUDE** |
| 7 | **Look Into Bitcoin** | — | — | — | — | **DEAD** — 301 → `bitcoinmagazinepro.com` (commercial); API 404 |
| 8 | **mempool.space** | **NO** — no such endpoint class exists | — | — | keyless | **not a candidate** |
| 9 | **HuggingFace** | **NO** | — | — | — | **ZERO relevant datasets** (see below) |
| 10 | **Kaggle** | **NO** (best has NUPL, not realized cap) | 2023 stale | CC BY 4.0 / Apache / CC0 | — | **EXCLUDE — provenance-tainted** |
| 11 | **CM GitHub CSV** | MVRV yes | 2010-07-18 → 2026-05-23 | ⛔ **identical CC BY-NC 4.0** | none | **no loophole** |

### The three that deserve detail

**② Blockchair bulk dumps — the real find of §4.** `https://gz.blockchair.com/bitcoin/outputs/`
(200) serves **6,408 daily TSVs, `..._20090103.tsv.gz` → `..._20260725.tsv.gz`**. Schema:
`block_id, transaction_hash, index, time, value, value_usd, recipient, type, script_hex,
is_from_coinbase, is_spendable`. **`value_usd` is the USD value at output-creation time — i.e. the
cost basis of that UTXO, precomputed.** Realized cap at date *T* = Σ `value_usd` over outputs
created ≤ *T* and not yet spent (join `outputs/` against `inputs/`). That is CM's published
definition (§4.2) almost verbatim, and it collapses the hardest part of the reconstruction.
**TWO REAL BLOCKERS, both stated honestly:**
- `https://gz.blockchair.com/README.html` (200): *"Note that by default the speed is limited to
  **10 kB/s**. You'd need a special key to download without this limit."* Measured **2,241 B/s** on
  a real download. The full BTC outputs corpus is hundreds of GB — **infeasible at throttled speed.**
- **Licence UNSTATED.** `blockchair.com/api/docs`, `/dumps`, `/api/plans` all **401** (bot-walled)
  to plain curl, browser-UA curl, and WebFetch alike. **No circumvention was attempted.** So this
  repeats the bitFlyer pattern exactly: *nothing prohibits, nothing permits* ⇒ **not adoptable
  today.** Unblocking step is one email to `info@blockchair.com` for (a) the licence in writing and
  (b) unthrottled access.

**⑤ Checkonchain — the painful near-miss.** `https://charts-cdn.checkonchain.com/btconchain/
unrealised/mvrv_all/mvrv_all_light.html` (200, 2,380,707 B) embeds a Plotly payload whose traces
include `Price`, `Realised Price`, `MVRV` at **6,415 daily points, 2009-01-01 → 2026-07-25**. It is
exactly the series the desk wants, at exactly the depth it wants, keyless. **And it carries no
licence whatsoever** — `checkonchain.com` shows only *"Copyright © 2024 _checkonchain"*. Default is
all-rights-reserved. **Scraping an unlicensed chart payload for commercial signal generation is
strictly worse than the CM position the desk is trying to escape** (CM at least *grants* something).
**Logged as EXCLUDE, and specifically as a temptation to be refused, not a lead to follow.**

**⑩ Kaggle — and the licence-laundering trap worth adding to the operator library.**
`https://www.kaggle.com/datasets/aleexharris/bitcoin-network-on-chain-blockchain-data` is tagged
**CC BY 4.0** and carries NUPL (from which realized cap is recoverable via
`RealizedCap = MarketCap × (1 − NUPL)`). Tempting. **But its own description names its sources as
"Blockchain.com" and "LookIntoBitcoin.com"** — one of which forbids copying/caching its content and
the other of which is now a paid product. **A permissive licence tag applied by a re-uploader does
not launder the upstream terms; you cannot grant rights you never held.** Also 3 years stale
(2023-09-03). **This is a generalisable rule the desk should carry: on any community data lake,
grade the UPSTREAM provenance, never the uploader's licence dropdown.**

### Negative results, stated plainly (§28 requires evidence, not a shrug)
- **HuggingFace: searched `mvrv`, `realized+cap`, `bitcoin+realized`, `bitcoin+onchain`,
  `coin+metrics`, `bitcoin`, `blockchain` via the keyless dataset API. ZERO datasets carrying
  realized cap or MVRV.** Not "few" — zero.
- **Blockchain.com is disqualified by its terms even for the price leg.**
  `https://www.blockchain.com/legal/api-terms` (200): *"You shall not commercialize (i.e., sell,
  rent, or lease), **copy, store or cache** the Blockchain Content, other than for the purposes
  allowed by this Agreement"* and *"nor use any alternative means such as **robots, spiders,
  scraping**…"*. Building a local history table is plainly "store or cache". **This kills what
  looked like the obvious free 2009→now price series** — an important negative, because that price
  series is the desk's other exposure (§4.1).
- **Glassnode has no free tier at all**, and `https://studio.glassnode.com/pricing` caps history at
  **"4 Years"** even on the paid Advanced tier. The long-standing desk assumption that Glassnode
  free could serve as a diff target is **refuted**.

### One more nail in §2's coffin — the repo's README says it out loud
`https://raw.githubusercontent.com/coinmetrics/data/master/README.md`:
> "These data archives are produced using **free Community tier** of Coin Metrics API."

So the GitHub CSVs are not an independent product with independent terms — they are **CM's own
Community-tier output, republished by CM under the same CC BY-NC 4.0.** Confirms §2.2: *there is no
looser surface to switch to.* (Also worth recording: **the free CSV has no `CapRealUSD` column at
all** — MVRV is served but realized cap must be backed out as `CapMrktCurUSD / CapMVRVCur`.
`CapMVRVCur` = 5,789 non-empty rows, 2010-07-18 → 2026-05-23.)

> **VERIFY-DON'T-TRUST APPLIED TO THIS RUN'S OWN SUB-SEARCHES.** The §4.4 sweep was fanned out to
> parallel research agents; their output is a **secondary source** until re-opened. The two
> load-bearing *negative* quotes — the ones actually doing work in the recommendation — were
> **independently re-fetched and confirmed byte-for-byte** by this author:
> - `https://www.blockchain.com/legal/api-terms` (200, 1,169,004 B) — "*You shall not commercialize
>   (i.e., sell, rent, or lease), copy, store or cache the Blockchain Content…*" and "*nor use any
>   alternative means such as robots, spiders, scraping or other technology to access, query, or use
>   www.blockchain.com…*" — **both present, verbatim, confirmed.**
> - `https://gz.blockchair.com/README.html` (200) — "*Note that by default the speed is limited to
>   **10 kB/s**. You'd need a special key to download without this limit, if you don't have one,
>   please reach us at info@blockchair.com*" — **confirmed verbatim**, including the documented
>   `?key=SECRETKEY` unthrottling mechanism.
>
> **One honest qualification on Blockchain.com that the sweep did not draw out:** the "store or
> cache" language sits inside the **API Program** agreement, whose surrounding text contemplates a
> participant *issued a key* ("We will provide to you a key…"). A narrow reading is that it binds
> API Program participants rather than anonymous chart-endpoint callers. **The desk should still
> treat it as restrictive** — the same document's *General License Conditions and Restrictions* bar
> scraping `www.blockchain.com` by "*robots, spiders, scraping or other technology*" in general
> terms, and betting a production dependency on the narrow reading is exactly the risk §13 exists to
> avoid. **Graded EXCLUDE, with the ambiguity recorded rather than resolved in the desk's favour.**

## 4.5 THE RECONSTRUCTION PATH — VIABLE, AND CHEAPER THAN EXPECTED

### 4.5.1 The algorithm telescopes — no UTXO set required

The reason this looked hard is a false assumption (that you must materialise the UTXO set at every
date). You don't. Realized cap decomposes into two daily aggregates plus a running sum:

```
created_usd(d)   = Σ over outputs CREATED on day d of  value · P(d)
destroyed_usd(d) = Σ over outputs SPENT   on day d of  value · P(creation_day_of_that_output)
RealizedCap(D)   = Σ_{d ≤ D} [ created_usd(d) − destroyed_usd(d) ]
MVRV(D)          = MarketCap(D) / RealizedCap(D)
RealizedPrice(D) = RealizedCap(D) / CirculatingSupply(D)
```

Both aggregates fall out of one self-join `(spent_transaction_hash, spent_output_index) →
(transaction_hash, index)`. **This is O(n) streaming, not O(UTXO-set) stateful** — which is why the
job is roughly a week of engineering, not a quarter.

### 4.5.2 Substrate — graded

| Substrate | Coverage (verified) | Has creation↔spend linkage? | Licence | Access | Grade |
|---|---|---|---|---|---|
| **AWS Public Blockchain** `s3://aws-public-blockchain/v1.0/btc/` | **2009-01-03 (genesis) → 2026-07-26** | ✅ `inputs[].spent_transaction_hash/_output_index`, `outputs[].value/index`, `block_timestamp` | ✅ **MIT-0 — see correction below** | keyless `--no-sign-request` | ✅ **PRIMARY** |
| **BigQuery** `bigquery-public-data.crypto_bitcoin` | genesis → now, 24h refresh | ✅ `spent_transaction_hash` confirmed | ⚠️ **no explicit licence found** — only an "AS IS" disclaimer | GCP account + billing; 1 TB/mo free then $6.25/TB | ✅ **best PROTOTYPE** |
| **Blockchair dumps** | 2009-01-03 → 2026-07-25 | ✅ **pre-joined** — `inputs` ships creation `value_usd` AND `spending_*` on one row, plus `lifespan`, `cdd` | ⚠️ **UNSTATED** (401 bot-wall) | keyless but **10 kB/s** | ⚠️ **fastest IF licensed** |

> **🔴 REGISTRY CORRECTION — `data/data_universe_map.json` IS WRONG ABOUT THE AWS LICENCE, IN THE
> DESK'S FAVOUR.** The map currently records: *"license: Apache 2.0 per AWS's open-data-registry
> github repo; usage requires citation 'AWS Public Blockchain Data was accessed on [DATE]' +
> registry URL."* **Both halves are wrong.** Verified independently this run: the registry YAML
> `https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets/aws-public-blockchain.yaml`
> (200) has exactly one licence field — `License: https://github.com/aws-samples/digital-assets-examples/blob/main/LICENSE`
> — and that file (200) reads:
> > "Permission is hereby granted, free of charge, to any person obtaining a copy of this software
> > and associated documentation files (the 'Software'), to deal in the Software **without
> > restriction**, including without limitation the rights to use, copy, modify, merge, publish,
> > distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
> > Software is furnished to do so."
>
> Note what is **absent**: the "subject to the following conditions… include the above copyright
> notice" clause present in standard MIT. This is **MIT-0 (MIT No Attribution)** — *more* permissive
> than the desk believed, **with no citation obligation**. **Honest caveat that must travel with
> this: it is a SOFTWARE licence pointed at a DATASET**, which is a genuine ambiguity. Mitigant:
> the payload is raw blockchain facts, the thinnest possible copyright surface. Worth a short
> counsel check; not a blocker. **This correction is applied to the map in this run.**

### 4.5.3 Open-source implementations — HONEST NEGATIVE

**There is no maintained, permissively-licensed, working from-UTXO realized-cap implementation on
GitHub.** Searched via the GitHub repo-search API (code search returned 401 — unauthenticated code
search is not available, and no token was used). Everything found is (a) a vendor scraper,
(b) unlicensed hobby code, or (c) infrastructure that stops short of the price join:

| Repo | Licence | Computes realized cap from UTXO? | Last commit |
|---|---|---|---|
| `github.com/citp/BlockSci` | GPL-3.0 | No — substrate only (C++ UTXO engine) | 2021-12-13 (stale) |
| `github.com/blockchain-etl/bitcoin-etl` | MIT | No — extraction only (**this is what generates BigQuery's tables**) | 2025-05-02 |
| `github.com/in3rsha/bitcoin-utxo-dump` | MIT | No — *current* chainstate only, no history, no prices | 2025-05-12 |
| `github.com/SciEcon/UTXO` | GPL-3.0 | Partial — UTXO **age** cohorts from BigQuery; **zero** `usd`/`price`/`realized` hits | 2022-05-05 |
| `github.com/Tsunekazu/checkonchain` | ISC | No — **pulls from Coin Metrics** | 2019-10-15 (abandoned) |
| `github.com/dhruvan2006/chaindl` | MIT | **No — it is a vendor scraper** (CheckOnChain, Glassnode Studio, Dune, Bitbo…) | 2026-03-31 |
| `github.com/mohitbhbundey/Bitcoin_MVRV_Ratio_System` | **none** ⇒ all rights reserved | claims to; 0★, unvetted | 2025-07-31 |

⚠️ **`chaindl` is the trap of this section, and it is the same trap as the Kaggle one:** MIT-licensed
*code* that scrapes Glassnode/Dune/CheckOnChain. **An MIT licence on a scraper does not launder the
ToS on the scraped data.** Generalised rule for the operator library: **on any "free data" repo,
grade the DATA's upstream terms, never the CODE's licence badge.**

**Why no good implementation exists** — worth stating, because it reframes the effort estimate:
it is not that the problem is hard. It is that **everyone who wanted this number just paid
Glassnode.** The desk is not swimming against a technical current, only a commercial habit.

### 4.5.4 Academic — one genuinely usable asset, and it stops short of the price leg

**Liu, Zhang & Zhao (2022), "Deciphering Bitcoin Blockchain Data by Cohort Analysis", *Scientific
Data* 9:136** — `https://www.nature.com/articles/s41597-022-01254-0` (303 to IdP; metadata via
`https://api.crossref.org/works/10.1038/s41597-022-01254-0`, 200).
- **Article licence: CC BY 4.0 — commercially usable.**
- **Code:** `github.com/SciEcon/UTXO`, GPL-3.0 — a *validated BigQuery query pattern* over
  `crypto_bitcoin.{inputs,outputs}` using `spent_transaction_hash`. Useful scaffolding.
- **Data:** Harvard Dataverse `doi:10.7910/DVN/XSZQWP`, 16 files, **2009-01-03 → 2021-02-10 daily
  (n=4,421)**. Terms, verbatim from the Dataverse export API: *"CC BY — … **The license allows for
  commercial use.**"*
- ⚠️ **Limitation: UTXO AGE COHORTS ONLY — no price leg, hence no realized cap.** It hands the desk
  the scaffolding under a commercially-clean licence; the desk supplies the price join.

`arXiv:2512.07886` reconstructs realized cap **backwards** from a vendor MVRV × market cap — i.e.
the exact circular dependency this section exists to break. **Cite as prior art for the shortcut,
never as a reconstruction.** No SSRN/ScienceDirect paper found that rebuilds realized cap from
UTXOs with released code — **honest negative.**

**Dune:** public queries exist (`dune.com/queries/1936502` "Bitcoin : Realized Price";
`.../3979995` "URPD v1") but both **403** to direct fetch and render the SQL only via an
authenticated XHR. **The SQL is not readable without an account. No circumvention attempted.**
A free registration is a legitimate route a human can take. Note also that Dune's Bitcoin tables are
themselves a curated product with their own ToS — read the method, do not depend on the pipeline.
(This also independently re-confirms card 7's earlier finding that the Dune path is key-gated.)

### 4.5.5 ⚠️ THE PRICE LEG — MY TWO SUB-SEARCHES CONTRADICTED EACH OTHER. RESOLVING IT EXPLICITLY.

**The conflict:** the reconstruction sweep recommended **Blockchain.com `market-price`** as the
primary price leg (6,413 gap-free daily points, 2009-01-03 → 2026-07-25, keyless, verified spacing
histogram: 6,412 of 6,412 gaps = exactly 1 day). The hosted-source sweep independently found that
**Blockchain.com's own API terms forbid exactly that use** — *"You shall not commercialize …, copy,
**store or cache** the Blockchain Content"*. I re-fetched the terms myself and **confirmed the
restriction is real** (§4.4 verification box).

**RESOLUTION: the licence finding wins. Blockchain.com is NOT the price leg.** A production price
table is a cache by any ordinary reading, and the whole point of §4 is to stop depending on data the
desk has no clear right to use. Adopting Blockchain.com would swap a CC BY-NC problem for a
"shall not store or cache" problem — **no improvement, and a self-inflicted one.**
*(Recording the disagreement rather than silently picking a winner: two independent searches
reaching opposite conclusions is exactly the signal that a claim needed adjudication, and the one
that looked at the licence was right.)*

**What the price leg actually needs — the requirement is smaller than it looks.** Per CM's own
published convention, coins that last moved before price discovery are valued at **$0**. So the
series only needs to start at **first price ≈ 2010-07-17**, not at genesis. Graded candidates:

| Price source | Depth (verified) | Licence | Key? | Verdict |
|---|---|---|---|---|
| Blockchain.com `market-price` | 2009-01-03 → 2026-07-25, gap-free daily | ⛔ **"shall not … copy, store or cache"** | no | **REJECTED** (see above) |
| **Bitcoinity** `data.bitcoinity.org/export_data.csv` | **5,854 rows, 2010-07-17 → 2026-07-25**, per-venue columns (bitstamp/coinbase/kraken/bitfinex/cex.io/others) | ⚠️ **UNSTATED** — `/about` is **404**; footer only "(c) 2011 Bitcoinity.org" | no | ⚠️ depth is perfect, licence unread |
| **Bitstamp public API** | **2011-08-29 → now** daily OHLCV | exchange-native ToS (desk already has a posture on these) | no | ✅ **cleanest** |
| Coinbase Exchange API | ~2016-01 → now | exchange-native | no | ✅ clean, too shallow alone |
| mempool.space historical-price | 2010-07-19 → now BUT **WEEKLY (168h) for 2010–2022** | code AGPL-3.0; data terms unstated | no | ⛔ **too coarse — unusable as the daily leg** |
| CoinGecko | free tier now caps at **365 d** | — | demo key for full history | ⛔ |
| bitcoincharts | **DEAD** — `api.bitcoincharts.com` connection failed (HTTP 000) | — | — | ⛔ do not plan around it |

**🔴 RESIDUAL GAP, NAMED AND QUANTIFIED (§28 requires the honest negative):**
**2010-07-17 → 2011-08-29 (~13.5 months) has NO cleanly-licensed daily BTC price source that this
run could find.** Bitstamp — the cleanest source — starts 2011-08-29. Bitcoinity covers the window
but its licence is unread (terms page 404s). Blockchain.com covers it but is rejected on terms.
- **Impact is small but real:** it is the MtGox era, when total BTC value was a rounding error
  against today — but those coins are *exactly* the never-moved cohort that realized cap is most
  sensitive to. Mis-pricing them propagates forward permanently.
- **Mitigations, in order:** (a) email Bitcoinity's operator for a one-line licence statement (the
  site is a hobby project by a named individual — a "yes" is plausible); (b) MtGox-era archives via
  the desk's existing era-archaeology capability (§30); (c) **document the convention and set the
  window to $0**, which is only a mild extension of the convention every vendor already uses for
  pre-2010-07 coins. **(c) is deployable today and is the recommended default.**

### 4.5.6 GOTCHAS — the list that stops this from silently producing a wrong series

Ordered by how much damage they do if missed:

1. **Change outputs.** Spending 10 BTC to send 0.1 re-prices the whole 10 at today's price; the 9.9
   change is not an economic flow but realized cap counts it. **This is inherent to the metric, not
   a bug** — the original article concedes it. **Match the convention; do not "fix" it**, or the
   series will reconcile with nobody.
2. **Exchange-internal / hot-wallet consolidation** — same mechanism at industrial scale. Glassnode's
   "entity-adjusted" variants net these out with **proprietary heuristic address clustering**, which
   is *not* reproducible. **Target the unadjusted `CapRealUSD` definition** — it is the one that is
   actually specified in public.
3. **BIP30 duplicate coinbase txids** — blocks 91722/91880 and 91812/91842 contain coinbase txs with
   *identical txids* that overwrote their predecessors. **A naive txid-keyed join will mislink or
   double-count.** Classic silent-corruption bug; special-case it. *(This is precisely the
   "silent-zero-data" hazard class the charter's verify-don't-trust rule exists for.)*
4. **Genesis block's 50 BTC is unspendable** by protocol quirk and never enters the UTXO set; plus
   OP_RETURN / provably-unspendable outputs. Decide inclusion, document it — vendors differ.
5. **No price before ~2010-07-17** ⇒ ~1.7M BTC at $0 basis forever. **Feature, not bug** (§4.5.5).
6. **Price-convention sensitivity.** CM uses its own reference rate at daily close. Any other price
   source produces small but persistent divergence, worst in thin early history. **The desk will not
   match a vendor to the basis point and should not set that as the acceptance test.**
7. **Reorgs / chain tip** — trailing partitions can rewrite. Compute on data lagged ≥6 blocks.
8. **Blockchair's `value_usd` is Blockchair's price opinion**, silently baked in — convenient, but
   you inherit their convention *and* their unread ToS.

### 4.5.7 EFFORT AND SCALE — measured, not guessed

AWS `v1.0/btc/transactions/` daily Parquet, sampled: 2010-06 = 0.2 MB · 2012 = 74 MB · 2014 = 112 MB
· 2016 = 493 MB · 2018 = 398 MB · 2020 = 488 MB · 2022 = 572 MB · 2024 = 541 MB · 2026 = 584 MB
⇒ **≈2.0–2.2 TB snappy Parquet for full history.** But most of that is `script_hex`/`witness` blob:
**columnar projection to just `block_timestamp, outputs.value, outputs.index,
inputs.spent_transaction_hash, inputs.spent_output_index` cuts the actual read to ≈200–400 GB.**
Blocks are trivial (~50 KB/day).

**Estimate: ~1 week of competent engineering to a validated series.** Prototype on BigQuery (likely
inside the 1 TB/month free tier); productionise on AWS Parquet + DuckDB.

### 4.5.8 ✅ RECOMMENDED RECONSTRUCTION PLAN

1. **Prototype on BigQuery** `crypto_bitcoin` — hours, not days; validates the query shape cheaply.
   *(Requires a human to create a GCP account — an agent must not.)*
2. **Productionise on AWS Public Blockchain Parquet** (`s3://aws-public-blockchain/v1.0/btc/`,
   keyless `--no-sign-request`, **MIT-0**, genesis→today confirmed) + DuckDB.
3. **Price leg: Bitstamp public API from 2011-08-29**, with 2010-07-17 → 2011-08-29 set to $0 by
   documented convention until a licence for Bitcoinity is obtained. **Not Blockchain.com.**
4. **Unit-test against CM's published toy ledger** (§4.2 — the $60,000 worked example). This is a
   **spec-conformance test using no Coin Metrics data**, and it is the single cheapest correctness
   gate available.
5. **Two emails a human can send in five minutes**, both zero-risk: Blockchair
   (`info@blockchair.com`) for a speed key **and written commercial terms** — their pre-joined
   `inputs` dumps would reduce the whole job to a `GROUP BY`; and Bitcoinity's operator for a
   one-line price-data licence.
6. **Short counsel check** on two narrow points: "MIT-0 software licence applied to a dataset", and
   whether a one-off comparison against a CC BY-NC series counts as permitted verification.

> **AMENDMENT TO §4.0(4), recorded rather than silently edited.** §4.0 stated "the one legitimate
> residual use of CM: **none**." On reflection that is stricter than the evidence supports, and the
> reconstruction sweep independently pushed back, recommending CM as a "correctness oracle."
> **Corrected position:** a **one-off** comparison of the reconstructed series against CM's, to
> check for gross error, falls inside the *verification/diff* scope graded **AMBER-GREEN** in §3.4 —
> and reading a number to check your own is not redistribution. **What remains barred: (a) fitting,
> tuning or calibrating the reconstruction to match CM; (b) any standing/automated dependency;
> (c) gap-filling the reconstruction with CM values.** The acceptance test must be the published
> spec (step 4), not agreement with the vendor.

