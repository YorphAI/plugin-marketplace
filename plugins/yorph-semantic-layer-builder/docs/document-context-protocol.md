# Document Context Protocol

This document defines how agents interpret enriched profile tags. Referenced by any agent that reads column or table profiles.

---

## Tag meanings

Your context includes **enriched profiles** — column and table entries may carry tags indicating their source:

- `📄 documented` — came from a user-uploaded document or URL. **High confidence.** Use as truth.
- `~ inferred` — inferred from column names and statistics. **Medium confidence.** Validate before relying on it.
- `⚠ CONFLICT` — documentation and data disagree. **Surface to the user** before making any decision that depends on this entry.

## Priority order

When multiple sources provide information about the same column or table:

1. `📄 documented` — highest priority. Use exactly as stated.
2. `~ inferred` — working hypothesis. Validate statistically before including in output.
3. `⚠ CONFLICT` — do not silently pick a side. Present both the documented and inferred values to the user and ask them to resolve.

## Business names

- If a column is documented as `"Gross Revenue"`, that is the canonical label — not `sum_revenue` or `total_f_amt`.
- If a metric formula is documented, generate SQL implementing that exact formula — not your own interpretation.
- Documented business names always override inferred names.

## SQL generation

All SQL is generated **on the fly** based on the actual column and table names in the enriched profiles. Example queries in agent prompts show **patterns only** — you generate the real SQL using the actual schema you're working with.
