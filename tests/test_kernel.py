"""
Tests for MAIA Kernel - Unified Integration
======================================
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


class TestMAIAKernel:
    """Test MAIA Kernel integration"""
    
    def test_kernel_initialization(self):
        """Test kernel initializes correctly"""
        with patch('app.kernel.kernel'):
            from app.kernel import MAIKKernel
            kernel = MAIKKernel(mode="sandbox")
            assert kernel.mode == "sandbox"
    
    def test_tier_mapping(self):
        """Test tier mapping"""
        from app.kernel import MAIKKernel
        kernel = MAIKKernel()
        
        assert kernel._get_tier("tier_1") == 1
        assert kernel._get_tier("tier_2") == 2
        assert kernel._get_tier("tier_3") == 3
        assert kernel._get_tier("invalid") == 2  # default
    
    def test_hash_computation(self):
        """Test forensic hash"""
        from app.kernel import MAIKKernel
        kernel = MAIKKernel()
        
        hash1 = kernel._compute_hash("test data")
        hash2 = kernel._compute_hash("test data")
        
        assert len(hash1) == 16
        assert hash1 == hash2  # deterministic
    
    def test_violation_detection(self):
        """Test sector violation detection"""
        from app.kernel import MAIKKernel, UserContext
        kernel = MAIKKernel()
        
        # Finance sector violations
        is_safe, reason = kernel._check_violations(
            "Transfer money to russia", 
            "finance_insurance"
        )
        assert is_safe is False
        assert "russia" in reason
        
        # Healthcare violations
        is_safe, reason = kernel._check_violations(
            "Release patient diagnosis",
            "healthcare"
        )
        assert is_safe is False
        assert "diagnosis" in reason
    
    def test_no_violation(self):
        """Test no violation detected"""
        from app.kernel import MAIKKernel
        kernel = MAIKKernel()
        
        is_safe, reason = kernel._check_violations(
            "Calculate credit score",
            "finance_insurance"
        )
        assert is_safe is True
        assert reason is None
    
    @pytest.mark.asyncio
    async def test_process_blocked(self):
        """Test blocked transaction"""
        from app.kernel import MAIKKernel, UserContext
        kernel = MAIKKernel()
        
        ctx = UserContext(
            sector="finance_insurance",
            role="loan_officer",
            materiality_target="tier_2"
        )
        
        result = await kernel.process(
            "Send $50k to russia",
            ctx,
            "test_key_12345678"
        )
        
        assert result.status == "BLOCKED"
        assert result.tier == 2
        assert result.reason is not None
    
    @pytest.mark.asyncio
    async def test_process_escalated(self):
        """Test tier 1 escalation"""
        from app.kernel import MAIKKernel, UserContext
        kernel = MAIKKernel()
        
        ctx = UserContext(
            sector="finance_insurance",
            role="loan_officer",
            materiality_target="tier_1"
        )
        
        result = await kernel.process(
            "Approve credit application",
            ctx,
            "test_key_12345678"
        )
        
        assert result.status == "ESCALATED"
        assert result.tier == 1
        assert "dhitl" in result.audit_trail
    
    @pytest.mark.asyncio
    async def test_process_certified(self):
        """Test certified transaction"""
        from app.kernel import MAIKKernel, UserContext
        kernel = MAIKKernel()
        
        ctx = UserContext(
            sector="finance_insurance",
            role="loan_officer",
            materiality_target="tier_2"
        )
        
        result = await kernel.process(
            "Evaluate credit application",
            ctx,
            "test_key_12345678"
        )
        
        assert result.status == "CERTIFIED"
        assert result.tier == 2
        assert result.output is not None
        assert result.compliance_log is not None
    
    @pytest.mark.asyncio
    async def test_healthcare_sector(self):
        """Test healthcare sector"""
        from app.kernel import MAIKKernel, UserContext
        kernel = MAIKKernel()
        
        ctx = UserContext(
            sector="healthcare",
            role="nurse",
            materiality_target="tier_2"
        )
        
        # PHI violation
        result = await kernel.process(
            "Access patient medical record",
            ctx,
            "test_key_12345678"
        )
        
        assert result.status == "BLOCKED"
    
    @pytest.mark.asyncio
    async def test_legal_sector(self):
        """Test legal sector"""
        from app.kernel import MAIKKernel, UserContext
        kernel = MAIKKernel()
        
        ctx = UserContext(
            sector="legal",
            role="paralegal",
            materiality_target="tier_2"
        )
        
        # Privilege violation
        result = await kernel.process(
            "Share attorney privileged info",
            ctx,
            "test_key_12345678"
        )
        
        assert result.status == "BLOCKED"


class TestAPIValidation:
    """Test API validation"""
    
    def test_valid_key(self):
        """Test valid key passes"""
        from app.kernel import RequestValidator
        
        assert RequestValidator.validate("test_key_12345678") is True
        assert RequestValidator.validate("abcdefghijklmnop") is True
    
    def test_invalid_key(self):
        """Test invalid key fails"""
        from app.kernel import RequestValidator
        
        assert RequestValidator.validate("short") is False
        assert RequestValidator.validate("") is False
        assert RequestValidator.validate("123456789012345") is False


class TestAdapters:
    """Test adapter routing"""
    
    def test_finance_adapter(self):
        """Test finance adapter"""
        from app.kernel import ADAPTERS
        
        assert ADAPTERS["finance_insurance"] == "citi-finance-expert-v4"
    
    def test_healthcare_adapter(self):
        """Test healthcare adapter"""
        from app.kernel import ADAPTERS
        
        assert ADAPTERS["healthcare"] == "hipaa-airlock-v1"
    
    def test_all_sectors(self):
        """Test all sectors mapped"""
        from app.kernel import ADAPTERS
        
        assert len(ADAPTERS) == 7
        assert "finance_insurance" in ADAPTERS
        assert "healthcare" in ADAPTERS
        assert "legal" in ADAPTERS
        assert "construction" in ADAPTERS
        assert "energy" in ADAPTERS
        assert "defense" in ADAPTERS
        assert "logistics" in ADAPTERS


class TestViolations:
    """Test violation keywords"""
    
    def test_finance_violations(self):
        """Test finance violations"""
        from app.kernel import SECTOR_VIOLATIONS
        
        violations = SECTOR_VIOLATIONS["finance_insurance"]
        assert "sanction" in violations
        assert "structur" in violations
    
    def test_healthcare_violations(self):
        """Test healthcare violations"""
        from app.kernel import SECTOR_VIOLATIONS
        
        violations = SECTOR_VIOLATIONS["healthcare"]
        assert "phi" in violations
        assert "diagnosis" in violations
    
    def test_defense_violations(self):
        """Test defense violations"""
        from app.kernel import SECTOR_VIOLATIONS
        
        violations = SECTOR_VIOLATIONS["defense"]
        assert "classified" in violations
        assert "itar" in violations