# RENTECH TEARDOWN — what the job specs leak, what the public record supports, and what this desk actually has

**Produced 2026-09-24. Public sources only.** The careers page, its 13 open postings, US Senate
sworn testimony, a peer-reviewed paper, and mainstream reporting on Gregory Zuckerman's book.
Nothing behind a login, no paywalled text, nobody contacted. Desk-side numbers are MEASURED on
this box on 2026-09-24 unless a line says UNMEASURED.

**Evidence grades used throughout:**
`[P]` primary — Renaissance's own words (their careers page, sworn Senate testimony, an employee
speaking on the record). `[C]` corroborated secondary — a named journalist or academic, multiple
outlets agreeing. `[S]` single-source secondary — one write-up, not independently confirmed.
`[I]` inference — mine, from the evidence named beside it. `[U]` uncorroborated — the claim was
put to the search and nothing better than a blog repeating it came back.

**THE HEADLINE, AND IT IS ABOUT US, NOT THEM.** Every mechanism below was checked against this
box. The controlling fact is not any single defect: it is that
`desks/mt5/data/gateway_state.json` is **193.2 hours old** (last reconcile
`2026-09-16T09:46:53Z`, last placement pass `2026-09-16T12:48:25Z`, equity 557.09), and
`docs/research/runtime_state.json` — the desk's own attestation, generated 2026-09-23T10:48:29Z —
stamps this host `"role": "non_trading_host"` with `"role_evidence": "gateway_state.json is
169.0h old -- no live trading loop is attested by this document"`. Of 202 hourly legs it
attests: **17 LIVE, 85 STALE, 33 MISSING, 67 NEVER**. Comparing our regime detection to
Renaissance's while the gateway has been dark for eight days is comparing a stopped engine's
ignition timing to a Formula 1 car's.

---

# PART A — THE CAREERS PAGE: ALL THIRTEEN POSTINGS

Source: `https://www.rentec.com/Careers.action?jobs=true` and each `&selectedPosition=` page,
fetched 2026-09-24. Twelve titles, thirteen postings (Systems Engineer is posted twice, NY and
East Setauket). Two slugs Google still indexes — `sysadminNy`, `sysadminEs` — now redirect to the
list: those roles are closed. All quotes below are `[P]`, verbatim from the postings.

## The roster, with salary bands

| Group | Title | Location | Base band |
|---|---|---|---|
| Research | Research Scientist | East Setauket | $185,000–$224,000 |
| Research | Research Engineer | East Setauket | $185,000–$224,000 |
| Programming | Research Infrastructure Programmer | East Setauket | $157,000–$186,000 |
| Programming | Data Programmer | East Setauket | **$129,000–$224,000** |
| Programming | Real-Time Trading Programmer | East Setauket | $173,000–$191,000 |
| Programming | Financial Infrastructure Programmer | NY / East Setauket | $168,000–$204,000 |
| Systems | DevOps Engineer | East Setauket | $191,000–$235,000 |
| Systems | Systems Engineer | East Setauket | $191,000–$235,000 |
| Systems | Systems Engineer | New York | $191,000–$235,000 |
| Systems | Network Engineer | East Setauket | $191,000–$235,000 |
| Systems | Security Engineer | East Setauket | $191,000–$235,000 |
| Facilities | Data Center Specialist | East Setauket | $150,000–$190,000 |
| Operations | Operations Associate – Equity Analyst | New York | $95,000–$146,000 |

**The first structural leak is in that table, not in any posting.** The infrastructure roles pay
**more** than the Research Scientist — DevOps, Systems, Network and Security all top out at
$235,000 against research's $224,000. A firm that pays its sysadmins above its quants has decided
that the machine, not the next idea, is the scarce input. `[I]`

## Research Scientist

> "use state-of-the-art techniques from data science, statistics, and applied mathematics to
> develop trading algorithms and mathematical models of the financial markets"

Required: "an advanced degree in computer science, mathematics, physics, statistics, or a related
discipline"; "a track record of exceptional intellectual achievement"; "a demonstrated capacity to
do first-class research"; "strong computer programming and system design skills".

**What it implies.** The posting names **zero techniques.** No machine learning, no deep learning,
no neural networks, no Bayesian, no HMM, no kernel methods, no Python, no R, no PyTorch. It asks
for a research temperament and "system design skills" — a scientist who can build. The absence is
the signal: either the methods are secret, or (more likely, given Patterson below) the methods are
not exotic enough to advertise. `[I]`

## Research Engineer — the sharpest leak on the page

> "design and build new software for research and data processing"
> "build new technical models for predicting and trading markets"

Required: "a degree in computer science, engineering, mathematics, physics, or a related
discipline"; **"a documented history of designing, developing, and maintaining large software
systems in C/C++23 or Rust"**; **"a good understanding of low-level CPU/GPU details necessary for
high-performance computing"**; "a track record of exceptional intellectual achievement".
Preferred: **"experience in distributed computing, GPU programming, compiler design, and/or
functional languages"**.

**What it implies, and this is the most informative sentence on the whole site.** Set it beside
the Research Infrastructure Programmer's requirement of "expert-level knowledge of **C++11/14/17**"
and the Data Programmer's "**C/C++17**". Three different C++ standards for three different jobs.
The shared research infrastructure and the data pipeline are a long-lived C++11/14/17 estate; the
*new model-building* work wants C++23 or Rust plus GPU internals. Renaissance is building a second,
modern numerical core alongside a large legacy one. `[I]`

"Compiler design" as a plus for a role whose job is to "build new technical models" is not a
general-purpose engineering nicety. It is what you ask for when models are expressed in a domain
language that something compiles — to GPU kernels, most plausibly. That is the same architecture
this desk gestures at with its expression DSL (`docs/RESEARCH.md` §11, 5l), built in Python. `[I]`

## Research Infrastructure Programmer — the headcount number

> "work in a stimulating academic environment to implement and support software used in systematic
> trading, finance, and accounting"
> "work closely with **roughly 150 programmers and scientists** to develop and maintain a **C++
> based infrastructure** that can be used to build complex statistical models and trading
> algorithms employing state-of-the-art techniques from data science and applied mathematics"

Required: "a degree in computer science, mathematics, physics, statistics, or a related field"; "an
outstanding academic record"; "strong analytical and programming skills"; "expert-level knowledge
of C++11/14/17 and programming tools in a **Linux/Unix** environment".

**What it implies.** "Roughly 150 programmers and scientists" is a hard scale number Renaissance
published about itself `[P]`. And one shared C++ infrastructure that everybody builds models in —
not 150 people with their own notebooks. That is the single most transferable organisational fact
on the page, and it is the opposite of how this desk is built (below). `[I]`

## Data Programmer — the widest band on the page

> "use strong analytical skills and in-depth knowledge of **C/C++ under Linux/Unix** to develop,
> improve, test, and maintain **data processing software**"

Required: degree in "computer science, mathematics, physics, statistics, or a related field"; "an
outstanding academic record"; "strong analytical and programming skills"; "experience in C/C++17
and programming tools in a Linux/Unix environment". Preferred: "basic knowledge of statistics
(considered a plus)".

**What it implies.** The band is **$129,000–$224,000** — a $95,000 spread, the widest on the site,
topping out level with the Research Scientist. Data processing is a full career ladder at
Renaissance, not an entry rung, and a senior data programmer earns what a research scientist earns.
`[I]` Note also that statistics is only "a plus" for this role: the data job is an *engineering*
job about correctness and throughput, deliberately not a modelling job. That is a division of
labour, and it is the strongest live corroboration that the Straus data story is still doctrine
forty years on. `[I]`

## Real-Time Trading Programmer — and the dog that does not bark

> "develop and support applications for all aspects of a computerized trading system, with a focus
> on **order handling; real-time risk, regulatory, and operations reporting; and real-time
> accounting**"
> "support complex models of the financial markets and trading algorithms in a real-time
> environment"

Required: degree as above; "an outstanding academic record"; "strong analytical and programming
skills"; "experience in C/C++17 and programming tools in a Linux/Unix environment". Preferred:
"accounting experience (considered a plus in some positions)".

**What it implies, by absence.** Across all thirteen postings there is **no FPGA, no Verilog/VHDL,
no kernel bypass, no Solarflare/Onload/DPDK, no PTP, no multicast, no colocation, no exchange
feed handler, no FIX, and no nanosecond or microsecond anywhere.** The Network Engineer asks for
BGP and OSPF and "a minimum of two years' experience" — an enterprise networking bar, not a
latency-race bar. The real-time role's own emphasis is order handling, risk reporting and
*accounting*.

**Renaissance is not hiring for a latency race.** `[I]` Their "real-time" means correct order
state and correct books at speed, not winning a queue position in microseconds. This matters
enormously for us: the part of their execution edge that is bought with hardware we cannot buy is
smaller than the folklore implies, and the part bought with measurement is larger. (Stated as
inference from absence — absence is weaker evidence than presence, and a firm need not advertise
every skill it employs.)

## Financial Infrastructure Programmer

> "develop and support applications for all aspects of fund administration in a modern financial
> services organization, including **fund accounting, risk reporting, margin management, tax
> reporting, treasury, and investor relations**"
> "prioritize automation to meet processing requirements in a Linux/Unix environment using **Java**"

Required: "a degree in computer science or a related technical field"; "experience in
**Java/Kotlin and PostgreSQL** databases"; "strong programming skills and application development
experience"; "excellent written and oral communication and interpersonal skills"; "an outstanding
academic record". Preferred: "financial services industry experience"; "experience in **Advent
Geneva or SWIFT**".

**What it implies.** A clean language boundary: research and trading are C/C++ (and now Rust); the
fund's books are Java/Kotlin on PostgreSQL with a commercial portfolio accounting system (Advent
Geneva) and SWIFT messaging. Nobody is asked to be fluent in both halves. `[I]` "Margin management"
and "tax reporting" named as first-class engineering surfaces is a quiet echo of the basket-option
history — those were the two things the structure was built to manage.

## Operations Associate – Equity Analyst — the data-hygiene role, still staffed

Department: "Trade Support/Business Analytics".

> "monitor, analyze, and reconcile trading accounts daily by liaising with **prime and executing
> brokers**"

reconciling "account balances and trade-related activity" and "non-trade-related activity";
"maintain counterparty issue lists, coordinate counterparty review meetings"; "support various
projects by conducting **root-cause analysis**"; "leverage technology to support user testing and
the implementation of operational improvements".

Required: "bachelor's degree in finance, information systems, mathematics, or another analytical or
engineering field"; "2-5 years of experience in the financial services field"; "**knowledge of the
trade lifecycle required**". Preferred: "experience preferred from a top-tier multi-strategy
investment firm, investment bank, or fund administrator"; "equity derivatives experience
preferred"; "**corporate action processing experience** (considered a plus)"; "strong data analysis
skills with advanced Excel proficiency". Tools: "Advent Geneva".

**What it implies.** Daily reconciliation against brokers, corporate-action processing, root-cause
analysis of breaks — as a standing salaried function in 2026 `[P]`. The cleanliness discipline the
Straus story is famous for is not a founding anecdote at Renaissance; it is an org chart box with a
salary band. `[I]` This is the single cheapest thing on the page for us to copy, and we do not do
it (Part C.2).

## Data Center Specialist — where the GPUs are

> "conduct engineering analysis and research designs and methods of data center equipment and
> facilities"; "ensure designs and installations meet requirements, including predicted cooling,
> structural, and operational concerns"; "install and document racks, structured cabling, servers,
> switches, and PDUs"; "respond to facility-wide emergencies (power outages, cooling failures) and
> participate in a 24/7 on-call rotation".

Required: "3+ years of hands-on experience in high-availability or large colocation environments";
"comprehensive understanding of data center HVAC systems and redundancy protocols". Named:
HVAC, Building Management Systems (BMS), EPMS, UPS, PDUs, backup generators, one-line diagrams,
and **liquid cooling systems with an understanding of "flow rate and pressure dynamics"**.
Preferred scripting: "Python, Bash, or PowerShell".

**What it implies.** Liquid cooling is what you install for dense GPU racks. Set beside the
Research Engineer's GPU requirement and the DevOps role's LLM line, Renaissance is running its own
GPU estate on its own floor. **There is no AWS, GCP or Azure anywhere on the careers page.** `[I]`

## DevOps Engineer — the 2026 leak

> "operate, improve, and maintain computer infrastructure using **Slurm, Github, Docker, and
> Podman**"
> "**scale and optimize on-premise Large Language Model (LLM) infrastructure**"
> "collaborate with research engineers to execute innovative research ideas"
> "build and package open-source software across multiple ecosystems"
> "implement and operate monitoring and observability systems"

Required: "bachelor's degree in a technical field"; "extensive experience designing, deploying, and
supporting Linux servers"; "extensive experience managing, automating, and orchestrating system
configuration"; infrastructure as code; "experience building and packaging software from source on
Linux". Preferred: DNS/TCP-IP/HTTP(S); "DNS, LDAP, RADIUS, NFS, Kerberos, OpenSSL"; monitoring and
observability.

**What it implies.** Two facts, both current and both `[P]`. **(a) The research cluster is
Slurm.** Research at Renaissance is *batch jobs submitted to a scheduler*, not analysts running
scripts on their own boxes. **(b) They run local LLMs, on their own hardware, at a scale that
needs a dedicated engineer to "scale and optimize".** Corroborated by the Systems Engineer (ES)
posting, which lists "experience implementing, operating, and supporting **Slurm, LLM deployments,
and PostgreSQL**" as a *required* qualification. Two independent postings naming the same stack is
as solid as an outside reading gets. `[P]`

## Systems Engineer (East Setauket)

Required: "extensive experience designing, deploying, and supporting Linux servers and desktops";
"comprehensive understanding of systems and network protocols (DNS, TCP/IP, SMTP, HTTP/HTTPS)";
"**UNIX/Linux system internals (kernel, drivers, file systems, virtual memory)**"; "experience
implementing, operating, and supporting **Slurm, LLM deployments, and PostgreSQL**"; "knowledge of
scripting to automate tasks". Responsibilities include collaborating "with development, production,
trading, and back-office operations" and an on-call rotation.

## Systems Engineer (New York)

Required: "experience administering **Windows** environments (AD/NT)"; "experience administering
Linux environments (LDAP)"; "a thorough understanding of network protocols and fundamentals";
"experience with endpoint and network hardening and security best practices".

**What it implies.** The NY office is a Windows/AD desktop estate (trading support, ops, investor
relations); East Setauket is the Linux/Slurm research plant. Two different machines for two
different jobs. `[I]`

## Network Engineer

Required: "a minimum of two years' experience deploying and supporting scalable routed and switched
networks"; "hands-on experience with enterprise-class routers, switches, and firewalls, including
Cisco and non-Cisco equipment"; "good understanding of network and routing protocols (TCP/IP, DNS,
DHCP, **OSPF, and BGP**)"; "excellent troubleshooting and creative problem-solving abilities,
including **packet-level traffic analysis**".

## Security Engineer

Required: security policy, risk assessments, "firewalls, antivirus/endpoint detection and response
(EDR), intrusion detection and prevention, encryption, vulnerability scanning, identity and access
management"; background in "software development, web application security, security governance,
and incident response". Preferred: "CISSP … CISA … or CISM".

## What the thirteen postings, taken together, describe

1. **On-premise Linux, Slurm-scheduled, GPU-dense, liquid-cooled. No cloud.** `[P]`
2. **One shared C++ research infrastructure used by ~150 programmers and scientists.** `[P]`
3. **A modern numerical core being built in C++23/Rust with GPU and compiler-design skills.** `[I]`
4. **Data processing is a senior engineering career, paid up to the research scientist's ceiling,
   and deliberately not a statistics job.** `[P]` on the band, `[I]` on the reading.
5. **Daily broker reconciliation and corporate-action processing as a permanent staffed function.** `[P]`
6. **Real-time means order state, risk and accounting — not a microsecond race.** `[I]` from the
   absence of every latency-engineering term across all thirteen postings.
7. **They run their own LLMs on their own metal.** `[P]`
8. **Infrastructure is paid more than research.** `[P]`

---

# PART B — THE SIX TRANSCRIPT CLAIMS, VERIFIED

The principal supplied two video transcripts. Their substantive claims are treated below as claims
to check, not as fact. Verdicts: **CORROBORATED**, **PARTLY CORROBORATED**, **UNCORROBORATED**, or
**CONTRADICTED**.

## B.1 "Data cleanliness was a primary edge; an early employee cleaned opening prices, tracked
bid-ask spreads and fixed corporate actions when nobody else bothered."

**CORROBORATED in substance, one person's identity confirmed, the specifics softer than stated.**

The person is **Sandor Straus**, and Zuckerman's book is the source everything else repeats `[C]`.
The corroborated core: Straus assembled and cleaned a historical price database across currencies,
bonds and commodities from magnetic tapes and manual records; he went beyond open/close to
**tick-level price and volume data** when the industry modelled on daily opens and closes; and he
"modelled" missing historical observations rather than dropping them. Reporting on the book states
plainly that a superior and cleaner dataset let the firm find signals competitors could not see.

**What I could NOT corroborate:** the specific triad "opening prices, bid-ask spreads, corporate
actions" as *his* three named tasks. The bid-ask element is plausible and consistent with the
tick-data account; the corporate-actions element belongs to the equities era that began later (Frey,
Mercer/Brown, mid-1990s) rather than to Straus's early futures work. Treat the triad as `[S]`
compression of a `[C]` story. The *direction* — cleanliness first, before modelling — is solid.

**Independent live support from Part A:** the Operations Associate posting requires trade-lifecycle
knowledge, daily broker reconciliation, and prefers corporate-action processing experience, in 2026
`[P]`. That is the discipline still funded, which is stronger evidence than any anecdote about 1983.

## B.2 "Execution cost was the obsession, nicknamed 'the devil'; competitors paid 2-3% against
their 0.3%; large orders sliced into hundreds of pieces across many windows."

**PARTLY CORROBORATED. The nickname and the obsession are real; the 2-3% vs 0.3% comparison is
UNCORROBORATED; the slicing is real but the "hundreds of pieces" figure is not sourced.**

- **"The devil"** — corroborated as Renaissance's internal term for slippage and market impact,
  traced to Zuckerman's book `[C]`.
- **The obsession** — corroborated. Reporting describes Renaissance writing a program specifically
  to track how far executions strayed from the ideal price, and capping Medallion at roughly
  $10bn precisely because slippage is what eats the edge at scale `[C]`.
- **"2-3% against their 0.3%"** — I put this to multiple searches and found nothing supporting it.
  The nearest sourced figures are of a different shape entirely (~1% gross per trade falling to
  ~0.5% after costs) and are themselves `[S]`. **Treat the 2-3% / 0.3% comparison as UNCORROBORATED
  and do not build an argument on it.**
- **Order slicing** — directionally corroborated by the scale: Renaissance told the Senate under
  oath that its funds traded "more than 100,000 trades a day, more than 30 million trades a year"
  `[P]`. Thirty million trades a year *is* order slicing, whatever the per-parent child count. The
  specific "hundreds of pieces across many windows" is `[U]`.

## B.3 "One hundred to three hundred-plus uncorrelated micro-signals rather than one model, each
required to clear p < 0.01, with a master portfolio optimiser choosing which run and how capital is
allocated, rebalancing several times a day."

**CONTRADICTED on architecture; PARTLY CORROBORATED on signal count and on weak-edge aggregation.**

The best public account says the opposite of "rather than one model". Zuckerman reports that
**Henry Laufer decided Medallion would use a single trading model rather than separate models per
instrument or market condition**, and that Simons wanted "a single, monolithic trading system" `[C]`.
The bedrock signal is described as **mean reversion**, inherited from Robert Frey's Morgan Stanley
prediction model, with later additions as "second order complements to the firm's core
reversion-to-the-mean predictive signals" `[C]`.

So: **many weak signals inside ONE model**, not many models with a supervisor choosing between them.
That distinction is load-bearing for us — it is the difference between a mixture-of-experts gate and
a portfolio of independent sleeves, and this desk has built the latter.

- **"Hundreds of weak uncorrelated predictors"** — corroborated in substance `[C]`/`[S]`: the
  aggregation of many weakly-correlated 50.1%-edges is the standard and well-attested description.
- **The hit rate is `[P]`**: Simons told the Senate that Medallion's signals are profitable "only
  slightly more often than not"; Mercer is widely quoted at **50.75%** `[S]`.
- **"p-value below 0.01"** — `[S]`. It appears in multiple write-ups, all tracing to the same book,
  with no primary quote. Plausible, unverified.
- **"100 to 300+"** — `[U]` as a count. No primary source states a number.
- **"Rebalancing several times a day"** — consistent with 100,000 trades/day `[P]`, but the
  *mechanism* (a master optimiser selecting which models run) is `[U]` and sits badly with the
  single-monolithic-model account.

## B.4 "Regime detection via hidden Markov models trained with Baum-Welch, turning momentum off and
mean reversion on as the regime changes."

**THIS IS THE WEAKEST CLAIM IN THE SET, AND IT IS THE ONE THE DESK HAS BUILT ITS ANXIETY AROUND.**

What is solid: **Leonard E. Baum**, co-author of the Baum-Welch algorithm, was Simons's first
recruit from IDA, and Renaissance's earliest modelling lineage runs through his work, later extended
by James Ax `[C]`. That is a real and documented connection.

What is not: **Baum left in 1984. Medallion launched in 1988.** `[C]` Baum himself abandoned
model-driven trading for fundamental trading before the fund that made the returns existed. The
inference "Baum-Welch built Medallion" is a genealogy, not a description of the production system.

I found **no primary or corroborated secondary source** describing a live HMM regime-switcher in
Medallion toggling momentum off and mean reversion on. The best available account of the
architecture — a single monolithic model whose core is mean reversion `[C]` — is in tension with a
top-level regime switch that turns whole strategy classes on and off.

**And the strongest counter-evidence is an employee on the record.** Nick Patterson, formerly a
senior statistician at Renaissance, on the *Talking Machines* podcast `[P]`:

> "…the most important thing to do in data analysis is to do the simple things right. So, here's a
> kind of non-secret about what we did at Renaissance: in my opinion, our most important statistical
> tool was simple regression with one target and one independent variable."

**Verdict: UNCORROBORATED, and in tension with both the best architectural account and with an
ex-employee's own words.** This matters for us in exactly one way, stated bluntly in Part C.1: the
mechanism this desk is most worried about lagging is the one with the least public evidence that
Renaissance ran it.

## B.5 "High-dimensional kernel regression, Bayesian updating, and a unified cross-asset model with
vector embeddings, attributed to Henry Laufer."

**PARTLY CORROBORATED — the unified model is solid, the named techniques are not.**

- **Unified cross-asset model, attributed to Laufer: CORROBORATED** `[C]`. Laufer pushed for a
  single cross-asset, cross-asset-class model so all the cleaned pricing data could be used at once,
  and decided Medallion would run one model rather than many. This is the well-attested part, and it
  is the part worth copying.
- **"High-dimensional kernel regression": `[S]`.** It recurs in secondary write-ups; I found no
  primary statement. Plausible for the era and the people, unverified.
- **"Bayesian updating": `[S]`/`[U]`.** Generic enough to be unfalsifiable as stated.
- **"Vector embeddings": `[U]`, and anachronistic as phrased.** The term carries modern
  representation-learning connotations that no source supports for the era in question. If the
  underlying claim is "a shared latent representation across assets", that is just the unified model
  again, which is already corroborated.

## B.6 "Leverage of roughly 10-20x via basket options, condemned by the US Senate in 2014, settled
with the IRS in 2021, no longer available."

**CORROBORATED, with the numbers tightened from primary sources. This is the best-evidenced claim
in the set.**

From the Senate Permanent Subcommittee on Investigations hearing of 22 July 2014, *Abuse of
Structured Financial Products: Misusing Basket Options to Avoid Taxes and Leverage Limits*, all
`[P]`:

> **Senator Levin:** "So instead of complying with the 2:1 leverage ratio, the banks offered their
> hedge fund clients leverage as high as 20:1."

> **Senator Levin:** "RenTec estimates that its trading through basket options accounts averaged
> more than 100,000 trades each day, or about 30 million trades a year."

> **Mr. Rosenthal (RenTec):** "The Renaissance hedge funds traded often, more than 100,000 trades a
> day, more than 30 million trades a year."

> **Mr. Rosenthal:** "statistical arbitrage entails trying to determine relationships between
> different assets…determine whether price is out of kilter."

Reporting on the structure adds that the arrangement let Medallion "borrow up to $17 for every
dollar the fund owned, which is more than it could have in a traditional margin-lending
relationship" `[C]`, and that the banks were Deutsche Bank (MAPS) and Barclays (COLT) `[C]`. The
Subcommittee estimated ~$6.8bn of taxes avoided `[C]`.

Settlement: in September 2021 Renaissance executives and investors agreed to pay approximately **$7
billion** to the IRS covering the tax treatment of options transactions from **2005 to 2015**, with
Simons paying an additional **$670 million** personally; CEO Peter Brown described settling "rather
than risking a worse outcome" `[C]`, multiple outlets.

**So: 17:1 to 20:1, not "10-20x"; the structure is closed; and the headline returns were earned
inside it.**

## B.7 The fact neither transcript mentions, and the most important one for us

**Renaissance's own external funds, run by the same people on the same software, do not reproduce
Medallion.** In 2020, Medallion returned **+76%** while Renaissance Institutional Equities Fund
(RIEF) lost **−22.6%** and Renaissance Institutional Diversified Alpha (RIDA) fell as much as
**−33.58%** `[C]`. Reporting attributes the divergence to Medallion's **short holding periods**,
faster adaptation, and **more leverage**; the public funds hunt longer-term aberrations in smaller
names. Roughly **$11 billion** of redemptions followed `[C]`.

This is as close to a controlled experiment as the public record offers. Same firm, same research
infrastructure, same senior management, same ~150 programmers and scientists — and the methods
alone, applied at a longer horizon without Medallion's leverage and capacity discipline, produced a
catastrophic year in the same twelve months the flagship made 76%.

**Read it honestly in both directions.** It refutes "just copy their methods and you get their
returns." It equally refutes "it was all the tax structure" — RIEF had the same researchers and
still lost. What separates them is *horizon, capacity discipline, and leverage*, and only the first
two are available to us.

## Reference facts, for calibration

| Fact | Value | Grade |
|---|---|---|
| Medallion gross annualised, 1988–2018 | ~66% | `[C]` |
| $100 → , 1988–2018, compound | $398,723,873; 63.3% | `[C]` Cornell, *J. Portfolio Management* 46(4), 2020 |
| Negative years, 1988–2018 | none; market beta and factor loadings all negative | `[C]` Cornell |
| Fees | 5% management / 44% performance | `[C]` |
| Outside investors | none since ~2005; employees only | `[C]` |
| Capacity | held near ~$10bn deliberately | `[C]` |
| Trades | >100,000/day, >30 million/year | `[P]` Senate |
| Hit rate | "profitable only slightly more often than not"; ~50.75% | `[P]` / `[S]` |
| Research + programming headcount | "roughly 150 programmers and scientists" | `[P]` careers page |

---

# PART C — THE SAME MECHANISMS, MEASURED ON THIS DESK

Everything below was checked on this box on 2026-09-24. Where the brief that commissioned this
teardown stated a number, I checked the number. **Three of the three stated numbers were wrong**,
and in each case the true state is a different problem from the one described. That is worth more
than agreement would have been.

## C.1 REGIME DETECTION — the brief's numbers are a source comment, and the real HMM is somewhere else

**What the brief said:** "a regime router … scores ZERO of 258 sleeves and publishes DARK: 34
sleeves are short of the fold minimum and 14 have no varying state feature."

**What is on disk.** `desks/mt5/reports/REGIME_ROUTER.json`, `"at": "2026-09-17T00:20:20.731379+00:00"`
— **178.7 hours stale**:

```json
"n_sleeves": 22,
"unmeasured": ["no sleeve's router beats its unrouted model out of sample after tax"],
"counts": {"live_rows_dropped": 95, "sleeves_without_trades": 196, "trades": 72,
           "sleeves_without_vol_axis": 0, "rows_without_full_state": 0,
           "router_active": 0, "representation_adapted": 0}
```

Recomputed from the 22 published sleeve rows: **0 scored, 6 short of the fold minimum
(`"N trades < 24 needed for folds"`), 16 with `"no state feature varies over this sleeve's trades"`.**

**The 258 / 34 / 14 figures exist only as a source comment** at
`desks/mt5/research/regime_router.py:666-667`:

```
# ZERO were scored because every sleeve was under the fold minimum. MEASURED on the box
# 2026-09-24: 48 published, 0 scored, 34 short of trades and 14 with no varying state feature.
```

The code that would publish that census (`_router_census`, lines 795-850) **has never written to
disk** — the artifact predates it by seven days. There is no `router_census` block and no
`DARK`/`LIT` status enum; "DARK" appears once as prose in a note string at line 676. The dashboard
says so itself (`desk_dashboard_state.py:1126`): *"REGIME_ROUTER.json publishes no router_census, so
a zero here cannot be told from a dark router"*. **So the headline comparison is UNMEASURED, and
the honest statement is: 0 of 22, six days ago.**

**The method is not Renaissance's, and that is fine.** The router's state is causal terciles and
sign/calendar rules — `np.quantile(pre, [1/3, 2/3])` at line 290, `np.sign(...)` at 246, sessions by
server hour at 296-298. The learned part is an **intercept-only SoftMoE**: line 433-449,
*"each [expert] is a mean-R predictor, the gate carries every bit of the state dependence, and the
model is `sum_k p(k | state) * mu_k`"*, scored by walk-forward Gaussian predictive log-density over
4 expanding folds, `K_GRID = (2, 3)`, activation tax `0.002`. **There is no HMM in the router.**

**But the desk DOES own the exact machinery Renaissance is famous for, and it is wired somewhere
else.** `libs/regime/hmm.py` is a self-contained Gaussian HMM implementing *"Baum-Welch EM (fit),
Viterbi (most-likely path), and the online forward filter … in log-space"*. It is consumed — by the
allocator, at `desks/mt5/research/pf_allocator.py:552-566`:

```python
from libs.regime.engine import RegimeEngine
from libs.regime.transitions import forecast as regime_forecast
eng = RegimeEngine().fit(close)
fc = regime_forecast(eng.hmm.transmat, post, lab, eng.filtered_states, horizons=REGIME_TERM_STRUCTURE)
```

with the module's own caveat at line 545: *"STILL FITTED ON XAUUSD DAILY CLOSES, which is a real
limitation and not a design"*. And `leg:pf_allocator` is **162.2 hours stale**.

Alongside it, `libs/regime/transitions.py` carries a hidden **semi-Markov** duration model whose own
docstring reads: *"Baum-Welch and has done since it was written. **Nothing has ever read it.**"*

**Nothing consumes the router to size anything.** `pf_allocator.py` contains zero occurrences of
`regime_router`. The one wire that looks live is dead: `allocator_trigger.py:98` watches keys
`("current", "route", "regime", "routed_to")` — **none of which is a top-level key in the artifact**
(the key is `current_state`) — so `_signature` returns the constant `"no-watched-key"` and the
trigger can never fire however the regime moves.

**What actually turns sleeves off** is a different, threshold-based organ: `regime_monitor.py` →
`data/regime_state.json` → `gateway.py:628 regime_hibernate()` → `gateway.py:3552`, thresholds
`HIBERNATE_EXP = -0.10` / `WAKE_EXP = -0.05`. Its state: `swept_at 2026-09-16T14:09:57Z`, **186
sleeves, every one `flag: "ok"`, zero hibernated, zero with any live trades**, and
`hibernate_filter_value: {"verdict": "UNMEASURED", "why": "no vetoed bracket has been replayed
yet"}`. `leg:regime_monitor` is **307.2 hours stale** despite a 15-minute box task
`MT5-RegimeMonitor`.

**Bug found while measuring, worth fixing regardless of anything in this document.**
`desks/mt5/tests/test_regime_router.py:136-141` monkeypatches `SLEEVES`, `LIVE_LEDGER`,
`SHADOW_DIR`, `SHADOW_STATE`, `UNI` and `OUT` — **but not `HISTORY`** — and then calls
`rr.main([])`, which writes. `desks/mt5/data/regime_state_history.jsonl` consequently holds exactly
one row, `{"at": "2026-09-23T22:56:22Z", "state": {"session": "off", "usd": "UNMEASURED", …}}`.
**The desk's only regime history row is test fixture residue, not an observed regime.**

**Honest verdict.** Against B.4 — the Renaissance claim with the *least* public support — this desk
has: a non-HMM router that is dark and stale; a genuine Baum-Welch HMM that *is* wired to the
allocator but fitted on one instrument's daily closes; a hidden semi-Markov model nothing has ever
read; and a threshold hibernator that has never hibernated anything. Four regime machineries, no
regime decision.

## C.2 DATA CLEANLINESS — the brief's defect does not exist; the real one is subtler and partly self-diagnosed

**What the brief said:** "the hourly spread column is a constant placeholder for foreign exchange:
three unrelated majors all read exactly 50.0 and two more exactly 160.0, against live and minute-bar
values of 2 to 6."

**Measured: FALSE.** Across **all 299 `*_H1.parquet` files** in `desks/mt5/data/universe/`,
the count with `spread.nunique() == 1` is **zero**. Every one varies.

| file | rows | nunique | mode (value, count) | min | max |
|---|---:|---:|---|---:|---:|
| EURUSD_H1 | 54,205 | 58 | (12, 19,538) | 0 | 165 |
| GBPUSD_H1 | 54,206 | 125 | (13, 15,268) | 0 | 308 |
| USDJPY_H1 | 54,336 | 98 | (13, 20,569) | 0 | 200 |
| USDCHF_H1 | 54,205 | 164 | (13, 23,970) | 0 | 293 |
| XAUUSD_H1 | 50,255 | 76 | (18, 10,346) | 0 | 268 |

Only one H1 file anywhere has 50.0 as more than half its rows: `AAL_H1.parquet` at 64.6% — an
equity CFD, not FX. The column is written by `desks/mt5/research/fetch_universe.py:329,338,341-342`
straight from `mt5.copy_rates_range`, i.e. **MT5's own per-bar spread in POINTS as `int32`** — not a
placeholder and not a tick reading.

**Where the real number lives.** The scalar every gate divides by is `median_spread_pts` in
`desks/mt5/data/universe/universe.json`, consumed at `desks/mt5/mt5desk/engine.py:158-159` and
`mt5desk/universe.py:260`. Measured directly, 2026-09-24: **14 of 251 symbols read `0.0`** —
`AUDJPY, AUDSGD, AUDUSD, EURAUD, EURCAD, EURGBP, EURUSD, GBPCAD, GBPUSD, NZDCAD, NZDUSD, USDCAD,
USDCHF, USDJPY`. That is **eight FX majors priced at zero spread**, against XAUUSD 14.5 and
EURJPY 5.0.

**And here is the part that inverts the brief.** The 50/160-shaped values *were* real, in the
**pre-repair** registry: `cost_basis_ratchet.json` records GBPCHF 165→3, CADCHF 98→3, NZDJPY 147→15,
with **106 of 136 corrections applied on 2026-09-23** via
`desks/mt5/scripts/repair_universe_spreads.py`. The brief is describing a state that was largely
repaired the day before.

The **30 refused** corrections were refused for a reason, and the desk's own `cost_truth` organ
published it — `docs/research/COST_TRUTH.md`, columns *symbol | charged | corrected to | broker
quotes | error before | after*:

```
| EURUSD | 0.0 | 12.0 | 0.0 | 0.0 | 12.0 (AWAY) |
| GBPUSD | 0.0 | 13.0 | 0.0 | 0.0 | 13.0 (AWAY) |
| USDCHF | 0.0 | 13.0 | 0.0 | 0.0 | 13.0 (AWAY) |
```

**The broker's live terminal quotes 0 points on those majors.** This is a Fusion RAW account where
the cost is the commission — measured at **2.00 EUR per lot per side, p10 = p50 = p90 = 2.00 over
n = 8 symbols, status MEASURED** — not the spread. The H1 median of 12-14 points is a *pre-2021
fixed-spread era* artifact, as `expand_universe.py:414` already notes. So `median_spread_pts = 0.0`
on EURUSD is plausibly **correct**, and "correcting" it to 12 would move the charge *away* from what
the venue quotes. The desk's own organ got this right and refused.

**So what IS the data-cleanliness defect? Three real ones, none of them the one alleged.**

1. **A false invariant asserted in a docstring and used to skip an audit.**
   `desks/mt5/research/cost_surface.py:38-39` claims *"EURUSD is EXACTLY 12 pts at all 24 hours and
   XAUUSD EXACTLY 16 — administered spreads, flat by construction."* Measured: EURUSD's per-hour
   medians take **two** values {12.0, 16.0}, and 12 is only **36.0%** of the column (58 distinct
   values, max 165). The premise that justified skipping the majors in the cost-surface audit does
   not hold. Same file, lines 6-7, cites ingest sites `fetch_universe.py:103` and
   `expand_universe.py:136`; the real lines are `343` and `236`.

2. **51 research call sites bypass the measured cost entirely.** Pinned by a ratchet test,
   `desks/mt5/tests/test_no_literal_spread_per_lot.py`, `MAX_LITERAL_SITES = 51` — still exactly 51
   today. They read, e.g. `desks/mt5/research/run_hunt10.py:32`:
   ```python
   COSTS = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100)
   ```
   `0.48` is USD **per ounce** in a field that wants account currency **per lot**; the engine divides
   by `contract_oz=100` and charges gold **0.0048/oz**. The test's own docstring: *"Every gold
   backtest ran very nearly spread-free, and the 3x cost-stress gate that existed to catch exactly
   this was stressing 3% up to 9%."* The commission literal of 3.50 is the brochure USD figure
   against a measured 2.00 EUR. Separately, `libs/backtest/fills.py:13-23` defaults
   `slippage_frac: float = 0.0`, and `libs/costs/params.py` carries hand-written per-instrument
   priors its own docstring says to "calibrate against realized fills before live".

3. **The cleaning layer Renaissance's whole story is about does not run.** `libs/data/medallion.py`
   defines `build_silver` and `build_gold`. `libs/research/bar_span.py:52` states: *"`build_silver`,
   which has no production caller, and the lake holds only `bronze/`."* `build_gold` has no caller
   anywhere outside its test. The `lake_promote` leg **is** live (artifact 174 s old — one of only
   17 live legs), and its own output reads:
   `"lake_promote: 18079 bronze -> 0 silver (0.0%), 18079 refused … no resolvable event_time"`.
   Every research script therefore reads raw bronze and re-derives its own cleaning, so two screens
   on the same symbol can disagree and neither records how.

**Honest verdict.** Renaissance's first edge was a *shared, cleaned, canonical dataset that
everybody modelled on*. We have 299 clean parquet files, one correct cost scalar, one organ that
audits it honestly — and **no silver layer, 51 call sites that ignore the audited number, and a
false flatness invariant used to skip the majors**. The gap is not dirty data. It is **the absence
of one canonical cleaned layer with one owner**, which is precisely what "roughly 150 programmers
and scientists" sharing "a C++ based infrastructure" buys them.

## C.3 UNCORRELATED SIGNALS — the recovery is unpublished, unreproducible, and measures something else

**What the brief said:** "effective rank recovered from 11.2 to 36.6 tonight against 65 registered
families."

**Measured: the number is not published anywhere, and the live recompute does not reproduce it.**

`desks/mt5/research/rank_recovery.py:55` declares `Artifact: reports/RANK_RECOVERY.json` and line 79
declares `docs/research/production_rank_ratchet.json`. **Both files are absent.**
`desks/mt5/data/events.jsonl` contains **zero** occurrences of `rank_recovery` — the leg has never
emitted. It *is* wired (`hourly_cycle.py:965`, budget 300 s, invoked at 3931-3933 with
`--once --budget-s 240`), and `research/issue_board.py:131` gives it a 3600 s staleness bound that
should have been flagging the missing artifact.

The 11.2 → 36.6 claim's actual source is **a commit message**, `c342461c674` (2026-09-24 02:18:28):
*"EFFECTIVE RANK 11.191 -> 36.5771 … Producers 200 -> 205, cells 49,671 -> 138,436…"*

Re-running the module's own matrix and formula against `data/alpha_registry.sqlite` now:

| Field | Commit message | **Measured 2026-09-24** |
|---|---:|---:|
| effective_rank | 36.5771 | **12.1491** |
| producers | 205 | **115** |
| cells | 138,436 | **6,127** |
| top producer's share | 8.87% | **18.15%** |

The claimed cell count is not merely stale, it is **arithmetically impossible**: `research_candidates`
holds **47,475 rows** in total and each row contributes at most one (producer, cell) pair.

**And the deeper problem is what the metric measures.** The formula (`rank_recovery.py:125,142-144`)
is a participation ratio, `(Σsᵢ²)² / Σsᵢ⁴`, computed on a **producer × (family|symbol|horizon) binary
indicator matrix**. The module says so itself at lines 209-211:

> "effective rank is a PRODUCER-CONCENTRATION measure: it equals the participation ratio of the
> per-producer cell counts whenever the rows are near-disjoint, so it rises only when output spreads
> across MORE producers, never with volume"

Confirmed numerically: the participation ratio of the raw per-producer counts is 12.2614 against the
SVD figure of 12.1491 — agreement to 0.9%. **This number describes how evenly the desk's research
output is spread across its own code organs. It is not a measure of signal diversity at all, and it
cannot be compared to "hundreds of uncorrelated signals" in any direction.**

**"65 registered families" matches no source.** `FAMILY_REGISTRY` (`mt5desk/families.py`) holds 28
(published as `"n_families": 28` in `reports/ALPHA_GENOME.json`); `ORTHOGONAL_FAMILIES`
(`families_orthogonal.py`) holds 36, with **zero overlap**; `run_hunt16.py` holds 14. Union of the
first two = 64, of all three = 78. The live registry DB holds **145** distinct family strings (many
are raw formula expressions). `reports/CONVERSION_MAXIMISER.json` publishes 62. Nothing reads 65.

**The number that DOES reach risk is much smaller, and it is clamped out.** The heat budget's √k_eff
law is real — `mt5desk/decision_core.py:789`:

```python
scaled = base * math.sqrt(float(k_eff) / _HEAT_BASE_KEFF)   # _HEAT_BASE_KEFF = 2.26
```

but its `k_eff` comes from `mt5desk/independence.py:measure_from_ledger`, i.e.
`k_eff = N / (1 + (N-1)·ρ̄)` on **live-ledger return correlations** — a different measurement that
the production effective rank never touches. Its live value, `desks/mt5/data/effective_breadth.jsonl`
last line, `2026-09-16T14:26:51`: **`effective_breadth = 2.057` on `n_nominal = 160`.** That is
*below* the 2.26 base, so `max(scaled, base)` clamps the term away and the heat budget returns its
base unchanged. Eight days stale.

**Two allocator call sites are dead code.** `desks/mt5/pipeline/allocate.py:54-62` and
`desks/mt5/side_channels/allocate.py:54-62` both do
`from mt5desk.gateway_config_fallback import Q_OPT, heat_budget` — `heat_budget` **is not defined in
that module** (the sole definition is `decision_core.py:725`), so it raises `ImportError`; and
`measure_from_ledger` returns `tuple[float | None, str]`, so even if it imported, `heat_budget` would
receive a tuple and raise `TypeError`.

**Sleeve counts, for the record.** `desks/mt5/data/sleeves.json`: **66 (40 LIVE, 26 STANDBY)**.
`desks/mt5/data/sleeve_registry.json`: **319**, zero name overlap with the former. The "258 sleeves"
in the brief appears in no artifact; nearest published figures are 319, 224
(`COUNTERFACTUAL_ATTRIBUTION.json`), 215 (`POSTERIOR_ALPHA.json`), 160 (`effective_breadth`) and 66.
**258 is UNMEASURED.**

**Honest comparison with Renaissance.** They ran, on the best available account, many weak
weakly-correlated predictors inside **one** model, and their measured independence was expressed as
a hit rate barely above a coin flip that compounded because the bets were numerous, short and nearly
independent. Our measured independence is **ρ̄-implied k_eff = 2.057 across 160 nominal sleeves** —
i.e. 160 sleeves behaving like about **two** independent bets. That is the real comparison, it is
eight days stale, and it is far more damning than anything the 11.2/36.6 figure was pointing at.

## C.4 EXECUTION COST — the organ exists, the ladder exists, and neither is connected

Renaissance's execution obsession (B.2) is the mechanism with the clearest transfer to a one-account
desk, so this section is the most consequential.

**Scale, for honesty.** Account 495044 (Fusion Markets, EUR). Whole realised record from
`desks/mt5/data/cost_truth_quotes.json` (snapshot `2026-09-23T05:13:05Z`): **433 deals; 430 traded;
212 distinct round trips; 12 distinct trading days; every one of them between 2026-09-01 and
2026-09-22.** Per symbol: XAUUSD 172, EURCHF 100, CHFNOK 38, AUDUSD 38, AUDCAD 22, USDCHF 16,
AUDNZD 16, EURGBP 14, then singles.

> **Renaissance: >100,000 trades per day** `[P]`. **This desk: 212 round trips, total, ever.**
> Their daily trade count exceeds our lifetime count by roughly 470×. Every statistical statement
> about our execution rests on a sample two to three orders of magnitude smaller than theirs.

**The markout organ measures one thing and has no horizons.**
`desks/mt5/mt5desk/markout.py` computes `entry_slip = (fill - intended) * direction` — intent versus
entry fill, a single point, no ladder. Its artifact `reports/markout.json` is dated **2026-09-08**
and reads `"usable": false, "n_matched": 0`, with the honest note:
*"no matched intent/deal pairs yet … This is NOT a clean bill of health -- execution is UNMEASURED
until a fill exists."*

**`matched_fills` now has three contradictory live answers.** Re-running the organ read-only against
current data gives **30 matched** (of 151 attributed deals, 20%; 121 unmatched). `FILL_RECORDER.json`
(`2026-09-23T22:00:47Z`) reports **151** under a looser rule its own `join_rule` concedes is
definitional — *"A DEAL WITH NO SURVIVING INTENT IS STILL A REALISED FILL … with slippage None,
never zero"* — and only **30** of those carry slippage (`"slip_points": {"n": 30, "share": 0.199}`).
Meanwhile `COST_TRUTH.json` still publishes
`"impact": {"status": "UNMEASURED", "why": "matched_fills is 0…"}`, and **`gateway.py:2841` branches
on the stalest of the three**: *"…which needs matched_fills > 0 and it is 0."*

**And the one verdict that sounds reassuring is manufactured.** The live recompute prints
*"slippage as a share of the book's +0.159R edge: 0.0% -- tolerable"*. That 0.0% comes from
`mean_slip_r = +0.0000`, which comes from `markout.py:234`,
`mean_r = (sum(srs) / len(srs)) if srs else 0.0` — and **`n_r = 0`**: not one of the 30 matched rows
carries a usable positive `risk_quote`. The "tolerable" reading is an empty-list fallback, not a
measurement. In quote units the same run gives mean `-0.06627`, median `+0.00000`, worst `+0.59000`;
`FILL_RECORDER` gives `mean_slip_r -0.03197`, `mean_slip_points 0.467`, `worst_slip_points 276.0`.

**Order slicing: fully built, fully priced, routed nowhere.**
`desks/mt5/mt5desk/execution_registry.py:275` registers
`"market": market, "twap": twap, "iceberg": iceberg, "sniper": sniper, "pullback": pullback`, with
`twap(intent, *, slices=4, horizon_s=900.0)` and `iceberg(intent, *, display_lots=None,
replenish=True)`. It runs on **every** gateway pass and writes its winner into every intent row —
live `order_intents.jsonl` shows `"registry": {"best": "iceberg", "utility": 0.2985, "children":
[…3 child orders…]}`. And then `gateway.py:332`:

```python
ROUTABLE_ALGOS = ("market",)
```

The gateway's own comment at 2820-2841 states it without flinching:

> "Nine execution policies and five child-order algorithms are priced and ranked inside every
> gateway pass, and exactly two order shapes have ever reached the venue: a pending stop for gold
> and a market order for everything else, chosen by a hard-coded branch rather than by the argmax
> the competition computes. That is the whole of E2: the ranking exists, is measured, and decides
> nothing."

The enabling flag `data/EXEC_ROUTING_ENABLED` does not exist on disk. What actually reaches the
venue is one full-lot `TRADE_ACTION_DEAL` with `"deviation": 20` (`gateway.py:2864-2869`) or one
`TRADE_ACTION_PENDING` stop (`gateway.py:1114-1138`).

**Realised spread at fill time: UNMEASURED, and the organ for it is written and unimported.**
`libs/research/fill_markout.py` implements exactly the Renaissance measurement —

```
EFFECTIVE COST     (fill - mid_at_fill) * direction
MARKOUT(h)         (mid_at_fill_plus_h - mid_at_fill) * direction
REALISED SPREAD(h) effective_cost - markout(h)
```

with `HORIZONS_MS = (1_000, 5_000, 30_000, 60_000, 300_000)`. **Nothing imports it; no artifact
exists.** `reports/MICROSTRUCTURE.json` (2026-09-16) lists `realised_spread`, `fill_markout_curve`,
`entry_slippage`, `effective_spread_at_latency` and `post_fill_mid_drift` under `"STARVED"`, with
`"by_verdict": {"LIVE": 2, "STARVED": 12, "UNBUILDABLE_ON_VENUE": 7, "NEEDS_EXTERNAL_FEED": 1}` and
`"venue_depth": {"state": "NO_DEPTH", "n_symbols": 22, "with_depth": []}`.

The input pipe is 1.3% full: `quote_mid_at_decision` and `spread_points_at_decision` are populated on
**2 of 151** fills; `latency_send_to_ack_ms` on **0**. Of 92 intents in `order_intents.jsonl`, 8
carry `decision_bid`/`decision_ask` and `fill_price` is populated on **none**. The `gateway.py:999-1004`
`setdefault` backfill that captures the tick on every intent was added **2026-09-23 — eight days
after the last live order**.

**What IS measured, and it is real.** `reports/EXECUTION_COST_SURFACE.json` (2026-09-23) publishes 3
of 8 symbols MEASURED — CHFNOK `cost_r 0.0494` (n=8), EURCHF `0.0253` (n=8), XAUUSD `0.0131` (n=5) —
with `"cost_r_is_bound": true` and `"excludes": ["commission", "swap", "market_impact"]`; five more
deferred under `MIN_DEALS=5`. Commission is genuinely measured at 2.00/lot/side. Market impact is an
honest `MEASURED_NULL` on n=30: `slope 16.2943 points/lot, se 862.5164, t 0.019`, upper bound
1741.33 — i.e. indistinguishable from zero on 30 fills spanning 0.01–0.1 lots.

**Honest verdict.** On the mechanism that transfers best, this desk has written every piece —
markout, the horizon ladder, five child-order algorithms, a cost-truth organ that audits the venue
honestly and refuses bad corrections — and connected almost none of it. The blocker is not
intelligence or code. It is **212 round trips**: every one of these instruments starves below its
minimum sample, and the gateway has been dark for eight days, so the sample is not growing.

## C.5 THE SHARED RESEARCH PLANT — the one comparison where we are not close

Renaissance: ~150 programmers and scientists, **one** shared C++ infrastructure, Slurm-scheduled
batch jobs, one canonical data plant, and infrastructure engineers paid above researchers `[P]`.

This desk, measured: **1,287 registered components**, of which 366 declare an output artifact and
**921 "declare no output artifact — nothing to hash"**. Of 202 hourly legs: **17 LIVE, 85 STALE, 33
MISSING, 67 NEVER**. Three separate family registries with zero overlap between the two largest.
Three contradictory answers to `matched_fills`. Four regime machineries and no regime decision. A
number quoted from a commit message that no artifact publishes. A test writing into a production
ledger.

That is not a research plant with 150 people sharing one infrastructure. It is ~1,300 organs, most
of which nothing reads, and the honest reading is that **our binding constraint is the same one
Renaissance solved with a salary band: one canonical shared layer, owned, that everything else is
required to use.**

---

# PART D — STRUCTURAL VERSUS METHOD

The single most useful discipline in this whole teardown is separating the advantages Renaissance
had *because of what they were* from the advantages they had *because of what they did*. Only the
second kind is buyable with effort.

## STRUCTURAL — unavailable to us, and no amount of cleverness changes it

1. **17:1–20:1 leverage via bank basket options.** `[P]` Senate. The structure was condemned in
   2014 and settled for ~$7bn in 2021 covering 2005-2015. It is gone, for them and for everyone. A
   large part of the headline return was manufactured here, and any comparison of our returns to 66%
   that ignores this is dishonest arithmetic.
2. **Prime brokerage and multi-venue routing.** Their Operations role reconciles against "prime and
   executing brokers", plural. We are **one account at one retail broker**, with
   `"venue_depth": {"state": "NO_DEPTH", "with_depth": []}` — we cannot see the book, let alone
   choose a venue. Order slicing to hide size across venues is not available to us at any effort
   level, and our `twap`/`iceberg` implementations should be understood as *intra-broker* tools at
   best.
3. **Trade count as a statistical engine.** 100,000/day versus our 212 lifetime. Their edge
   *is* the law of large numbers applied to a 50.75% hit rate. At n=212 a 50.75% edge is
   indistinguishable from noise and will remain so for years. **Every statistical method they used
   was powered by a sample size we will not reach.**
4. **~150 programmers and scientists, ~$200k+ each, plus an on-prem GPU plant with liquid cooling
   and a 24/7 facilities rotation.** `[P]` An 8 GB Windows VM is not a smaller version of this; it is
   a different category of object.
5. **Capacity discipline enforced by closing the fund.** They kept Medallion near $10bn and returned
   outside money to protect the edge. We have the *opposite* structural position — we are far below
   any capacity limit — which is genuinely an advantage, and it is the one in this list that favours
   us.
6. **Forty years of proprietary cleaned history nobody else has.** Their oldest edge compounds.
   Ours starts when our recorders started.

## METHOD — copyable, and cheaply

1. **Clean the data first, in one canonical place, with one owner, and make everything use it.**
   That is the Straus lesson and it is still an org-chart box in 2026 `[P]`. It needs no capital.
2. **Treat execution cost as a first-class measured quantity, not an assumption.** "The devil" `[C]`.
   Measuring realised spread and markout needs a tick capture at decision time and a join — both of
   which we have already written.
3. **Reconcile against the broker daily and root-cause every break.** `[P]` from the Operations
   posting. Costs nothing but a scheduled job.
4. **One model / one shared representation across assets rather than per-instrument silos.** Laufer
   `[C]`. This is an architecture choice, free at our scale.
5. **Many weak, weakly-correlated predictors, judged on their *marginal independence*, not their
   standalone Sharpe.** `[C]`. We already have the law (`docs/RESEARCH.md` §6c-bis) — what we lack is
   a working measurement of independence (C.3).
6. **Do the simple things right; prefer simple regression.** Patterson, on the record `[P]`. This is
   the cheapest and most-ignored item on the list.
7. **A shared research infrastructure everybody is required to build in, with batch scheduling.**
   `[P]`. Slurm is not the point; *one plant* is the point.
8. **Pay for the plant.** Infrastructure paid above research `[P]` is a revealed preference. Our
   analogue is spending cycles on wiring and liveness rather than on new organs.

## The honest middle: what looks structural but is actually method

**Short holding periods.** The RIEF/Medallion divergence `[C]` points at horizon as a primary
discriminator, and horizon is a *choice*, not a resource. Medallion's holding period is reported as
a day and a half to a week and a half in the Berlekamp era `[C]`. This desk trades gold windows and
scalp sleeves, which is the right end of the spectrum — we are, on this axis alone, structurally
closer to Medallion than Renaissance's own $10bn public funds were.

---

# PART E — RANKED BY EXPECTED VALUE TO THIS DESK

Ranked by expected contribution to robust forward E[log W], not by how impressive they sound. Each
carries what it costs and why.

### 0. Restart the gateway and get the legs live again. **Prerequisite, not an item.**
`gateway_state.json` is 193 hours old; 17 of 202 hourly legs are LIVE. Every item below is worth
zero while the machine is off, and every measurement in Part C decays further each day. This is not
a research item and it does not compete with them.

### 1. Capture the tick at decision time on every intent, and turn on `fill_markout.py`. **HIGHEST.**
The organ is written (`libs/research/fill_markout.py`, five horizons), the schema fields exist
(`quote_bid`, `quote_mid_at_decision`, `spread_points_at_decision`), and the `gateway.py:999-1004`
backfill already landed on 2026-09-23 — it has simply never seen a live order. **Cost: an import and
a scheduled leg.** Payoff: the single mechanism Renaissance were most obsessive about, the one that
transfers fully to one account at one broker, and the one blocking three downstream verdicts
(`impact`, `cost_r_is_bound`, execution routing). It also converts the manufactured "0.0% —
tolerable" into a real number. *Why first: highest payoff-to-cost ratio on the page, and it is the
gate on item 4.*

### 2. Collapse `matched_fills` to ONE answer, and fix the zero-denominator verdict.
Three live values (0 / 30 / 151) with the gateway branching on the stalest, and
`markout.py:234`'s `if srs else 0.0` manufacturing a clean bill of health from an empty list.
**Cost: hours.** Payoff: every execution decision downstream currently reads a number that is wrong
in a direction that flatters us. *Why second: a wrong measurement is worse than no measurement, and
this one is actively arming a branch.*

### 3. One canonical cleaned layer, with one owner, that everything is required to use.
Make `build_silver` run (it is refused today on `no resolvable event_time`), delete the 51
hardcoded-cost call sites down the ratchet, and fix the false flatness invariant at
`cost_surface.py:38-39`. **Cost: days.** Payoff: this is the Straus mechanism and the ~150-people
mechanism in one item — it removes the class of error where two screens on one symbol disagree and
neither records how. *Why third: highest ceiling of anything here, but it is a week of work rather
than an afternoon, and item 1 buys more per hour.*

### 4. Fix the independence measurement, then let it size.
`effective_breadth = 2.057` on 160 nominal sleeves means 160 sleeves are behaving like two bets —
and it is clamped out of the heat formula by `max(scaled, base)` and eight days stale, while the two
`allocate.py` paths that consume it cannot even import. **Cost: days.** Payoff: under the growth
law (Rule 2), genuine independence is the only thing that lets heat rise; a broken measurement means
the desk cannot *earn* more risk even when it deserves it. *Why fourth: it depends on a live ledger,
which depends on items 0-2.*

### 5. Decide what the regime layer is FOR, then wire exactly one of the four.
We have a quantile/SoftMoE router (dark, stale, consumed by nothing, with a dead trigger watching
keys that do not exist), a real Baum-Welch HMM wired to `pf_allocator` but fitted only on XAUUSD
daily closes, a hidden semi-Markov model nothing has ever read, and a threshold hibernator that has
never hibernated anything. **Cost: days, mostly deletion.** Payoff: modest and honest. *Why fifth,
and this is the deliberate demotion: the public evidence that Renaissance ran a regime switcher is
the weakest in the entire set (B.4), the best account of their architecture is a single monolithic
model, and an ex-employee's on-record answer was "simple regression". Extending the existing HMM off
XAUUSD daily closes is the one concrete sub-item worth doing; building a fifth regime machine is
not.*

### 6. Daily broker reconciliation with root-cause on every break.
Their Operations Associate does this for a living `[P]`. We have **121 unmatched deals** the desk
cannot account for. **Cost: one scheduled job.** Payoff: real but bounded at n=212.

### 7. Route more than `market`. **LAST, and deliberately.**
Five algorithms are priced and ranked on every pass and `ROUTABLE_ALGOS = ("market",)`. It is
tempting because it is nearly free to flip. **Do not flip it yet.** The gateway's own comment has
the right reason: the fill surface must be fitted on this box's own fills first, and market impact
is currently `MEASURED_NULL` with a standard error fifty times its slope. Turning on TWAP or iceberg
against an unmeasured impact model is guessing with real money. **This item unblocks only after item
1 has produced a surface.**

### Explicitly NOT worth building

- **Anything justified by the 2-3% vs 0.3% cost comparison** — UNCORROBORATED (B.2).
- **A regime switcher modelled on the Medallion story** — the story is UNCORROBORATED (B.4).
- **Kernel regression or "vector embeddings" because Renaissance allegedly used them** — `[S]`/`[U]`
  (B.5), and Patterson's on-record answer points the other way.
- **Leverage architecture** — the structure is illegal and settled (B.6). Note that this is *not* a
  recommendation to reduce aggressiveness: the desk's heat law and floors are untouched by anything
  here. It is a statement that a specific historical leverage mechanism is unavailable.
- **Chasing trade count for its own sake** — 100,000/day is structural (D.3). The right response to
  a small sample is measurement discipline and longer patience, not manufactured turnover.

---

# SOURCES

**Primary — Renaissance's own words**
- Careers index and all 13 postings: `https://www.rentec.com/Careers.action?jobs=true` and each
  `&selectedPosition=` page (researchScientist, researchEngineer, researchInfraProgrammer,
  dataProgrammer, realtimeTradingProgrammer, financialInfrastructureProgrammer,
  operationsAssociateEquityAnalyst, dataCenterSpecialist, devopsEngineer, systemsEngineerEs,
  systemsEngineerNy, networkEngineer, securityEngineer). Fetched 2026-09-24.
- US Senate hearing transcript, *Abuse of Structured Financial Products: Misusing Basket Options to
  Avoid Taxes and Leverage Limits*, 22 July 2014 —
  `https://www.govinfo.gov/content/pkg/CHRG-113shrg89882/html/CHRG-113shrg89882.htm`
- Senate PSI report of the same title, 22 July 2014 (updated 30 Sept 2014), hsgac.senate.gov
- Nick Patterson, *Talking Machines* podcast ("AI Safety and The Legacy of Bletchley Park"), on
  simple regression as Renaissance's most important statistical tool.

**Academic**
- Bradford Cornell, "Medallion Fund: The Ultimate Counterexample?", *Journal of Portfolio
  Management* 46(4), 2020; SSRN 3504766.

**Secondary reporting**
- Gregory Zuckerman, *The Man Who Solved the Market* (2019), via published reviews and notes —
  Straus and the data plant, "the devil", Laufer's single model, Berlekamp's 1990 redesign and Kelly
  sizing, the Frey mean-reversion core.
- CNBC, CBS News, Forbes, Law360, Institutional Investor — the 2021 ~$7bn IRS settlement and
  Simons's $670m payment.
- Institutional Investor — Medallion +76% versus RIEF −22.6% and RIDA −33.58% in 2020, and the
  ~$11bn of redemptions.
- Wikipedia (Leonard E. Baum; Renaissance Technologies) — Baum's tenure, departure in 1984, and the
  Ax succession.

**This desk, measured 2026-09-24**
`desks/mt5/data/gateway_state.json` · `docs/research/runtime_state.json` ·
`desks/mt5/reports/REGIME_ROUTER.json` · `desks/mt5/research/regime_router.py` ·
`libs/regime/hmm.py` · `libs/regime/transitions.py` · `desks/mt5/research/pf_allocator.py` ·
`desks/mt5/data/regime_state.json` · `desks/mt5/data/regime_state_history.jsonl` ·
`desks/mt5/data/universe/*.parquet` (299 H1 files) · `desks/mt5/data/universe/universe.json` ·
`desks/mt5/research/fetch_universe.py` · `desks/mt5/research/cost_surface.py` ·
`desks/mt5/data/cost_basis_ratchet.json` · `docs/research/COST_TRUTH.md` ·
`desks/mt5/reports/COST_TRUTH.json` · `desks/mt5/reports/EXECUTION_COST_SURFACE.json` ·
`desks/mt5/reports/FILL_RECORDER.json` · `desks/mt5/reports/markout.json` ·
`desks/mt5/mt5desk/markout.py` · `libs/research/fill_markout.py` ·
`desks/mt5/reports/MICROSTRUCTURE.json` · `desks/mt5/mt5desk/execution_registry.py` ·
`desks/mt5/mt5desk/gateway.py` · `desks/mt5/data/cost_truth_quotes.json` ·
`desks/mt5/research/rank_recovery.py` · `data/alpha_registry.sqlite` ·
`desks/mt5/data/effective_breadth.jsonl` · `desks/mt5/mt5desk/decision_core.py` ·
`desks/mt5/mt5desk/independence.py` · `desks/mt5/data/sleeves.json` ·
`desks/mt5/data/sleeve_registry.json` · `libs/data/medallion.py` · `libs/research/bar_span.py` ·
`desks/mt5/tests/test_no_literal_spread_per_lot.py` · `libs/backtest/fills.py` · `libs/costs/params.py`

**Method note.** No file in this repository was modified other than this document. Nothing was
committed. No trading state was touched. Where the commissioning brief stated a number and the disk
disagreed, the disk is reported and the brief's figure is named as its actual source.
