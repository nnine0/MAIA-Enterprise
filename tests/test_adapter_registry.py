"""
Tests for Adapter Registry module.
"""

import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path
from app.adapter_registry import (
    AdapterRegistry,
    AdapterMetadata,
)


class TestAdapterMetadata:
    """Tests for AdapterMetadata dataclass."""

    def test_metadata_creation(self):
        """Test AdapterMetadata creation."""
        metadata = AdapterMetadata(
            adapter_id="law",
            name="Legal Expert Adapter",
            version="1.0.0",
            sr26_tier=1,
            domain="legal",
            sub_domain="Legal Advisory",
            base_model="llama-3.1-70b",
            created_date="2026-05-04",
            conceptual_soundness={"version": "1.0.0"},
            risk_assessment={"level": "HIGH"},
            governance={"requires_dhitl": True}
        )

        assert metadata.adapter_id == "law"
        assert metadata.version == "1.0.0"
        assert metadata.sr26_tier == 1


class TestAdapterRegistry:
    """Tests for AdapterRegistry class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.council_dir = os.path.join(self.temp_dir, "council")
        os.makedirs(self.council_dir)

    def teardown_method(self):
        """Clean up temp files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_metadata_file(self, adapter_id: str, tier: int):
        """Helper to create metadata file."""
        adapter_path = os.path.join(self.council_dir, f"adapter_{adapter_id}")
        os.makedirs(adapter_path)

        metadata = {
            "adapter_id": adapter_id,
            "name": f"{adapter_id.title()} Expert",
            "version": "1.0.0",
            "sr26_tier": tier,
            "domain": "general",
            "sub_domain": "General",
            "base_model": "test-model",
            "created_date": "2026-05-04",
            "conceptual_soundness": {"version": "1.0.0"},
            "risk_assessment": {"level": "LOW"},
            "governance": {"requires_dhitl": tier == 1}
        }

        with open(os.path.join(adapter_path, "metadata.json"), 'w') as f:
            json.dump(metadata, f)

    def test_registry_creation(self):
        """Test registry creation."""
        registry = AdapterRegistry(self.council_dir)
        assert registry is not None

    def test_load_adapters(self):
        """Test loading adapter metadata."""
        self._create_metadata_file("law", 1)
        self._create_metadata_file("finance", 2)

        registry = AdapterRegistry(self.council_dir)
        adapters = registry.list_all()

        assert len(adapters) == 2
        adapter_ids = [a.adapter_id for a in adapters]
        assert "law" in adapter_ids
        assert "finance" in adapter_ids

    def test_get_adapter(self):
        """Test getting specific adapter."""
        self._create_metadata_file("legal", 1)

        registry = AdapterRegistry(self.council_dir)
        adapter = registry.get("legal")

        assert adapter is not None
        assert adapter.adapter_id == "legal"
        assert adapter.sr26_tier == 1

    def test_get_adapter_not_found(self):
        """Test getting non-existent adapter."""
        registry = AdapterRegistry(self.council_dir)
        adapter = registry.get("nonexistent")

        assert adapter is None

    def test_list_by_tier(self):
        """Test listing adapters by tier."""
        self._create_metadata_file("law", 1)
        self._create_metadata_file("finance", 1)
        self._create_metadata_file("math", 2)

        registry = AdapterRegistry(self.council_dir)

        tier1_adapters = registry.list_by_tier(1)
        tier2_adapters = registry.list_by_tier(2)

        assert len(tier1_adapters) == 2
        assert len(tier2_adapters) == 1
        assert all(a.sr26_tier == 1 for a in tier1_adapters)

    def test_list_by_tier_none(self):
        """Test listing non-existent tier."""
        self._create_metadata_file("law", 1)

        registry = AdapterRegistry(self.council_dir)
        tier3_adapters = registry.list_by_tier(3)

        assert len(tier3_adapters) == 0

    def test_get_inventory(self):
        """Test getting inventory summary."""
        self._create_metadata_file("law", 1)
        self._create_metadata_file("math", 2)
        self._create_metadata_file("puzzle", 3)

        registry = AdapterRegistry(self.council_dir)
        inventory = registry.get_inventory()

        assert inventory["total_adapters"] == 3
        assert inventory["by_tier"]["tier_1_critical"] == 1
        assert inventory["by_tier"]["tier_2_elevated"] == 1
        assert inventory["by_tier"]["tier_3_benign"] == 1

    def test_get_inventory_with_list(self):
        """Test inventory includes adapter list."""
        self._create_metadata_file("test_adapter", 2)

        registry = AdapterRegistry(self.council_dir)
        inventory = registry.get_inventory()

        assert "adapters" in inventory
        assert len(inventory["adapters"]) == 1
        assert inventory["adapters"][0]["id"] == "test_adapter"

    def test_empty_council_dir(self):
        """Test handling empty council directory."""
        registry = AdapterRegistry(self.council_dir)

        assert registry.list_all() == []
        assert registry.get_inventory()["total_adapters"] == 0


class TestAdapterRegistryFactory:
    """Tests for factory function."""

    def test_create_registry(self):
        """Test factory function."""
        temp_dir = tempfile.mkdtemp()
        try:
            registry = AdapterRegistry(temp_dir)
            assert registry is not None
        finally:
            shutil.rmtree(temp_dir)


class TestAdapterMetadataFields:
    """Tests for adapter metadata field validation."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.council_dir = os.path.join(self.temp_dir, "council")
        os.makedirs(self.council_dir)

    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_metadata_has_conceptual_soundness(self):
        """Test metadata includes conceptual soundness."""
        self._create_metadata_with_cs("law", "1.0.0")

        registry = AdapterRegistry(self.council_dir)
        adapter = registry.get("law")

        assert adapter.conceptual_soundness is not None
        assert "version" in adapter.conceptual_soundness

    def test_metadata_has_risk_assessment(self):
        """Test metadata includes risk assessment."""
        self._create_metadata_with_cs("finance", "1.0.0")

        registry = AdapterRegistry(self.council_dir)
        adapter = registry.get("finance")

        assert adapter.risk_assessment is not None

    def test_metadata_has_governance(self):
        """Test metadata includes governance."""
        self._create_metadata_with_cs("legal", "1.0.0")

        registry = AdapterRegistry(self.council_dir)
        adapter = registry.get("legal")

        assert adapter.governance is not None

    def _create_metadata_with_cs(self, adapter_id: str, cs_version: str):
        """Helper to create metadata with conceptual soundness."""
        adapter_path = os.path.join(self.council_dir, f"adapter_{adapter_id}")
        os.makedirs(adapter_path)

        metadata = {
            "adapter_id": adapter_id,
            "name": f"{adapter_id.title()} Adapter",
            "version": "1.0.0",
            "sr26_tier": 1,
            "domain": "test",
            "sub_domain": "Test",
            "base_model": "test",
            "created_date": "2026-05-04",
            "conceptual_soundness": {
                "version": cs_version,
                "auditor_weight_hash": "abc123"
            },
            "risk_assessment": {
                "level": "HIGH"
            },
            "governance": {
                "requires_dhitl": True
            }
        }

        with open(os.path.join(adapter_path, "metadata.json"), 'w') as f:
            json.dump(metadata, f)