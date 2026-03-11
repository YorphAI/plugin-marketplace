"""
DocumentContext — the structured output of document/URL ingestion.

This is the currency that flows between the document processor and the
9 agents. It is NOT raw text — it is parsed, structured intelligence
that agents can merge with column profiles to reason more accurately.

Design principle:
  Column profiles tell you WHAT the data looks like.
  DocumentContext tells you WHAT THE DATA MEANS.

When both are available, agents prioritise DocumentContext for semantic
decisions (naming, descriptions, metric definitions, business rules)
and profiles for statistical decisions (grain, cardinality, nulls).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


# ── Sub-structures ─────────────────────────────────────────────────────────────

@dataclass
class TableDefinition:
    """Human-provided description of a table's business meaning."""
    table_name: str
    description: str | None = None
    source_system: str | None = None          # e.g. "Shopify", "Salesforce", "Stripe"
    grain_description: str | None = None      # e.g. "one row per order"
    table_type: str | None = None             # "fact", "dimension", "slowly_changing_dimension"
    primary_key: str | None = None            # primary key column name
    owner: str | None = None                  # team or person responsible
    notes: str | None = None


@dataclass
class ColumnDefinition:
    """Human-provided description of a specific column's business meaning."""
    table_name: str
    column_name: str
    business_name: str | None = None          # human label, e.g. "Gross Revenue"
    description: str | None = None
    data_type_note: str | None = None         # e.g. "USD, 2 decimal places"
    semantic_type: str | None = None          # "dimension", "time_dimension", "entity", "measure"
    time_granularity: str | None = None       # "day", "week", "month", "quarter", "year" (for time dims)
    is_pii: bool = False
    is_foreign_key: bool = False
    references_table: str | None = None       # FK target table
    valid_values: list[str] = field(default_factory=list)   # documented enum values
    notes: str | None = None


@dataclass
class MeasureDefinition:
    """
    An additive, aggregatable measure defined on a fact table or semantic model.
    Measures are the building blocks of metrics — metrics reference measures.

    e.g. dbt MetricFlow: measures block, LookML: measure type fields.
    """
    name: str
    table_name: str                           # which semantic model / fact table it lives on
    aggregation: str                          # SUM, COUNT, COUNT_DISTINCT, AVG, MIN, MAX, MEDIAN
    expression: str | None = None            # SQL expression, e.g. "amount" or "CASE WHEN paid THEN amount END"
    description: str | None = None
    label: str | None = None                 # human-readable name
    filters: list[str] = field(default_factory=list)    # e.g. ["status = 'completed'"]
    non_additive_dimension: str | None = None  # for semi-additive measures (e.g. balance → date)


@dataclass
class MetricDefinition:
    """A documented metric or KPI defined by the business."""
    name: str
    business_name: str                        # "Monthly Recurring Revenue"
    description: str | None = None
    metric_type: str | None = None           # "simple", "derived", "ratio", "cumulative", "conversion"
    formula: str | None = None               # e.g. "SUM(mrr) WHERE status = 'active'"
    measure_name: str | None = None          # for simple metrics: which measure this wraps
    numerator_measure: str | None = None     # for ratio metrics
    denominator_measure: str | None = None   # for ratio metrics
    source_table: str | None = None
    source_column: str | None = None
    aggregation: str | None = None            # SUM, COUNT, RATIO, etc.
    filters: list[str] = field(default_factory=list)   # e.g. ["status = 'completed'"]
    dimensions: list[str] = field(default_factory=list)  # dimensions this metric can be sliced by
    owner: str | None = None                 # Finance, Product, etc.
    domain: str | None = None               # Revenue, Customer, Marketing, etc.
    is_certified: bool = False               # explicitly marked as authoritative
    notes: str | None = None




@dataclass
class BusinessRule:
    """A documented business logic rule that affects how data should be read."""
    rule: str                                 # e.g. "Revenue only counts when status='paid'"
    affects_tables: list[str] = field(default_factory=list)
    affects_columns: list[str] = field(default_factory=list)
    affects_metrics: list[str] = field(default_factory=list)
    source: str | None = None               # where this rule came from in the doc


@dataclass
class GlossaryTerm:
    """A business glossary entry."""
    term: str
    definition: str
    synonyms: list[str] = field(default_factory=list)
    related_tables: list[str] = field(default_factory=list)
    related_columns: list[str] = field(default_factory=list)


@dataclass
class JoinHint:
    """An explicitly documented join relationship."""
    left_table: str
    right_table: str
    join_key: str
    cardinality: str | None = None           # "1:many", "1:1", "many:many"
    description: str | None = None
    is_primary_path: bool = True             # is this the preferred join path?


# ── Main DocumentContext ────────────────────────────────────────────────────────

@dataclass
class DocumentContext:
    """
    Structured semantic intelligence extracted from a user-uploaded document or URL.

    One DocumentContext per source document. Multiple DocumentContexts are merged
    before being handed to agents.
    """
    source_path: str                          # file path or URL
    source_type: str                          # "pdf", "docx", "csv", "yaml", "json", "url", "xlsx"
    document_type: str                        # "data_dictionary", "saas_context", "business_glossary",
                                              # "existing_semantic_layer", "schema_docs", "unknown"
    extracted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    extraction_confidence: str = "medium"     # "high" | "medium" | "low"

    # Structured extractions
    table_definitions: list[TableDefinition] = field(default_factory=list)
    column_definitions: list[ColumnDefinition] = field(default_factory=list)
    measure_definitions: list[MeasureDefinition] = field(default_factory=list)  # additive measures on fact tables
    metric_definitions: list[MetricDefinition] = field(default_factory=list)    # business KPIs
    business_rules: list[BusinessRule] = field(default_factory=list)
    glossary: list[GlossaryTerm] = field(default_factory=list)
    join_hints: list[JoinHint] = field(default_factory=list)

    # Raw text — always stored for HTML/developer docs so agents can read it natively.
    # For structured formats (CSV, dbt manifest, JSON) this is empty.
    raw_text_summary: str | None = None      # up to 50K chars of clean extracted text
    extraction_notes: list[str] = field(default_factory=list)  # warnings, skips, issues

    def to_dict(self) -> dict:
        return asdict(self)

    def to_context_summary(self) -> str:
        """
        Compact text representation for loading into Claude's context window.
        Structured so agents can quickly find relevant definitions.
        """
        lines = [
            f"## Document: {self.source_path}",
            f"Type: {self.document_type} | Source format: {self.source_type} "
            f"| Confidence: {self.extraction_confidence}",
            "",
        ]

        if self.table_definitions:
            lines.append("### Tables / Semantic Models")
            for t in self.table_definitions:
                ttype = f" [{t.table_type.upper()}]" if t.table_type else ""
                pk = f" | PK: `{t.primary_key}`" if t.primary_key else ""
                lines.append(f"- **{t.table_name}**{ttype}{pk}: {t.description or '(no description)'}")
                if t.source_system:
                    lines[-1] += f" [source: {t.source_system}]"
                if t.grain_description:
                    lines.append(f"  - Grain: {t.grain_description}")
            lines.append("")

        if self.column_definitions:
            lines.append("### Columns / Dimensions")
            # Group by table
            by_table: dict[str, list[ColumnDefinition]] = {}
            for cd in self.column_definitions:
                by_table.setdefault(cd.table_name, []).append(cd)
            for table, cols in by_table.items():
                lines.append(f"**{table}**")
                for col in cols:
                    label = f" → \"{col.business_name}\"" if col.business_name else ""
                    desc = f" — {col.description}" if col.description else ""
                    pii = " [PII]" if col.is_pii else ""
                    fk = f" [FK → {col.references_table}]" if col.is_foreign_key and col.references_table else ""
                    stype = f" [{col.semantic_type}]" if col.semantic_type else ""
                    grain = f" grain:{col.time_granularity}" if col.time_granularity else ""
                    lines.append(f"  - `{col.column_name}`{stype}{grain}{label}{desc}{pii}{fk}")
                    if col.data_type_note:
                        lines.append(f"    - Type note: {col.data_type_note}")
                    if col.valid_values:
                        lines.append(f"    - Valid values: {', '.join(col.valid_values)}")
            lines.append("")

        if self.measure_definitions:
            lines.append("### Measures (additive aggregations on fact tables)")
            by_table_m: dict[str, list[MeasureDefinition]] = {}
            for m in self.measure_definitions:
                by_table_m.setdefault(m.table_name, []).append(m)
            for table, measures in by_table_m.items():
                lines.append(f"**{table}**")
                for m in measures:
                    label = f" \"{m.label}\"" if m.label else ""
                    expr = f" — `{m.expression}`" if m.expression else ""
                    lines.append(f"  - `{m.name}`{label} [{m.aggregation}]{expr}")
                    if m.description:
                        lines.append(f"    - {m.description}")
                    if m.filters:
                        lines.append(f"    - Filters: {' AND '.join(m.filters)}")
                    if m.non_additive_dimension:
                        lines.append(f"    - Semi-additive over: {m.non_additive_dimension}")
            lines.append("")

        if self.metric_definitions:
            lines.append("### Metrics (business KPIs)")
            for m in self.metric_definitions:
                cert = " [certified]" if m.is_certified else ""
                mtype = f" [{m.metric_type}]" if m.metric_type else ""
                lines.append(f"- **{m.business_name}** (`{m.name}`){mtype}{cert}")
                if m.description:
                    lines.append(f"  - {m.description}")
                if m.formula:
                    lines.append(f"  - Formula: `{m.formula}`")
                if m.measure_name:
                    lines.append(f"  - Measure: `{m.measure_name}`")
                if m.numerator_measure and m.denominator_measure:
                    lines.append(f"  - Ratio: `{m.numerator_measure}` / `{m.denominator_measure}`")
                if m.filters:
                    lines.append(f"  - Filters: {' AND '.join(m.filters)}")
                if m.dimensions:
                    lines.append(f"  - Dimensions: {', '.join(m.dimensions)}")
                if m.domain:
                    lines.append(f"  - Domain: {m.domain}")
            lines.append("")

        if self.business_rules:
            lines.append("### Business Rules")
            for r in self.business_rules:
                lines.append(f"- {r.rule}")
            lines.append("")

        if self.glossary:
            lines.append("### Glossary")
            for g in self.glossary:
                syns = f" (also: {', '.join(g.synonyms)})" if g.synonyms else ""
                lines.append(f"- **{g.term}**{syns}: {g.definition}")
            lines.append("")

        if self.join_hints:
            lines.append("### Documented Join Relationships")
            for j in self.join_hints:
                card = f" [{j.cardinality}]" if j.cardinality else ""
                lines.append(
                    f"- `{j.left_table}` → `{j.right_table}` on `{j.join_key}`{card}"
                )
                if j.description:
                    lines.append(f"  - {j.description}")
            lines.append("")

        if self.extraction_notes:
            lines.append("### Extraction Notes")
            for note in self.extraction_notes:
                lines.append(f"- ⚠ {note}")
            lines.append("")

        # Always surface raw text for low/medium confidence — lets agents read it natively
        # (same as Claude Code's approach: give the LLM raw content, don't pre-extract)
        if self.raw_text_summary and self.extraction_confidence in ("low", "medium"):
            lines.append("### Source Document (raw text — read and reason about this directly)")
            lines.append(self.raw_text_summary)

        return "\n".join(lines)


# ── Merged context (all documents combined) ────────────────────────────────────

class MergedDocumentContext:
    """
    Combines multiple DocumentContext objects into a single lookup structure.
    Used by agents to resolve column/metric/table definitions efficiently.
    """

    def __init__(self, contexts: list[DocumentContext]):
        self.contexts = contexts
        self._build_indexes()

    def _build_indexes(self):
        """Build fast-lookup dictionaries for agents."""
        self.column_index: dict[tuple[str, str], ColumnDefinition] = {}  # (table, col) → def
        self.table_index: dict[str, TableDefinition] = {}                 # table → def
        self.measure_index: dict[str, MeasureDefinition] = {}            # name → def
        self.metric_index: dict[str, MetricDefinition] = {}              # name → def
        self.glossary_index: dict[str, GlossaryTerm] = {}               # term → def
        self.rule_list: list[BusinessRule] = []
        self.join_hints: list[JoinHint] = []

        for ctx in self.contexts:
            for td in ctx.table_definitions:
                self.table_index[td.table_name.lower()] = td
            for cd in ctx.column_definitions:
                key = (cd.table_name.lower(), cd.column_name.lower())
                self.column_index[key] = cd
            for ms in ctx.measure_definitions:
                self.measure_index[ms.name.lower()] = ms
            for md in ctx.metric_definitions:
                self.metric_index[md.name.lower()] = md
            for g in ctx.glossary:
                self.glossary_index[g.term.lower()] = g
            self.rule_list.extend(ctx.business_rules)
            self.join_hints.extend(ctx.join_hints)

    def get_column(self, table: str, column: str) -> ColumnDefinition | None:
        return self.column_index.get((table.lower(), column.lower()))

    def get_table(self, table: str) -> TableDefinition | None:
        return self.table_index.get(table.lower())

    def get_measure(self, name: str) -> MeasureDefinition | None:
        return self.measure_index.get(name.lower())

    def get_metric(self, name: str) -> MetricDefinition | None:
        return self.metric_index.get(name.lower())

    def get_glossary(self, term: str) -> GlossaryTerm | None:
        return self.glossary_index.get(term.lower())

    def rules_for_table(self, table: str) -> list[BusinessRule]:
        return [r for r in self.rule_list if table.lower() in [t.lower() for t in r.affects_tables]]

    def all_measures(self) -> list[MeasureDefinition]:
        return list(self.measure_index.values())

    def all_metrics(self) -> list[MetricDefinition]:
        return list(self.metric_index.values())

    def fact_tables(self) -> list[TableDefinition]:
        return [t for t in self.table_index.values() if t.table_type == "fact"]

    def dimension_tables(self) -> list[TableDefinition]:
        return [t for t in self.table_index.values() if t.table_type == "dimension"]

    def time_dimensions(self) -> list[ColumnDefinition]:
        return [c for c in self.column_index.values() if c.semantic_type == "time_dimension"]

    def to_context_summary(self) -> str:
        """Combined summary of all loaded documents."""
        if not self.contexts:
            return "No documents loaded."
        parts = [ctx.to_context_summary() for ctx in self.contexts]
        header = f"# Document Context — {len(self.contexts)} source(s) loaded\n\n"
        return header + "\n---\n\n".join(parts)

    def is_empty(self) -> bool:
        return len(self.contexts) == 0


# ── Disk I/O ───────────────────────────────────────────────────────────────────

DOCS_DIR = Path.home() / ".yorph" / "documents"


def save_document_context(ctx: DocumentContext) -> Path:
    """Save a DocumentContext to disk as JSON."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitise filename from source path
    safe_name = Path(ctx.source_path).name.replace(" ", "_")
    path = DOCS_DIR / f"{safe_name}.context.json"
    with open(path, "w") as f:
        json.dump(ctx.to_dict(), f, indent=2, default=str)
    return path


def load_all_document_contexts() -> list[DocumentContext]:
    """Load all saved DocumentContext files from disk."""
    if not DOCS_DIR.exists():
        return []
    contexts = []
    for f in sorted(DOCS_DIR.glob("*.context.json")):
        with open(f) as fh:
            data = json.load(fh)
            # Reconstruct dataclasses
            ctx = DocumentContext(
                source_path=data["source_path"],
                source_type=data["source_type"],
                document_type=data["document_type"],
                extracted_at=data.get("extracted_at", ""),
                extraction_confidence=data.get("extraction_confidence", "medium"),
                table_definitions=[TableDefinition(**t) for t in data.get("table_definitions", [])],
                column_definitions=[ColumnDefinition(**c) for c in data.get("column_definitions", [])],
                measure_definitions=[MeasureDefinition(**m) for m in data.get("measure_definitions", [])],
                metric_definitions=[MetricDefinition(**m) for m in data.get("metric_definitions", [])],
                business_rules=[BusinessRule(**r) for r in data.get("business_rules", [])],
                glossary=[GlossaryTerm(**g) for g in data.get("glossary", [])],
                join_hints=[JoinHint(**j) for j in data.get("join_hints", [])],
                raw_text_summary=data.get("raw_text_summary"),
                extraction_notes=data.get("extraction_notes", []),
            )
            contexts.append(ctx)
    return contexts
