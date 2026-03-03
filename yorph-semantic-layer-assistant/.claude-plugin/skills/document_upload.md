# Skill: Document Upload & URL Context

This skill governs how the orchestrator handles user-provided documentation. Documents and URLs dramatically improve the quality of the semantic layer by giving the agents documented business meaning — not just what the data looks like, but what it means.

---

## When to trigger this skill

- User mentions they have a data dictionary, business glossary, or SaaS context doc
- User uploads a file during the conversation
- User pastes a URL to documentation (Confluence, Notion, GitHub, internal wiki, etc.)
- User mentions column/table names that don't match what's in the warehouse (may need a data dictionary to explain naming)
- After profiling, Claude detects columns with cryptic names (e.g. `f_amt`, `cd_typ`) where documentation would help

---

## Conversation flow

### If user proactively uploads a file or URL

Acknowledge quickly, confirm what you're doing, then process:

```
Got it — I'll extract the column definitions, metric definitions, and business rules
from this document and use them to guide how the agents name and define everything
in your semantic layer.

[call process_document or fetch_url_context]

Here's what I found:
- X table descriptions
- Y column definitions (with business names where available)
- Z metric definitions
- Any conflicts between the documentation and the actual data

These will now automatically be applied when I build your profiles...
```

### If user hasn't provided documents — prompt at Step 3

Ask conversationally, not as a form:

```
Before we build the semantic layer, do you have any of these available?

📄 A **data dictionary** — column-by-column descriptions of what the data means
📊 A **SaaS app context doc** — e.g. "here's how Stripe structures its data"
📐 An **existing semantic layer** — a dbt schema.yaml, LookML file, or similar
🔗 A **documentation URL** — Confluence, Notion, GitHub wiki, internal docs

These aren't required, but they make a big difference. Without them, I'll infer
column meanings from names and statistics — which works well but may miss business
context like "amt means pre-tax invoice amount in GBP".

If you have something, just upload it or paste a link.
If not, just say "no" and we'll proceed with inference.
```

---

## Processing behaviour

### Files — call `process_document`
```
process_document(
  file_path="<absolute path to uploaded file>",
  document_type="<data_dictionary | saas_context | business_glossary | existing_semantic_layer | schema_docs>"
)
```

Supported formats:
| Format | Best for |
|--------|----------|
| `.pdf` | Data dictionaries, business specifications |
| `.docx` | Business glossaries, process documentation |
| `.xlsx` / `.csv` | Column-level data dictionaries (table, column, description format) |
| `.yaml` / `.json` | dbt schema.yaml, dbt manifest.json, LookML, OSI spec |
| `.md` / `.txt` | README files, schema documentation |

### URLs — call `fetch_url_context`
```
fetch_url_context(
  url="<the URL>",
  document_type="<type>"
)
```

Supported sources:
| Source | Notes |
|--------|-------|
| Confluence | Strips nav chrome, extracts page content |
| Notion (public) | Extracts page body |
| GitHub README / Wiki | Extracts markdown content |
| GitBook | Extracts page section |
| Raw JSON endpoint | Parses directly (e.g. dbt manifest.json on S3) |
| Raw YAML endpoint | Parses directly |
| Any HTML page | Best-effort content extraction |

---

## After processing — what to tell the user

Show a friendly summary of what was extracted. Focus on what's useful, not just counts:

```
Here's what I pulled from your data dictionary:

✅ 3 table descriptions — orders, customers, order_items
✅ 47 column definitions with business names
  - e.g. `f_amt` → "Fulfillment Amount (pre-tax, USD)"
  - e.g. `cd_typ` → "Customer Type" (valid values: enterprise, SMB, consumer)
✅ 8 metric definitions
  - ARR, MRR, Churn Rate, CAC, LTV, NPS, CSAT, GMV
✅ 4 business rules
  - "Revenue is only recognized when order_status = 'fulfilled'"
  - etc.

⚠ 2 conflicts found:
  - `status` column: documentation lists valid values ['pending', 'paid', 'refunded']
    but the data also contains 'cancelled' and 'draft' — I'll flag this for review.
  - `customer_id` column: documented as a Salesforce Account ID (18-char string)
    but the profile shows numeric values — may be a legacy column naming issue.

I'll now use all of this when building your semantic layer. The agents will use your
business names and metric definitions as the primary source of truth.
```

---

## When there are conflicts between documentation and data

Use the conflict resolution templates in `prompts/clarification.md`. Key principle:

> **Documentation wins for naming and definitions. Profiled data wins for statistics. When they conflict on facts (like valid values or data types), ask the user.**

Examples:
- Documentation says `status` can be 'pending', 'paid', 'refunded' — but data also has 'cancelled' → ask
- Documentation says `amount` is GBP but data shows $ symbols → ask
- Documentation references a table that doesn't exist in the warehouse → flag (may be deprecated or renamed)
- Documentation lists a metric with a formula that references a column not in the warehouse → flag

---

## How document context affects agents

Once documents are loaded, agents receive **enriched profiles** — each column includes:

```
`f_amt` (NUMBER) → 📄 "Fulfillment Amount"
  Meaning 📄: Pre-tax invoice amount in USD. Excludes shipping and taxes.
  FK → invoices [documented]
  Stats: null=0.1% | ~distinct=45,231 | range=[0.01, 89,432.00]
  Samples: 249.99, 1049.00, 32.50
```

The `📄` icon tells agents this came from documentation (high confidence), vs `~` which means inferred (medium confidence).

Agents must:
- **Use documented business names** for all measure labels and entity names in their output
- **Use documented metric formulas** when available, rather than inferring from column names
- **Apply documented business rules** as filters on measures (e.g. revenue filter on status)
- **Cite the documentation source** when making claims about column meaning
- **Flag conflicts** rather than silently picking one interpretation

---

## Multiple documents

Users can upload multiple documents. They are all merged:
- If two documents define the same column differently → surface the conflict
- If one document has table descriptions and another has metric definitions → both apply
- Document context is cumulative across the session

Prompt the user after each document: "Do you have any other documents to add, or shall we proceed?"
