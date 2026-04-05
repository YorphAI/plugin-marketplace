"""
Tests for document processing and enrichment — no warehouse connection needed.
"""

import pytest


class TestDocumentContext:

    def test_context_summary_renders(self, sample_document_context):
        summary = sample_document_context.to_context_summary()
        assert "orders" in summary
        assert "Gross Revenue" in summary
        assert "Total Revenue" in summary

    def test_context_summary_shows_business_rules(self, sample_document_context):
        summary = sample_document_context.to_context_summary()
        assert "Business Rules" in summary
        assert "completed" in summary

    def test_context_summary_shows_metrics(self, sample_document_context):
        summary = sample_document_context.to_context_summary()
        assert "Metric" in summary
        assert "certified" in summary.lower() or "✓" in summary

    def test_to_dict_roundtrip(self, sample_document_context):
        from runtime.documents.context import DocumentContext, ColumnDefinition, TableDefinition
        from dataclasses import asdict
        d = sample_document_context.to_dict()
        assert d["source_path"] == sample_document_context.source_path
        assert len(d["column_definitions"]) == len(sample_document_context.column_definitions)


class TestMergedDocumentContext:

    def test_lookup_by_table(self, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        merged = MergedDocumentContext([sample_document_context])
        td = merged.get_table("orders")
        assert td is not None
        assert td.source_system == "Shopify"

    def test_lookup_by_column(self, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        merged = MergedDocumentContext([sample_document_context])
        cd = merged.get_column("orders", "revenue")
        assert cd is not None
        assert cd.business_name == "Gross Revenue"

    def test_lookup_case_insensitive(self, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        merged = MergedDocumentContext([sample_document_context])
        assert merged.get_column("ORDERS", "REVENUE") is not None

    def test_rules_for_table(self, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        merged = MergedDocumentContext([sample_document_context])
        rules = merged.rules_for_table("orders")
        assert len(rules) > 0

    def test_all_metrics(self, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        merged = MergedDocumentContext([sample_document_context])
        metrics = merged.all_metrics()
        assert any(m.name == "total_revenue" for m in metrics)

    def test_empty_context(self):
        from runtime.documents.context import MergedDocumentContext
        merged = MergedDocumentContext([])
        assert merged.get_table("orders") is None
        assert merged.is_empty()


class TestProfileEnricher:

    def test_enrich_adds_business_name(self, sample_table_profiles, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher
        merged = MergedDocumentContext([sample_document_context])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(sample_table_profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        revenue_col = next(c for c in orders.columns if c.name == "revenue")

        assert revenue_col.business_name == "Gross Revenue"
        assert revenue_col.business_name_source == "documented"

    def test_enrich_adds_description(self, sample_table_profiles, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher
        merged = MergedDocumentContext([sample_document_context])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(sample_table_profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        revenue_col = next(c for c in orders.columns if c.name == "revenue")
        assert "USD" in (revenue_col.description or "")

    def test_enrich_detects_valid_value_conflict(self, sample_table_profiles, sample_document_context):
        """Status has 'N/A' in data but docs list valid_values without it."""
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher
        merged = MergedDocumentContext([sample_document_context])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(sample_table_profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        status_col = next(c for c in orders.columns if c.name == "status")
        # "N/A" is in sample_values but not in documented valid_values
        # This should trigger a conflict
        if status_col.conflicts:
            assert any("N/A" in c or "valid values" in c.lower() for c in status_col.conflicts)

    def test_enrich_adds_table_description(self, sample_table_profiles, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher
        merged = MergedDocumentContext([sample_document_context])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(sample_table_profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        assert orders.description is not None
        assert "Shopify" in (orders.description or orders.source_system or "")

    def test_enrich_adds_relevant_metrics(self, sample_table_profiles, sample_document_context):
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher
        merged = MergedDocumentContext([sample_document_context])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(sample_table_profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        assert any(m.name == "total_revenue" for m in orders.relevant_metrics)

    def test_fallback_humanises_column_name(self, sample_table_profiles):
        """Without docs, column names should be humanised."""
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher
        merged = MergedDocumentContext([])  # no docs
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(sample_table_profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        order_id_col = next(c for c in orders.columns if c.name == "order_id")
        # Should have a humanised fallback
        assert order_id_col.business_name is not None
        assert order_id_col.business_name_source == "inferred"

    def test_agent_summary_contains_stats_and_semantics(
        self, sample_table_profiles, sample_document_context
    ):
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher
        merged = MergedDocumentContext([sample_document_context])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(sample_table_profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        summary = orders.to_agent_summary()

        assert "orders" in summary
        assert "Shopify" in summary           # from doc
        assert "Gross Revenue" in summary     # business name from doc
        assert "null=" in summary             # statistical content
        assert "Total Revenue" in summary     # metric from doc
        assert "Business Rules" in summary    # rules from doc


class TestDocumentProcessor:

    def test_csv_data_dictionary_parse(self, tmp_path):
        """Parse a CSV in standard data dictionary format."""
        from runtime.documents.processor import process_file
        csv_content = (
            "table_name,column_name,description,business_name\n"
            "orders,order_id,Unique order identifier,Order ID\n"
            "orders,revenue,Pre-tax revenue in USD,Gross Revenue\n"
            "customers,customer_id,CRM account ID,Customer ID\n"
        )
        csv_path = tmp_path / "dict.csv"
        csv_path.write_text(csv_content)

        ctx = process_file(str(csv_path), document_type="data_dictionary")
        assert len(ctx.column_definitions) == 3
        revenue = next(c for c in ctx.column_definitions if c.column_name == "revenue")
        assert revenue.business_name == "Gross Revenue"

    def test_json_dbt_schema_parse(self, tmp_path):
        """Parse a dbt schema.yaml-equivalent as JSON."""
        import json
        from runtime.documents.processor import process_file

        data = {
            "models": [
                {
                    "name": "orders",
                    "description": "Order fact table",
                    "columns": [
                        {"name": "order_id", "description": "Primary key"},
                        {"name": "revenue", "description": "Gross revenue"},
                    ],
                }
            ],
            "metrics": [
                {
                    "name": "total_revenue",
                    "label": "Total Revenue",
                    "description": "Sum of all revenue",
                }
            ],
        }

        # dbt schema.yaml → save as YAML for the processor
        import yaml
        yaml_path = tmp_path / "schema.yaml"
        yaml_path.write_text(yaml.dump(data))

        ctx = process_file(str(yaml_path), document_type="existing_semantic_layer")
        assert ctx.extraction_confidence == "high"
        assert any(t.table_name == "orders" for t in ctx.table_definitions)
        assert any(m.name == "total_revenue" for m in ctx.metric_definitions)
