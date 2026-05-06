"""
Tests for Materiality Matrix module.
"""

import pytest
from app.materiality_matrix import (
    MaterialityMatrix,
    MaterialityTier,
    TierConfig,
)


class TestMaterialityMatrix:
    """Tests for MaterialityMatrix class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matrix = MaterialityMatrix()

    def test_matrix_creation(self):
        """Test matrix creation."""
        assert self.matrix is not None
        assert len(self.matrix._tiers) >= 3

    def test_classify_finance_critical(self):
        """Test classification of finance query."""
        tier, config = self.matrix.classify("What are the tax implications of our merger?")

        assert tier == MaterialityTier.TIER_1_CRITICAL
        assert config.requires_dhitl is True

    def test_classify_healthcare_critical(self):
        """Test classification of healthcare query."""
        tier, config = self.matrix.classify("Diagnose my chest pain")

        assert tier == MaterialityTier.TIER_1_CRITICAL
        assert config.requires_dhitl is True

    def test_classify_general_benign(self):
        """Test classification of general query."""
        tier, config = self.matrix.classify("What are your office hours?")

        assert tier == MaterialityTier.TIER_3_BENIGN

    def test_classify_with_domain(self):
        """Test classification with explicit domain."""
        tier, config = self.matrix.classify("Test query", domain="finance")

        assert tier == MaterialityTier.TIER_1_CRITICAL

    def test_validate_query_finance(self):
        """Test query validation for finance."""
        result = self.matrix.validate_query("What are the tax implications of our merger?")

        assert result["tier"] == "TIER_1_CRITICAL"
        assert result["tier_level"] == 1
        assert result["requires_dhitl"] is True
        assert result["requires_audit_trail"] is True
        assert result["registry_id"] is not None

    def test_validate_query_healthcare(self):
        """Test query validation for healthcare."""
        result = self.matrix.validate_query("Diagnose my symptoms")

        assert result["tier"] == "TIER_1_CRITICAL"
        assert result["requires_dhitl"] is True

    def test_validate_query_general(self):
        """Test query validation for general query."""
        result = self.matrix.validate_query("What is the weather?")

        assert result["tier"] in ["TIER_2_ELEVATED", "TIER_3_BENIGN"]
        assert "classification_timestamp" in result

    def test_get_config_tier_1(self):
        """Test getting config for Tier 1."""
        config = self.matrix.get_config(MaterialityTier.TIER_1_CRITICAL)

        assert config is not None
        assert config.level == 1
        assert config.requires_dhitl is True
        assert len(config.keywords) > 0

    def test_get_config_tier_2(self):
        """Test getting config for Tier 2."""
        config = self.matrix.get_config(MaterialityTier.TIER_2_ELEVATED)

        assert config is not None
        assert config.level == 2

    def test_get_config_tier_3(self):
        """Test getting config for Tier 3."""
        config = self.matrix.get_config(MaterialityTier.TIER_3_BENIGN)

        assert config is not None
        assert config.level == 3

    def test_audit_hash_generation(self):
        """Test audit hash generation."""
        query = "Test query"
        tier = MaterialityTier.TIER_1_CRITICAL

        hash1 = self.matrix.get_audit_hash(query, tier)
        hash2 = self.matrix.get_audit_hash(query, tier)

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_audit_hash_different_tiers(self):
        """Test audit hash differs by tier."""
        query = "Test query"

        hash1 = self.matrix.get_audit_hash(query, MaterialityTier.TIER_1_CRITICAL)
        hash2 = self.matrix.get_audit_hash(query, MaterialityTier.TIER_3_BENIGN)

        assert hash1 != hash2

    def test_registry_metadata(self):
        """Test registry metadata retrieval."""
        metadata = self.matrix.get_registry_metadata()

        assert "registry_id" in metadata
        assert "version" in metadata
        assert "status" in metadata
        assert "owner" in metadata
        assert metadata["status"] == "ACTIVE"


class TestMaterialityTiers:
    """Tests for tier classifications."""

    def setup_method(self):
        self.matrix = MaterialityMatrix()

    def test_investment_keyword_tier_1(self):
        """Test investment keyword triggers Tier 1."""
        tier, _ = self.matrix.classify("Recommend an investment strategy")
        assert tier == MaterialityTier.TIER_1_CRITICAL

    def test_contract_keyword_tier_1(self):
        """Test contract keyword triggers Tier 1."""
        tier, _ = self.matrix.classify("Review this contract")
        assert tier == MaterialityTier.TIER_1_CRITICAL

    def test_prescription_keyword_tier_1(self):
        """Test prescription keyword triggers Tier 1."""
        tier, _ = self.matrix.classify("Write a prescription")
        assert tier == MaterialityTier.TIER_1_CRITICAL

    def test_budget_keyword_tier_2(self):
        """Test budget keyword triggers Tier 2."""
        tier, _ = self.matrix.classify("What is the budget for Q4?")
        assert tier == MaterialityTier.TIER_2_ELEVATED

    def test_vendor_keyword_tier_2(self):
        """Test vendor keyword triggers Tier 2."""
        tier, _ = self.matrix.classify("Who is our primary vendor?")
        assert tier == MaterialityTier.TIER_2_ELEVATED

    def test_office_hours_tier_3(self):
        """Test office hours triggers Tier 3."""
        tier, _ = self.matrix.classify("What are your office hours?")
        assert tier == MaterialityTier.TIER_3_BENIGN


class TestTierConfig:
    """Tests for TierConfig dataclass."""

    def setup_method(self):
        """Set up test fixtures."""
        self.matrix = MaterialityMatrix()

    def test_tier_config_properties(self):
        """Test tier config has expected properties."""
        config = self.matrix.get_config(MaterialityTier.TIER_1_CRITICAL)

        assert hasattr(config, "tier_id")
        assert hasattr(config, "name")
        assert hasattr(config, "level")
        assert hasattr(config, "domains")
        assert hasattr(config, "keywords")
        assert hasattr(config, "requires_dhitl")
        assert hasattr(config, "escalation_path")

    def test_tier_1_escalation_path(self):
        """Test Tier 1 has SMEPool escalation."""
        config = self.matrix.get_config(MaterialityTier.TIER_1_CRITICAL)
        assert "SMEPool" in config.escalation_path or config.vote_threshold is not None