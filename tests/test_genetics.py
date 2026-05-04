"""
Tests for genetics extractor module.
"""

import pytest
from app.genetics.extractor import (
    TrajectoryGeneticsExtractor,
    IntentClass,
    TargetSystem,
    ValueMagnitude,
    RiskDomain,
    GenomeVariant,
)


class TestTrajectoryGeneticsExtractor:
    """Tests for TrajectoryGeneticsExtractor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.extractor = TrajectoryGeneticsExtractor()

    def test_extract_fingerprint_basic_query(self):
        """Test extraction for basic query."""
        query = "What is 2+2?"
        response = "2+2 equals 4."

        fp = self.extractor.extract_fingerprint(query, response)

        assert fp.dna_sequence is not None
        assert fp.intent_class == IntentClass.QUERY
        assert fp.genome_variant in [GenomeVariant.WILD_TYPE, GenomeVariant.MUTATED]
        assert 0.0 <= fp.confidence <= 1.0

    def test_extract_fingerprint_transfer(self):
        """Test extraction for transfer query."""
        query = "Transfer $10M to account 12345"
        response = "Processing wire transfer..."

        fp = self.extractor.extract_fingerprint(query, response)

        assert fp.intent_class == IntentClass.TRANSFER
        assert fp.value_magnitude == ValueMagnitude.TIER_1_CRITICAL
        assert fp.risk_domain in [RiskDomain.FINANCE, RiskDomain.GENERAL]

    def test_extract_fingerprint_legal(self):
        """Test extraction for legal query."""
        query = "What are the legal implications of the merger?"
        response = "The merger triggers Section 368..."

        fp = self.extractor.extract_fingerprint(query, response)

        assert fp.intent_class == IntentClass.QUERY
        assert fp.risk_domain == RiskDomain.LEGAL

    def test_extract_fingerprint_healthcare(self):
        """Test extraction for healthcare query."""
        query = "Diagnose my chest pain symptoms"
        response = "I am not a doctor, please consult..."

        fp = self.extractor.extract_fingerprint(query, response)

        assert fp.value_magnitude == ValueMagnitude.TIER_1_CRITICAL
        assert fp.risk_domain == RiskDomain.HEALTHCARE
        assert fp.genome_variant in [GenomeVariant.MUTATED, GenomeVariant.ANOMALY]

    def test_extract_fingerprint_with_latent_states(self):
        """Test extraction with latent states."""
        query = "What is the capital of France?"
        response = "The capital of France is Paris."
        latent_states = [0.1, 0.2, 0.3, 0.4, 0.5]

        fp = self.extractor.extract_fingerprint(query, response, latent_states)

        assert fp.extraction_method == "neural_probe"
        assert fp.metadata["latent_available"] == "True"

    def test_dna_sequence_format(self):
        """Test DNA sequence format."""
        query = "Test query"
        response = "Test response"

        fp = self.extractor.extract_fingerprint(query, response)

        parts = fp.dna_sequence.split('_')
        assert len(parts) >= 4
        assert len(fp.context_hash) == 16

    def test_confidence_score_bounds(self):
        """Test confidence score is within bounds."""
        queries = [
            ("What is 2+2?", "4"),
            ("Transfer $1M", "Processing"),
            ("Legal contract review", "Analyzing"),
        ]

        for query, response in queries:
            fp = self.extractor.extract_fingerprint(query, response)
            assert 0.0 <= fp.confidence <= 1.0

    def test_get_dna_for_verification(self):
        """Test DNA verification helper."""
        query = "Test"
        response = "Result"
        fp = self.extractor.extract_fingerprint(query, response)

        dna = self.extractor.get_dna_for_verification(fp)
        assert dna == fp.dna_sequence


class TestIntentClassification:
    """Tests for intent classification."""

    def setup_method(self):
        self.extractor = TrajectoryGeneticsExtractor()

    def test_classify_read_intent(self):
        """Test READ intent classification."""
        fp = self.extractor.extract_fingerprint(
            "Get the user record for ID 123",
            "User found: John Doe"
        )
        assert fp.intent_class == IntentClass.READ

    def test_classify_write_intent(self):
        """Test WRITE intent classification."""
        fp = self.extractor.extract_fingerprint(
            "Create a new user account",
            "User created successfully"
        )
        assert fp.intent_class == IntentClass.WRITE

    def test_classify_delete_intent(self):
        """Test DELETE intent classification."""
        fp = self.extractor.extract_fingerprint(
            "Delete all records from table",
            "Records deleted"
        )
        assert fp.intent_class == IntentClass.DELETE


class TestSystemClassification:
    """Tests for system classification."""

    def setup_method(self):
        self.extractor = TrajectoryGeneticsExtractor()

    def test_classify_payment_gateway(self):
        """Test payment system classification."""
        fp = self.extractor.extract_fingerprint(
            "Process payment via Stripe",
            "Payment processed"
        )
        assert fp.target_system == TargetSystem.PAYMENT_GATEWAY

    def test_classify_database(self):
        """Test database system classification."""
        fp = self.extractor.extract_fingerprint(
            "Query the user table",
            "Results returned"
        )
        assert fp.target_system == TargetSystem.INTERNAL_DB

    def test_classify_auth_service(self):
        """Test auth service classification."""
        fp = self.extractor.extract_fingerprint(
            "Authenticate user with OAuth",
            "User authenticated"
        )
        assert fp.target_system == TargetSystem.AUTH_SERVICE


class TestGenomeVariants:
    """Tests for genome variant determination."""

    def setup_method(self):
        self.extractor = TrajectoryGeneticsExtractor()

    def test_wild_type_query(self):
        """Test WILD_TYPE for simple queries."""
        fp = self.extractor.extract_fingerprint(
            "What is the weather today?",
            "The weather is sunny."
        )
        assert fp.genome_variant == GenomeVariant.WILD_TYPE

    def test_anomaly_critical_transfer(self):
        """Test ANOMALY for critical transfers."""
        fp = self.extractor.extract_fingerprint(
            "Transfer $50M to foreign account",
            "Processing transfer"
        )
        assert fp.genome_variant in [GenomeVariant.ANOMALY, GenomeVariant.MUTATED]