# Quant desk vault — start here

- [[desk_digest]] — auto-generated daily brief: book, validation clocks, open decisions, KPIs
- [[institutional_knowledge]] — the compounding encyclopedia: meta-learnings, alpha map, failure
  taxonomy, stress checklist (the CRO appends here every cycle)
- [[graveyard]] — every rejected hypothesis + why (do_not_repeat; feeds the EV-gate priors)
- `playbooks/` — operational runbooks ([[carry]] first: restart procedure, failure modes, never-dos)
- `research/` — distilled topic notes; [[feed_inbox]] is the auto-filled arXiv queue the CRO
  processes nightly (summarize → EV-score → distill or reject → delete entry)
- `monthly_reviews/` + `decision_reviews/` — filled by the monthly governance cycle
- `KILL_THESIS` / `REPO_MAP` / `GAP_ANALYSIS` — historical audits (repo root)

Ground rules: knowledge lives HERE (markdown, wikilinked); measurable state lives in JSON
(`data/decision_ledger.json`, `data/executive_kpis.json`, `data/data_registry.json`) and is
rendered into [[desk_digest]] daily. Generated files (desk_digest, feed_inbox) are never
hand-edited. Structure grows only when content exists — no empty taxonomy.
