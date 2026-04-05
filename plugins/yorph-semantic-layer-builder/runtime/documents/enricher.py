"""
Profile enricher — merges DocumentContext into column/table profiles.

This is the bridge between "what we scraped from the warehouse" and
"what the user told us the data means". The enriched profile is what
all 9 agents actually work from.

Enrichment adds:
  - business_name: human label from document (overrides inferred name)
  - description: documented meaning of the column
  - documented_grain: the stated grain of the table
  - source_system: which SaaS/system produced this table
  - documented_metrics: metric definitions that reference this table
  - business_rules: rules that apply to this table/column
  - join_hints: documented join relationships
  - conflicts: cases where documentation contradicts the profiled data

Design principle:
  Documentation ENRICHES inferences, it does not silently replace them.
  When doc and data AGREE → agent uses doc label with high confidence.
  When doc and data CONFLICT → flag it, surface to user.
  When doc has info the profile doesn't → add it with provenance = "documented".
  When profile has info doc doesn't → keep it with provenance = "inferred".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..profiler.base import ColumnProfile, TableProfile
from .context import (
    DocumentContext, MergedDocumentContext,
    ColumnDefinition, TableDefinition, MetricDefinition,
    BusinessRule, JoinHint,
    load_all_document_contexts,
)


# ── Enriched column profile ─────────────────────────────────────────────────────

@dataclass
class EnrichedColumnProfile:
    """
    A ColumnProfile extended with DocumentContext intelligence.
    Agents work from this — it has both statistical and semantic context.
    """
    # Original statistical profile
    profile: ColumnProfile

    # Documented semantic layer (may be None if not in any document)
    doc_definition: ColumnDefinition | None = None

    # Resolved values (doc wins over inference when available)
    business_name: str | None = None        # human-readable label
    description: str | None = None          # what this column means
    is_pii: bool = False                    # marked as PII in documentation
    valid_values: list[str] = field(default_factory=list)   # documented enum values
    is_foreign_key: bool = False
    references_table: str | None = None

    # Provenance tags — agents cite these
    business_name_source: str = "inferred"  # "documented" | "inferred"
    description_source: str = "inferred"

    # Conflicts — where doc and data disagree
    conflicts: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.profile.name

    @property
    def data_type(self) -> str:
        return self.profile.data_type

    def to_agent_summary(self) -> str:
        """
        Compact agent-facing summary combining statistical + semantic context.
        This is what agents read when reasoning about a column.
        """
        parts = [f"`{self.name}` ({self.data_type})"]

        if self.business_name and self.business_name.lower() != self.name.lower():
            src = "📄" if self.business_name_source == "documented" else "~"
            parts[0] += f" → {src} \"{self.business_name}\""

        if self.description:
            src = "📄" if self.description_source == "documented" else "~"
            parts.append(f"  Meaning {src}: {self.description}")

        if self.is_pii:
            parts.append("  ⚠ PII — exclude from samples and context")

        if self.is_foreign_key and self.references_table:
            parts.append(f"  FK → {self.references_table}")

        if self.valid_values:
            parts.append(f"  Valid values: {', '.join(self.valid_values[:10])}")

        # Key stats
        stat_parts = [f"null={self.profile.pct_null:.1f}%", f"~distinct={self.profile.approx_distinct:,}"]
        if self.profile.min_numeric is not None:
            stat_parts.append(f"range=[{self.profile.min_numeric}, {self.profile.max_numeric}]")
        if self.profile.avg_len is not None:
            stat_parts.append(f"avg_len={self.profile.avg_len:.0f}")
        parts.append(f"  Stats: {' | '.join(stat_parts)}")

        if self.profile.sample_values:
            samples = ", ".join(str(v) for v in self.profile.sample_values[:3])
            parts.append(f"  Samples: {samples}")

        if self.conflicts:
            for c in self.conflicts:
                parts.append(f"  ⚠ CONFLICT: {c}")

        return "\n".join(parts)


@dataclass
class EnrichedTableProfile:
    """
    A TableProfile extended with DocumentContext intelligence.
    """
    # Original statistical profile
    profile: TableProfile

    # Documented semantic layer
    doc_definition: TableDefinition | None = None

    # Resolved values
    description: str | None = None
    source_system: str | None = None
    documented_grain: str | None = None

    # Enriched columns
    columns: list[EnrichedColumnProfile] = field(default_factory=list)

    # Metrics that reference this table (from all docs)
    relevant_metrics: list[MetricDefinition] = field(default_factory=list)

    # Business rules that apply to this table
    relevant_rules: list[BusinessRule] = field(default_factory=list)

    # Documented joins involving this table
    join_hints: list[JoinHint] = field(default_factory=list)

    # Conflicts
    conflicts: list[str] = field(default_factory=list)

    @property
    def table_name(self) -> str:
        return self.profile.table_name

    @property
    def schema_name(self) -> str:
        return self.profile.schema_name

    def to_agent_summary(self) -> str:
        """
        Full enriched table summary for agents. Combines stats + semantics.
        This is richer than TableProfile.to_context_summary() alone.
        """
        lines = [
            f"## {self.schema_name}.{self.table_name}",
            f"Rows: {self.profile.total_rows:,} | Profiled: {self.profile.profiled_at[:10]}",
        ]

        if self.description:
            src = "📄" if self.doc_definition else "~"
            lines.append(f"Description {src}: {self.description}")

        if self.source_system:
            lines.append(f"Source system: {self.source_system}")

        if self.documented_grain:
            lines.append(f"Documented grain 📄: {self.documented_grain}")

        if self.relevant_rules:
            lines.append("\n**Business Rules (from documentation):**")
            for r in self.relevant_rules:
                lines.append(f"- 📄 {r.rule}")

        if self.join_hints:
            lines.append("\n**Documented Joins:**")
            for j in self.join_hints:
                other = j.right_table if j.left_table.lower() == self.table_name.lower() else j.left_table
                card = f" [{j.cardinality}]" if j.cardinality else ""
                lines.append(f"- 📄 → `{other}` on `{j.join_key}`{card}")

        if self.relevant_metrics:
            lines.append("\n**Metrics sourced from this table (from documentation):**")
            for m in self.relevant_metrics:
                cert = " ✓" if m.is_certified else ""
                lines.append(f"- 📄 **{m.business_name}**{cert}: {m.description or m.formula or ''}")

        if self.conflicts:
            lines.append("\n**⚠ Documentation vs Data Conflicts:**")
            for c in self.conflicts:
                lines.append(f"- {c}")

        lines.append("\n**Columns:**")
        for col in self.columns:
            lines.append(col.to_agent_summary())

        return "\n".join(lines)


# ── Enricher ───────────────────────────────────────────────────────────────────

class ProfileEnricher:
    """
    Merges a list of TableProfiles with MergedDocumentContext to produce
    EnrichedTableProfiles that the 9 agents work from.
    """

    def __init__(self, doc_context: MergedDocumentContext):
        self.docs = doc_context

    def enrich_all(self, profiles: list[TableProfile]) -> list[EnrichedTableProfile]:
        return [self.enrich_table(p) for p in profiles]

    def enrich_table(self, profile: TableProfile) -> EnrichedTableProfile:
        table_name = profile.table_name
        table_doc = self.docs.get_table(table_name)

        # Table-level enrichment
        description = None
        source_system = None
        documented_grain = None
        table_conflicts: list[str] = []

        if table_doc:
            description = table_doc.description
            source_system = table_doc.source_system
            documented_grain = table_doc.grain_description

        # Metrics referencing this table
        relevant_metrics = [
            m for m in self.docs.all_metrics()
            if m.source_table and m.source_table.lower() == table_name.lower()
        ]

        # Business rules for this table
        relevant_rules = self.docs.rules_for_table(table_name)

        # Join hints involving this table
        join_hints = [
            j for j in self.docs.join_hints
            if j.left_table.lower() == table_name.lower()
            or j.right_table.lower() == table_name.lower()
        ]

        # Enrich columns
        enriched_cols = [
            self.enrich_column(col, table_name)
            for col in profile.columns
        ]

        # Check for documented columns that are missing from the profile
        documented_cols = {
            cd.column_name.lower()
            for cd in (self.docs.column_index.values())
            if cd.table_name.lower() == table_name.lower()
        }
        profiled_cols = {col.name.lower() for col in profile.columns}
        missing_in_profile = documented_cols - profiled_cols
        if missing_in_profile:
            table_conflicts.append(
                f"Documentation references columns not found in profile: "
                f"{', '.join(sorted(missing_in_profile))} — may be excluded (PII) or renamed."
            )

        return EnrichedTableProfile(
            profile=profile,
            doc_definition=table_doc,
            description=description,
            source_system=source_system,
            documented_grain=documented_grain,
            columns=enriched_cols,
            relevant_metrics=relevant_metrics,
            relevant_rules=relevant_rules,
            join_hints=join_hints,
            conflicts=table_conflicts,
        )

    def enrich_column(self, col: ColumnProfile, table_name: str) -> EnrichedColumnProfile:
        col_doc = self.docs.get_column(table_name, col.name)
        conflicts: list[str] = []

        business_name = None
        description = None
        is_pii = False
        valid_values: list[str] = []
        is_foreign_key = False
        references_table = None
        business_name_source = "inferred"
        description_source = "inferred"

        if col_doc:
            business_name = col_doc.business_name
            description = col_doc.description
            is_pii = col_doc.is_pii
            valid_values = col_doc.valid_values or []
            is_foreign_key = col_doc.is_foreign_key
            references_table = col_doc.references_table

            if col_doc.business_name:
                business_name_source = "documented"
            if col_doc.description:
                description_source = "documented"

            # Conflict: documented valid values vs profiled sample values
            if valid_values and col.sample_values:
                sample_set = {str(v).strip().lower() for v in col.sample_values}
                doc_set = {v.strip().lower() for v in valid_values}
                unexpected = sample_set - doc_set
                if unexpected and len(unexpected) < 5:
                    conflicts.append(
                        f"Sample contains values not in documented valid values: "
                        f"{', '.join(repr(v) for v in unexpected)}. "
                        f"Either the documentation is incomplete or there's dirty data."
                    )

            # Conflict: documented as numeric but profile is string
            if col_doc.data_type_note and "int" in col_doc.data_type_note.lower():
                is_string = any(t in col.data_type.upper() for t in ["VARCHAR", "TEXT", "STRING", "CHAR"])
                if is_string and col.pct_numeric_like and col.pct_numeric_like < 80:
                    conflicts.append(
                        f"Documentation says this should be numeric ({col_doc.data_type_note}) "
                        f"but only {col.pct_numeric_like:.0f}% of values look numeric. "
                        f"May be stored as strings — verify before defining measures."
                    )

        else:
            # No documentation — infer business name from column name heuristics
            business_name = _humanize_column_name(col.name)

        return EnrichedColumnProfile(
            profile=col,
            doc_definition=col_doc,
            business_name=business_name,
            description=description,
            is_pii=is_pii,
            valid_values=valid_values,
            is_foreign_key=is_foreign_key,
            references_table=references_table,
            business_name_source=business_name_source,
            description_source=description_source,
            conflicts=conflicts,
        )

    def undocumented_metrics(self) -> list[MetricDefinition]:
        """
        Return metrics that appear in documentation but have no obvious source column in profiles.
        Agents use this to flag 'defined but not yet sourced' metrics.
        """
        # We'd need profiles to check — return all metrics for now,
        # and let agents filter. This is a starting point.
        return self.docs.all_metrics()


# ── Column name humaniser ──────────────────────────────────────────────────────

def _humanize_column_name(name: str) -> str:
    """
    Convert snake_case column names to human-readable labels.
    Used as a fallback when no documentation exists.

    Examples:
      customer_id       → Customer ID
      total_revenue     → Total Revenue
      created_at        → Created At
      is_refunded       → Is Refunded
      pct_discount      → % Discount
    """
    label = name

    # Handle common prefixes/suffixes
    prefixes = {"is_": "Is ", "has_": "Has ", "pct_": "% ", "num_": "# "}
    suffixes = {"_id": " ID", "_at": " At", "_ts": " Timestamp", "_amt": " Amount",
                "_ct": " Count", "_cnt": " Count", "_qty": " Quantity"}

    for prefix, replacement in prefixes.items():
        if label.lower().startswith(prefix):
            label = replacement + label[len(prefix):]
            break

    for suffix, replacement in suffixes.items():
        if label.lower().endswith(suffix):
            label = label[: -len(suffix)] + replacement
            break

    # snake_case → Title Case
    label = label.replace("_", " ").title()
    return label


# ── Convenience loader ─────────────────────────────────────────────────────────

def build_enriched_profiles(profiles: list[TableProfile]) -> list[EnrichedTableProfile]:
    """
    Load all saved DocumentContexts from disk, merge them, and enrich
    the given list of TableProfiles.

    This is called by agents at the start of the build phase.
    """
    contexts = load_all_document_contexts()
    merged = MergedDocumentContext(contexts)
    enricher = ProfileEnricher(merged)
    return enricher.enrich_all(profiles)


def enriched_context_summary(
    enriched_profiles: list[EnrichedTableProfile],
    doc_context: MergedDocumentContext,
    batch_index: int = 0,
    batch_size: int = 100,
) -> str:
    """
    Returns a combined context string for a batch of enriched tables
    plus any document-defined metrics not yet sourced to a table.
    """
    start = batch_index * batch_size
    batch = enriched_profiles[start: start + batch_size]
    total_batches = (len(enriched_profiles) + batch_size - 1) // batch_size

    header = (
        f"# Enriched Profiles — Batch {batch_index + 1} of {total_batches} "
        f"({len(batch)} tables)\n"
    )
    if total_batches > 1:
        header += (
            f"> {len(enriched_profiles)} tables total. "
            f"Call get_context_summary(batch_index={batch_index + 1}) for next batch.\n"
        )

    # Document-defined metrics not attributed to any table in this batch
    batch_tables = {ep.table_name.lower() for ep in batch}
    undocumented = [
        m for m in doc_context.all_metrics()
        if not m.source_table or m.source_table.lower() not in batch_tables
    ]

    parts = [header]
    for ep in batch:
        parts.append(ep.to_agent_summary())

    if undocumented and batch_index == 0:
        parts.append("\n## 📄 Metrics Defined in Documentation (source table not yet identified)")
        for m in undocumented:
            cert = " ✓ certified" if m.is_certified else ""
            parts.append(f"- **{m.business_name}** (`{m.name}`){cert}")
            if m.description:
                parts.append(f"  {m.description}")
            if m.formula:
                parts.append(f"  Formula: `{m.formula}`")

    if doc_context.is_empty():
        parts.append(
            "\n> ℹ No documents loaded. Column semantics are inferred from names and profiles only. "
            "Upload a data dictionary or provide a documentation URL to improve accuracy."
        )

    return "\n\n".join(parts)
