# Yorph Semantic Layer Builder

A Claude Code plugin that builds production-grade semantic layers from your data warehouse — automatically.

Connect your warehouse, answer a few questions, and get a fully structured semantic layer with documented entities, validated joins, certified metrics, business rules, and a plain-English companion document your team can actually read.

> **Status:** Beta. Works end-to-end, rough edges exist. Review generated output before deploying to production.

---

## What this plugin does

Given a connected warehouse, the plugin:

1. **Profiles your schema** — scans every table, detects column roles (measures, dimensions, foreign keys, timestamps, flags), and builds compact statistical summaries
2. **Asks you the right questions** — entity disambiguation, business exclusions, key KPIs, data gotchas — all as clickable prompts, not free-form typing
3. **Runs a multi-agent analysis DAG** — 10 specialized agents analyze your schema in parallel and cross-validate each other's outputs
4. **Surfaces conflicts with evidence** — when agents disagree, you see the actual FK match rates, cardinality data, and quality flags before making a call
5. **Gives you three design options** — conservative (strict joins, core KPIs), comprehensive (full coverage), or balanced (recommended for most teams)
6. **Generates your semantic layer** — in the format your stack needs, plus a plain-English `_readme.md` explaining every metric, join decision, and business rule

---

## Requirements

- [Claude Code](https://claude.ai/code)
- Python ≥ 3.10 (dependencies are installed automatically on first run)
- One or more supported data warehouses (see below)

---

## Installation

Install via the [Yorph plugin marketplace](https://github.com/YorphAI/plugin-marketplace) or [download the zip](https://github.com/YorphAI/plugin-marketplace/raw/main/yorph-semantic-layer-builder.zip) and upload it directly in Claude Code (**Customize → + next to Personal Plugins**).

---

## Supported warehouses

| Warehouse | Auth |
|---|---|
| Snowflake | Key pair (recommended — MFA-compatible) |
| BigQuery | Application Default Credentials or service account JSON |
| Redshift | AWS profile, access key/secret, or IAM role |
| SQL Server / Azure SQL | SQL auth or Windows auth |
| Supabase | OAuth or project ref + password |
| PostgreSQL | Password (SSL: prefer/require/disable) |
| Amazon S3 | Access key/secret, AWS profile, or IAM role |
| Google Cloud Storage | ADC or service account JSON |

You can connect up to two sources in a single session. Cross-source joins are discovered and flagged as requiring federation or ETL at query time.

---

## How it works

### Agents

The plugin runs a dependency DAG of 10 specialized agents organized into two tiers.

**Tier 0 — Foundation (run in parallel, no dependencies):**

| Agent | What it does |
|---|---|
| **Schema Annotator** | Classifies tables by business domain, tags column semantic roles (measure, FK, dimension, timestamp, flag), ranks measure candidates by confidence |
| **Quality Sentinel** | Flags data quality issues: high null rates, stale columns, constant columns, negative values in revenue columns, encoded nulls |
| **SCD Detector** | Detects slowly-changing dimensions (Type 1/2/3) and flags joins that need temporal filters to avoid metric inflation |

**Tier 1 — Analysis (run in parallel, receive Tier 0 outputs):**

| Agent | What it does |
|---|---|
| **Join Validator** (×3 personas) | Discovers joins by exhaustive value-overlap checks across all ID-like columns — not just name matching. JV-1 (Strict): confirmed N:1 only. JV-2 (Explorer): all plausible joins. JV-3 (Trap Hunter): validated joins + fan-out/chasm trap detection |
| **Measures Builder** (×3 personas) | Builds metric sets at different coverage levels. MB-1 (Minimalist): 5–15 core KPIs. MB-2 (Analyst): all derivable metrics. MB-3 (Strategist): core + top derived, grouped by domain |
| **Grain Detector** (×3 personas) | GD-1 (Purist): atomic grain. GD-2 (Pragmatist): reporting grain. GD-3 (Architect): atomic + pre-aggregated mart |
| **Business Rules** | Applies your stated exclusions (e.g. "exclude internal accounts") as hard filters on every affected measure |
| **Glossary Builder** | Builds a business term glossary and surfaces open questions for ambiguities it can't resolve from data alone |
| **Time Intelligence** | Detects time dimensions, generates period-over-period calculations (MTD, YTD, MoM, YoY, rolling windows) |
| **Dimension Hierarchies** | Detects parent-child drill paths (year → quarter → month → day) and validates 1:many integrity at each level |

After both tiers complete, an automated cross-validation step checks for: SCD joins missing temporal filters, measures built on quality-flagged columns, metrics that depend on rejected joins, and hierarchy warnings on Type-2 dimensions.

### What you choose

You don't have to pick a single agent output. At the end of analysis, you choose a posture for joins, measures, and grain independently — or mix recommendations. You get three pre-packaged designs (conservative, comprehensive, balanced) plus the ability to adjust any element.

---

## Output

Every run produces two files in `~/.yorph/output/`:

**Your chosen technical format:**

| Format | Best for |
|---|---|
| `dbt` | Teams already using dbt — generates `schema.yaml` + `metrics.yaml` (MetricFlow compatible) |
| `Snowflake` | Snowflake Cortex Analyst — ready-to-deploy semantic layer YAML |
| `JSON` | Any BI tool or custom pipeline |
| `YAML` | Generic, human-readable, easy to adapt |
| `OSI Spec` | Cube, MetricFlow, and other headless BI frameworks |
| `All formats` | Generates everything above |

**Always included — a companion `_readme.md`:**

A plain-English document covering every entity (what it is, its grain, its source), every metric (formula, filters, business rules applied, additivity, complexity), every join (cardinality, FK match rate, any caveats), open questions to revisit, and a business glossary. Designed so a new analyst — or a stakeholder — can understand the semantic layer without reading any YAML.

---

## Credentials & security

Credentials are stored in `~/.yorph/.env` and read by the plugin's Python runtime — **they are not passed to the language model**. The runtime uses read-only connections: only `SELECT` and `WITH` statements are permitted; write and DDL keywords are blocked at the server level and cannot be overridden.

That said: **only approve tool calls that you'd be comfortable with**. Review what the plugin is about to execute before approving. If a permission prompt looks unexpected, deny it and ask what's happening.

For Snowflake specifically, use key-pair auth — TOTP/MFA codes expire in 30 seconds and can't be stored. The plugin walks you through generating a key pair on first connect.

---

## Iteration mode

If you've already built a semantic layer, the plugin detects it at session start and offers to load and extend it rather than starting over. Iteration mode re-runs only the agents affected by what changed — adding a new table re-profiles just that table and re-runs affected agents; correcting a metric formula only re-runs the Measures Builder and Glossary. Validated work from the original build is preserved.

---

## Limitations

- Output is AI-generated. Validate measures against known numbers before relying on them in production dashboards.
- Cross-source joins (when two warehouses are connected) require federation or ETL at query time — the plugin flags these but can't execute them for you.
- S3 and GCS are file-based sources (CSV, Parquet, JSON) — not SQL warehouses. Join discovery and profiling work differently than for SQL sources.
- Snowflake key-pair setup requires terminal access and a one-time Snowflake admin action.

---

## Contributing

Issues and PRs welcome. If you hit a connector bug, include your warehouse type, the error message, and (if possible) a sanitized schema description. Don't include credentials or real data samples.
