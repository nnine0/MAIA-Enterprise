"""
Tests for Conceptual Soundness module.
"""

import pytest
import json
import tempfile
import os
from app.conceptual_soundness import (
    ConceptualSoundnessExplainer,
    ConceptualSoundnessProof,
    LogicStep,
    FeatureAttribution,
)


class TestConceptualSoundnessExplainer:
    """Tests for ConceptualSoundnessExplainer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.explainer = ConceptualSoundnessExplainer()

    def test_explainer_creation(self):
        """Test explainer creation."""
        assert self.explainer is not None

    def test_explainer_with_model_registry(self):
        """Test explainer with model card registry."""
        registry = {"law": {"version": "1.0.0"}, "finance": {"version": "2.0.0"}}
        explainer = ConceptualSoundnessExplainer(model_card_registry=registry)
        assert explainer.model_card_registry == registry

    def test_generate_proof_basic(self):
        """Test generating basic proof."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_001",
            adapter_id="law",
            sr26_tier=1,
            query="What are the tax implications?",
            response="The merger triggers Section 368...",
            auditor_reasoning="VERDICT: PASS"
        )

        assert proof.transaction_id == "tx_001"
        assert proof.adapter_id == "law"
        assert proof.sr26_tier == 1
        assert proof.latent_hash is not None

    def test_generate_proof_with_latent_states(self):
        """Test generating proof with latent states."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_002",
            adapter_id="finance",
            sr26_tier=1,
            query="Test query",
            response="Test response",
            auditor_reasoning="Approved",
            latent_states=[0.1, 0.2, 0.3, 0.4, 0.5]
        )

        assert proof.latent_integrity_verified is True
        assert proof.latent_hash != "N/A"

    def test_generate_proof_without_latent_states(self):
        """Test generating proof without latent states."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_003",
            adapter_id="law",
            sr26_tier=2,
            query="Test",
            response="Result",
            auditor_reasoning="OK"
        )

        assert proof.latent_integrity_verified is False

    def test_proof_has_logic_chain(self):
        """Test proof includes logic chain."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_004",
            adapter_id="legal",
            sr26_tier=1,
            query="Explain the contract",
            response="First, the terms are defined. Therefore, the obligations apply. Hence, compliance is required.",
            auditor_reasoning="PASS"
        )

        assert len(proof.logic_chain) > 0
        assert isinstance(proof.logic_chain[0], LogicStep)

    def test_proof_has_feature_attributions(self):
        """Test proof includes feature attributions."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_005",
            adapter_id="legal",
            sr26_tier=1,
            query="What are the tax implications?",
            response="The tax implications involve...",
            auditor_reasoning="Approved"
        )

        assert len(proof.feature_attributions) > 0
        assert isinstance(proof.feature_attributions[0], FeatureAttribution)

    def test_proof_has_decision_justification(self):
        """Test proof includes decision justification."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_006",
            adapter_id="legal",
            sr26_tier=1,
            query="Test query",
            response="Test response",
            auditor_reasoning="Approved"
        )

        assert proof.decision_justification is not None
        assert len(proof.decision_justification) > 0

    def test_proof_query_preview(self):
        """Test proof includes query preview."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_007",
            adapter_id="law",
            sr26_tier=1,
            query="What are the tax implications of our merger?",
            response="Response",
            auditor_reasoning="OK"
        )

        assert proof.query_preview in "What are the tax implications of our merger?"

    def test_proof_model_card_version(self):
        """Test proof includes model card version when available."""
        registry = {"law": {"version": "1.2.3"}}
        explainer = ConceptualSoundnessExplainer(model_card_registry=registry)

        proof = explainer.generate_proof(
            transaction_id="tx_008",
            adapter_id="law",
            sr26_tier=1,
            query="Test",
            response="Result",
            auditor_reasoning="OK"
        )

        assert proof.model_card_version == "1.2.3"


class TestLogicStep:
    """Tests for LogicStep dataclass."""

    def test_logic_step_creation(self):
        """Test LogicStep creation."""
        step = LogicStep(
            step_number=1,
            premise="Given that X",
            inference="Therefore Y",
            confidence=0.85,
            weight_activated="lora_layer_0_head_0"
        )

        assert step.step_number == 1
        assert step.confidence == 0.85


class TestFeatureAttribution:
    """Tests for FeatureAttribution dataclass."""

    def test_feature_attribution_creation(self):
        """Test FeatureAttribution creation."""
        attr = FeatureAttribution(
            feature="tax",
            contribution=0.75,
            token_range=(0, 10),
            direction="positive"
        )

        assert attr.feature == "tax"
        assert attr.contribution == 0.75
        assert attr.direction == "positive"


class TestConceptualSoundnessProof:
    """Tests for ConceptualSoundnessProof dataclass."""

    def setup_method(self):
        """Set up test fixtures."""
        self.explainer = ConceptualSoundnessExplainer()

    def test_proof_timestamp(self):
        """Test proof includes timestamp."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_009",
            adapter_id="law",
            sr26_tier=1,
            query="Test",
            response="Result",
            auditor_reasoning="OK"
        )

        assert proof.timestamp is not None

    def test_proof_explainability_version(self):
        """Test proof includes explainability version."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_010",
            adapter_id="law",
            sr26_tier=1,
            query="Test",
            response="Result",
            auditor_reasoning="OK"
        )

        assert proof.explainability_version == "1.0.0"


class TestExportProofPackage:
    """Tests for proof package export."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.explainer = ConceptualSoundnessExplainer()

    def teardown_method(self):
        """Clean up temp files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_export_proof_package(self):
        """Test exporting proof package."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_export",
            adapter_id="law",
            sr26_tier=1,
            query="Test query",
            response="Test response",
            auditor_reasoning="Approved"
        )

        output_path = os.path.join(self.temp_dir, "proof.json")
        self.explainer.export_proof_package(proof, output_path)

        assert os.path.exists(output_path)

        with open(output_path, 'r') as f:
            data = json.load(f)
            assert data["transaction_id"] == "tx_export"
            assert "logic_chain" in data
            assert "feature_attributions" in data

    def test_export_creates_directory(self):
        """Test export creates parent directory."""
        proof = self.explainer.generate_proof(
            transaction_id="tx_export2",
            adapter_id="law",
            sr26_tier=1,
            query="Test",
            response="Result",
            auditor_reasoning="OK"
        )

        output_path = os.path.join(self.temp_dir, "subdir", "proof.json")
        self.explainer.export_proof_package(proof, output_path)

        assert os.path.exists(output_path)