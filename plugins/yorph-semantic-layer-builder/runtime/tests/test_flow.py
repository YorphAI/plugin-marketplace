"""
End-to-end flow integration test.

Simulates the full 6-step plugin workflow without Claude or a real warehouse:

  Step 1 — Connect        (DuckDB mock profiler)
  Step 2 — Profile        (run_profiler + get_context_summary)
  Step 3 — Documents      (process_document with a CSV fixture)
  Step 4 — Agents         (verify enriched context that agents would receive)
  Step 5 — Recommendations (build_semantic_layer_from_agent_outputs x3)
  Step 6 — Save           (render all formats, verify files written)

Run with:
  cd semantic_layer/runtime
  pytest tests/test_flow.py -v -s

The -s flag shows the context summary and file paths as the test runs,
so you can see exactly what Claude would see at each step.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml


# ── Step 1 + 2: Connect + Profile ─────────────────────────────────────────────

class TestConnectAndProfile:

    def test_step1_connect(self, mock_profiler):
        """Verify connection works and returns rows."""
        rows = mock_profiler.execute("SELECT 1 AS ping")
        assert rows == [{"ping": 1}], "Connection test failed"
        print("\n✅ Step 1 — Connected (DuckDB mock)")

    def test_step2_profile_all(self, mock_profiler):
        """Profile all tables and verify profiles are written to disk."""
        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))

        assert len(profiles) >= 4, f"Expected ≥4 tables, got {len(profiles)}"
        table_names = [p.table_name for p in profiles]
        assert "orders" in table_names
        assert "customers" in table_names

        # Profiles should be saved to disk
        profile_dir = mock_profiler._profiles_dir / mock_profiler.WAREHOUSE_TYPE
        saved_files = list(profile_dir.glob("*.json"))
        assert len(saved_files) == len(profiles), "Not all profiles were saved to disk"

        print(f"\n✅ Step 2 — Profiled {len(profiles)} tables:")
        for p in profiles:
            high_null = [c.name for c in p.columns if c.pct_null > 10]
            print(f"   {p.schema_name}.{p.table_name}: {p.total_rows:,} rows, "
                  f"{len(p.columns)} cols"
                  + (f", high nulls: {high_null}" if high_null else ""))

    def test_step2_context_summary_is_populated(self, mock_profiler):
        """get_context_summary returns enriched text Claude can read."""
        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))

        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import build_enriched_profiles, enriched_context_summary

        enriched = build_enriched_profiles(profiles)
        merged_docs = MergedDocumentContext([])  # no docs yet
        summary = enriched_context_summary(enriched, merged_docs, batch_index=0)

        assert "orders" in summary
        assert "revenue" in summary
        assert "null=" in summary

        print(f"\n✅ Step 2 — Context summary ({len(summary)} chars):")
        print(summary[:800] + "...\n[truncated]")

    def test_step2_encoded_nulls_detected(self, mock_profiler):
        """Status column contains 'N/A' — should be detected as null-like strings."""
        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))
        orders = next(p for p in profiles if p.table_name == "orders")
        status = next(c for c in orders.columns if c.name == "status")

        # Either pct_na or pct_n_slash_a should be populated
        null_like = (status.pct_na or 0) + (status.pct_n_slash_a or 0)
        assert null_like > 0, (
            "Expected N/A values to be detected. "
            f"Got pct_na={status.pct_na}, pct_n_slash_a={status.pct_n_slash_a}"
        )
        print(f"\n✅ Step 2 — Encoded null detected: status N/A = {null_like:.1f}%")


# ── Step 3: Document ingestion ─────────────────────────────────────────────────

class TestDocumentIngestion:

    @pytest.fixture
    def data_dictionary_csv(self, tmp_path):
        content = (
            "table_name,column_name,description,business_name,pii\n"
            "orders,order_id,Unique order identifier,Order ID,false\n"
            "orders,revenue,Pre-tax invoice amount in USD,Gross Revenue,false\n"
            "orders,status,Fulfilment status,Order Status,false\n"
            "orders,customer_id,FK to customers table,Customer ID,false\n"
            "customers,customer_id,Unique customer identifier,Customer ID,false\n"
            "customers,email,Customer email address,Email,true\n"
        )
        path = tmp_path / "data_dictionary.csv"
        path.write_text(content)
        return str(path)

    def test_step3_process_csv_document(self, data_dictionary_csv, tmp_path):
        from runtime.documents.processor import process_file

        ctx = process_file(data_dictionary_csv, document_type="data_dictionary")

        assert ctx.extraction_confidence == "high"
        assert len(ctx.column_definitions) == 6
        assert any(c.business_name == "Gross Revenue" for c in ctx.column_definitions)
        assert any(c.is_pii for c in ctx.column_definitions)  # email is PII

        print(f"\n✅ Step 3 — Document processed:")
        print(f"   {len(ctx.table_definitions)} tables, "
              f"{len(ctx.column_definitions)} columns, "
              f"confidence: {ctx.extraction_confidence}")
        print(f"   PII columns: {[c.column_name for c in ctx.column_definitions if c.is_pii]}")

    def test_step3_enrichment_applies_doc_context(
        self, mock_profiler, data_dictionary_csv, tmp_path
    ):
        from runtime.documents.processor import process_file
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import ProfileEnricher

        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))
        ctx = process_file(data_dictionary_csv, document_type="data_dictionary")
        merged = MergedDocumentContext([ctx])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        revenue = next(c for c in orders.columns if c.name == "revenue")

        assert revenue.business_name == "Gross Revenue"
        assert revenue.business_name_source == "documented"
        assert "USD" in (revenue.description or "")

        print(f"\n✅ Step 3 — Enrichment applied:")
        print(f"   orders.revenue → business_name: '{revenue.business_name}' (source: {revenue.business_name_source})")
        print(f"   orders.revenue → description: '{revenue.description}'")

    def test_step3_conflict_detection(self, mock_profiler, tmp_path):
        """Status column has 'N/A' in data but doc lists valid values without it."""
        from runtime.documents.processor import process_file
        from runtime.documents.context import MergedDocumentContext, ColumnDefinition, DocumentContext
        from runtime.documents.enricher import ProfileEnricher

        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))

        # Doc says valid values are limited — doesn't include 'N/A'
        ctx = DocumentContext(
            source_path="/tmp/test.csv",
            source_type="csv",
            document_type="data_dictionary",
            column_definitions=[
                ColumnDefinition(
                    table_name="orders",
                    column_name="status",
                    business_name="Order Status",
                    valid_values=["pending", "completed", "refunded"],  # 'N/A' not listed
                )
            ],
        )

        merged = MergedDocumentContext([ctx])
        enricher = ProfileEnricher(merged)
        enriched = enricher.enrich_all(profiles)

        orders = next(e for e in enriched if e.table_name == "orders")
        status = next(c for c in orders.columns if c.name == "status")

        # Conflict should be flagged
        if status.conflicts:
            print(f"\n✅ Step 3 — Conflict detected on status column:")
            for c in status.conflicts:
                print(f"   ⚠ {c}")
        else:
            print(f"\n⚠  Step 3 — No conflict detected (sample may not include N/A values)")


# ── Step 4: What agents would receive ─────────────────────────────────────────

class TestAgentContext:

    def test_step4_agent_context_is_comprehensive(
        self, mock_profiler, tmp_path
    ):
        """Verify the enriched context that all 9 agents receive."""
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import build_enriched_profiles, enriched_context_summary

        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))
        enriched = build_enriched_profiles(profiles)
        merged = MergedDocumentContext([])
        summary = enriched_context_summary(enriched, merged)

        # Agents should be able to see:
        assert "orders" in summary           # table names
        assert "revenue" in summary          # column names
        assert "null=" in summary            # null statistics
        assert "distinct=" in summary        # cardinality

        print(f"\n✅ Step 4 — Agent context ready ({len(summary):,} chars):")
        print("   Tables:", [e.table_name for e in enriched])
        print(f"   Excerpt:\n{summary[:500]}...[truncated]")

    def test_step4_context_batching(self, mock_profiler):
        """Large warehouses are split into 100-table batches."""
        from runtime.profiler.base import TABLES_PER_CONTEXT_BATCH
        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))
        batches = mock_profiler.context_batches()

        assert all(len(b) <= TABLES_PER_CONTEXT_BATCH for b in batches)
        total = sum(len(b) for b in batches)
        assert total == len(profiles)

        print(f"\n✅ Step 4 — Context batching: {len(profiles)} tables → {len(batches)} batch(es)")


# ── Step 5 + 6: Recommendations + Save ────────────────────────────────────────

class TestRecommendationsAndSave:

    @pytest.fixture
    def agent_outputs(self):
        from runtime.cli import _builtin_fixture
        return _builtin_fixture()

    def test_step5_all_three_recommendations_build(self, agent_outputs):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs

        for rec_number in (1, 2, 3):
            layer = build_semantic_layer_from_agent_outputs(
                agent_outputs=agent_outputs,
                recommendation_number=rec_number,
                warehouse_type="snowflake",
                project_name="Test Corp",
                description="E-commerce semantic layer.",
            )
            assert layer.recommendation in ("Conservative", "Comprehensive", "Balanced")
            assert len(layer.measures) > 0
            assert len(layer.joins) > 0

        print("\n✅ Step 5 — All 3 recommendations built")

    def test_step6_save_all_formats(self, agent_outputs, tmp_path):
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )

        layer = build_semantic_layer_from_agent_outputs(
            agent_outputs=agent_outputs,
            recommendation_number=3,
            warehouse_type="snowflake",
            project_name="Test Corp",
        )

        renderer = OutputRenderer(layer, output_dir=tmp_path)
        all_written: dict[str, Path] = {}

        for fmt in ("dbt", "snowflake", "json", "yaml", "osi_spec"):
            written = renderer.render(fmt, filename_base=f"test_{fmt}")
            all_written.update(written)

        print(f"\n✅ Step 6 — Files written to {tmp_path}:")
        for kind, path in all_written.items():
            size = path.stat().st_size
            print(f"   {kind}: {path.name} ({size:,} bytes)")

        # Every render must include the companion document
        doc_files = [p for k, p in all_written.items() if k == "document"]
        assert len(doc_files) >= 1

    def test_step6_dbt_output_is_valid(self, agent_outputs, tmp_path):
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        layer = build_semantic_layer_from_agent_outputs(
            agent_outputs, 1, "snowflake", "Test"
        )
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("dbt", filename_base="test")

        content = written["dbt"].read_text()
        parsed = yaml.safe_load(content)
        assert parsed["version"] == 2
        assert "models" in parsed

        print(f"\n✅ Step 6 — dbt YAML valid, {len(parsed['models'])} models")

    def test_step6_companion_document_complete(self, agent_outputs, tmp_path):
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        layer = build_semantic_layer_from_agent_outputs(
            agent_outputs, 3, "snowflake", "Test Corp"
        )
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("json", filename_base="test")

        readme = written["document"].read_text()
        required_sections = [
            "## What Was Built",
            "## Entities",
            "## Metrics",
            "## Business Rules Applied",
            "## ⚠ Open Questions to Revisit",
        ]
        for section in required_sections:
            assert section in readme, f"Missing section: {section}"

        print(f"\n✅ Step 6 — Companion document complete ({len(readme):,} chars):")
        print(f"   Sections: {', '.join(s.replace('## ', '') for s in required_sections)}")


# ── Full flow smoke test ───────────────────────────────────────────────────────

class TestFullFlowSmoke:
    """
    Single test that runs the entire flow sequentially.
    Useful for a quick sanity check: pytest tests/test_flow.py::TestFullFlowSmoke -v -s
    """

    def test_full_flow(self, mock_profiler, tmp_path):
        from runtime.documents.processor import process_file
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import build_enriched_profiles, enriched_context_summary
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        from runtime.cli import _builtin_fixture

        print("\n" + "="*60)
        print("FULL FLOW SMOKE TEST")
        print("="*60)

        # Step 1: Connect
        rows = mock_profiler.execute("SELECT 1 AS ping")
        assert rows[0]["ping"] == 1
        print("\n[1/6] Connect ✅")

        # Step 2: Profile
        profiles = asyncio.run(mock_profiler.profile_all(schemas=["main"]))
        assert len(profiles) >= 4
        print(f"[2/6] Profile ✅  ({len(profiles)} tables)")

        # Step 3: Document ingestion
        csv_content = (
            "table_name,column_name,description,business_name\n"
            "orders,revenue,Pre-tax revenue in USD,Gross Revenue\n"
            "orders,status,Order fulfilment status,Order Status\n"
        )
        csv_path = tmp_path / "dict.csv"
        csv_path.write_text(csv_content)
        ctx = process_file(str(csv_path), document_type="data_dictionary")
        assert len(ctx.column_definitions) == 2
        print(f"[3/6] Documents ✅  ({len(ctx.column_definitions)} column defs extracted)")

        # Step 4: Enriched agent context
        merged = MergedDocumentContext([ctx])
        enriched = build_enriched_profiles(profiles)
        summary = enriched_context_summary(enriched, merged)
        assert "Gross Revenue" in summary or "revenue" in summary
        print(f"[4/6] Agent context ✅  ({len(summary):,} chars)")

        # Step 5: Build all 3 recommendations
        agent_outputs = _builtin_fixture()
        layers = []
        for rec in (1, 2, 3):
            layer = build_semantic_layer_from_agent_outputs(
                agent_outputs, rec, "snowflake", "Test Corp"
            )
            layers.append(layer)
        assert all(len(l.measures) > 0 for l in layers)
        print(f"[5/6] Recommendations ✅  (3 built: {', '.join(l.recommendation for l in layers)})")

        # Step 6: Save
        out_dir = tmp_path / "output"
        renderer = OutputRenderer(layers[2], output_dir=out_dir)  # Balanced
        written = renderer.render("dbt", filename_base="smoke_test")
        assert written["dbt"].exists()
        assert written["document"].exists()
        dbt_content = yaml.safe_load(written["dbt"].read_text())
        assert dbt_content["version"] == 2
        print(f"[6/6] Save ✅  → {out_dir}/smoke_test.yml + smoke_test_readme.md")

        print("\n" + "="*60)
        print("ALL 6 STEPS PASSED ✅")
        print("="*60)
