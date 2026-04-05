"""
Tests for the output renderer — no warehouse connection needed.
Uses mock agent_outputs fixture from conftest.py.
"""

import json
import pytest
import yaml


class TestSemanticLayerIR:
    """Test building the intermediate representation from agent outputs."""

    def test_build_conservative(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs
        layer = build_semantic_layer_from_agent_outputs(
            agent_outputs=mock_agent_outputs,
            recommendation_number=1,
            warehouse_type="snowflake",
            project_name="Test",
        )
        assert layer.recommendation == "Conservative"
        assert len(layer.measures) > 0
        assert len(layer.joins) > 0

    def test_build_comprehensive(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs
        layer = build_semantic_layer_from_agent_outputs(
            agent_outputs=mock_agent_outputs,
            recommendation_number=2,
            warehouse_type="snowflake",
            project_name="Test",
        )
        assert layer.recommendation == "Comprehensive"
        # Rec 2 uses MB-2 which has more measures than MB-1
        assert len(layer.measures) >= 2

    def test_build_balanced(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs
        layer = build_semantic_layer_from_agent_outputs(
            agent_outputs=mock_agent_outputs,
            recommendation_number=3,
            warehouse_type="snowflake",
            project_name="Test",
        )
        assert layer.recommendation == "Balanced"

    def test_business_rules_preserved(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs
        layer = build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 3, "snowflake", "Test"
        )
        assert len(layer.business_rules) > 0
        assert any("completed" in r for r in layer.business_rules)

    def test_open_questions_preserved(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs
        layer = build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 3, "snowflake", "Test"
        )
        assert len(layer.open_questions) > 0


class TestDbtRenderer:
    """Test dbt YAML output."""

    @pytest.fixture
    def layer(self, mock_agent_outputs):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs
        return build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 1, "snowflake", "TestProject"
        )

    def test_dbt_renders_without_error(self, layer, tmp_path):
        from runtime.output.renderer import OutputRenderer
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("dbt", filename_base="test")
        assert "dbt" in written
        assert written["dbt"].exists()

    def test_dbt_is_valid_yaml(self, layer, tmp_path):
        from runtime.output.renderer import OutputRenderer
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("dbt", filename_base="test")
        content = written["dbt"].read_text()
        parsed = yaml.safe_load(content)
        assert parsed is not None

    def test_dbt_has_version_2(self, layer, tmp_path):
        from runtime.output.renderer import OutputRenderer
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("dbt", filename_base="test")
        content = written["dbt"].read_text()
        parsed = yaml.safe_load(content)
        assert parsed.get("version") == 2

    def test_dbt_has_models(self, layer, tmp_path):
        from runtime.output.renderer import OutputRenderer
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("dbt", filename_base="test")
        parsed = yaml.safe_load(written["dbt"].read_text())
        assert "models" in parsed
        assert len(parsed["models"]) > 0

    def test_dbt_always_writes_readme(self, layer, tmp_path):
        from runtime.output.renderer import OutputRenderer
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("dbt", filename_base="test")
        assert "document" in written
        assert written["document"].exists()
        readme = written["document"].read_text()
        assert "## What Was Built" in readme
        assert "## Metrics" in readme


class TestSnowflakeRenderer:

    @pytest.fixture
    def layer(self, mock_agent_outputs):
        from runtime.output.renderer import build_semantic_layer_from_agent_outputs
        return build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 2, "snowflake", "TestProject"
        )

    def test_snowflake_renders_valid_yaml(self, layer, tmp_path):
        from runtime.output.renderer import OutputRenderer
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("snowflake", filename_base="test")
        content = written["snowflake"].read_text()
        parsed = yaml.safe_load(content)
        assert "semantic_layer" in parsed

    def test_snowflake_has_entities_and_joins(self, layer, tmp_path):
        from runtime.output.renderer import OutputRenderer
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("snowflake", filename_base="test")
        parsed = yaml.safe_load(written["snowflake"].read_text())
        sl = parsed["semantic_layer"]
        assert "entities" in sl
        assert "joins" in sl


class TestJsonRenderer:

    def test_json_renders_valid(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        layer = build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 1, "snowflake", "Test"
        )
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("json", filename_base="test")
        content = written["json"].read_text()
        parsed = json.loads(content)
        assert "semantic_layer" in parsed
        assert parsed["semantic_layer"]["recommendation"] == "Conservative"


class TestAllFormats:

    def test_all_formats_generate_files(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        layer = build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 3, "snowflake", "Test"
        )
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        formats = ["dbt", "snowflake", "json", "yaml", "osi_spec"]
        for fmt in formats:
            written = renderer.render(fmt, filename_base=f"test_{fmt}")
            assert fmt in written or "document" in written
            # Companion readme always present
            assert "document" in written


class TestDocumentRenderer:

    def test_readme_contains_key_sections(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        layer = build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 3, "snowflake", "Acme Corp"
        )
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("json", filename_base="test")
        readme = written["document"].read_text()

        assert "## What Was Built" in readme
        assert "## Entities" in readme
        assert "## Metrics" in readme
        assert "## Business Rules Applied" in readme
        assert "## ⚠ Open Questions to Revisit" in readme

    def test_readme_uses_business_names(self, mock_agent_outputs, tmp_path):
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        layer = build_semantic_layer_from_agent_outputs(
            mock_agent_outputs, 1, "snowflake", "Test"
        )
        renderer = OutputRenderer(layer, output_dir=tmp_path)
        written = renderer.render("json", filename_base="test")
        readme = written["document"].read_text()
        # Business name from fixture is "Total Revenue"
        assert "Total Revenue" in readme
