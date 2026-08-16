# DATA GOVERNANCE — Institutional Discipline Without Institutional Bills

Every observation in the lake carries provenance. Raw responses are immutable forever.
Derived layers are built only from canonical, point-in-time-checked data.

## Raw vault record schema
| field | meaning |
|---|---|
| event_time | when the observed phenomenon occurred |
| published_time | when the source published it |
| available_time | when it became retrievable |
| ingested_time | when we stored it |
| source | publisher (e.g. FRED, SGE, Swiss Customs) |
| source_version | API/feed/edition version |
| revision_id | revision or vintage identifier |
| raw_hash | sha256 of the raw payload |
| license | usage rights |
| quality_flags | gaps, revisions, anomalies |
| provenance | exact URL/endpoint + retrieval context |

ALFRED preserves historical vintages/revisions explicitly (FRED current-vintage lake already
built — `data/lake/fred_*.parquet`, 1962–2026; ALFRED key = point-in-time upgrade path).
CFTC provides historical COT via its public reporting environment.

## Research lake stack (no institutional bills)
Immutable compressed **Parquet** → **DuckDB** for research analytics → **PostgreSQL** for
transactional/control state → **MLflow** for experiment/dataset/model lineage (registry +
version relationships). No Spark/K8s/message clusters: at our capital size operational
simplicity is the higher-ROI choice.

## Research method (institutional)
- Every idea gets a unique **hypothesis ID** before confirmation testing.
- Record every parameter/window/instrument/model tried; failures become a permanent searchable
  **graveyard**.
- Untouched chronological confirmation; realistic bid/ask costs; block/bootstrap dependence
  tests; regime splits; negative controls; portfolio-level incremental value.
- **The model invents hypotheses; it cannot decide whether its own hypothesis passed.**
  Promotion authority is deterministic (gates → WF OOS → cost stress → shadow forward →
  portfolio contribution).
- Multiple-testing accounting so a huge search machine does not manufacture false discoveries.

## Data lifecycle
DISCOVERED → INGESTED → QUALITY-PASSED → RESEARCH-USEFUL → OOS-INCREMENTAL → FORWARD-INCREMENTAL → CORE
Demotion is allowed and recorded.

## ROI of data
ROI_data = Δforward net economic value / (acquisition + compute + model + maintenance cost).
Every dataset, miner, model and feature must justify its cost.