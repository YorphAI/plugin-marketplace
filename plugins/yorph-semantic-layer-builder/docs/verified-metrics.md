# Verified Metrics Protocol

This document defines how user-provided metrics are handled. Referenced by any agent that works with measures.

---

## User-provided metrics are ground truth

Metrics the user described during onboarding are stored as `user_provided_metrics[]` and carry `confidence=VERIFIED`, `source=user_provided`.

## Rules

1. **Never drop a verified metric.** It appears in every tier of output (MB-1, MB-2, MB-3) regardless of what column-name heuristics would say.
2. **Use the user's exact formula.** If they said `ARR = SUM(mrr * 12) WHERE status = 'active'`, implement that — don't reinterpret.
3. **Use the user's label.** The metric name they provided is the canonical business name.
4. **Map to the warehouse.** Verify the source table(s) and column(s) exist. If they don't, escalate — don't silently drop the metric.
5. **Process first.** In any agent that discovers or ranks measures, process `user_provided_metrics[]` before scanning columns.

## Standard exclusions are hard rules

Filters provided during onboarding are stored as `standard_exclusions[]`. These:
- Appear in `business_rules[]` marked `[USER CONFIRMED]`
- Are referenced in every measure that touches the relevant table
- Cannot be softened, reinterpreted, or omitted
