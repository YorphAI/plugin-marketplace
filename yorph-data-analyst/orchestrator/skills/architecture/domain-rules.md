# Domain Sensitivity Rules

Single source of truth for domain-specific guidance. Referenced by `architecture`, `validate`, and `insights` skills. Always loaded by the architecture skill.

When the domain is known (inferred or user-stated), apply the relevant rules throughout the pipeline.

---

## Finance
- Never silently change monetary values
- Track currency and exchange rates explicitly
- Preserve audit trails — every transformation must be traceable
- Revenue recognition rules (e.g., ASC 606) affect timing logic

## Healthcare
- Missing data is often meaningful (not collected, not disclosed, not applicable)
- Apply strict validation on all fields
- Respect privacy constraints — never impute sensitive attributes

## Marketing / CRM
- Expect duplicates and identity ambiguity (same person, multiple records)
- Event order matters — do not sort or deduplicate without preserving sequence
- Attribution logic must be explicit — never assume a default model

## Insurance
- Lifecycle fields (`claim_closed_at`, `payout_amount`) use NULL to encode state — do not impute
- Preserve audit trails and historical record versions
- Deduplication must respect claim vs policy vs incident identity boundaries

## Retail / eCommerce
- Product and catalog data varies by region, channel, and time
- Pricing and promotions are time-bound — overlapping/conflicting records need temporal validation
- Normalize SKUs and variants using controlled vocabularies when available
- Missing inventory/fulfillment fields may reflect upstream system lag, not errors

## Supply Chain / Logistics
- Units of measure must be normalized explicitly (each, case, pallet)
- Partial shipments are common — NULL delivery dates often mean "not yet delivered"
- Location identifiers and timezones are critical for correctness
- Preserve event order and shipment lineage

## Human Resources
- Fields like `termination_date`, `manager_id`, `compensation_end_date` encode state via NULL
- Do not impute sensitive personal or employment attributes
- Historical accuracy is more important than completeness

## Manufacturing
- Batch, lot, and run identifiers define data lineage — must not be altered
- Sensor readings include noise and calibration drift
- Quarantine anomalous production runs instead of deleting
- Time alignment across machines is critical

## Government / Public Sector
- Data formats often follow mandated standards — do not deviate
- Do not silently correct values without preserving originals
- Missing data may reflect legal or procedural constraints

## IoT / Sensors
- Expect noise as baseline — not every anomaly is a data quality issue
- Detect sensor drift (gradual calibration shift over time)
- High-frequency anomalies are common and often legitimate
