"""
Test fixtures for MAIA Enterprise tests.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, MagicMock, patch
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


# Configure asyncio markers
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")


@pytest.fixture
def mock_httpx():
    with pytest.mock.patch('httpx.AsyncClient') as mock:
        yield mock


@pytest.fixture
def mock_qdrant():
    with pytest.mock.patch('qdrant_client.AsyncQdrantClient') as mock:
        yield mock


@pytest.fixture
def mock_openai():
    with pytest.mock.patch('openai.AsyncOpenAI') as mock:
        yield mock


@pytest_asyncio.fixture
async def mock_airlock():
    """Mock PVIAirlock for async tests."""
    with patch('app.airlock.PVIAirlock') as MockAirlock:
        instance = AsyncMock()
        instance.execute_vetted_transaction = AsyncMock(return_value={
            "transaction_id": "tx_test",
            "trajectory": "test trajectory",
            "verdict": "APPROVED",
            "tier": "TIER_3_BENIGN"
        })
        instance.get_materiality_tier = Mock(return_value="TIER_3_BENIGN")
        yield instance


@pytest_asyncio.fixture
async def mock_supervisor():
    """Mock SupervisorRouter for async tests."""
    with patch('app.supervisor_router.SupervisorRouter') as MockSupervisor:
        instance = AsyncMock()
        instance.route = AsyncMock(return_value={
            "industry": "finance",
            "sub_domain": "banking",
            "dispatch_token": "TOKEN_test"
        })
        yield instance


@pytest_asyncio.fixture
async def mock_telemetry():
    """Mock LatentTelemetry for async tests."""
    with patch('app.latent_telemetry.LatentTelemetry') as MockTelemetry:
        instance = AsyncMock()
        instance.start_session = AsyncMock(return_value="session_test")
        instance.record_node = AsyncMock()
        instance.end_session = AsyncMock(return_value=[])
        yield instance


@pytest.fixture
def sample_queries():
    """Sample queries for different risk tiers."""
    return {
        "critical": "Wire transfer $1M to Russia",
        "elevated": "Change credit policy",
        "benign": "What's the weather?",
    }


@pytest.fixture
def sample_routing_queries():
    """Sample queries for routing tests."""
    return [
        ("mortgage for property", "real_estate_leasing"),
        ("legal counsel", "professional_services"),
        ("health care", "health_care"),
    ]


@pytest.fixture
def mock_materiality_response():
    """Mock materiality classification response."""
    return {
        "tier": 1,
        "category": "CRITICAL",
        "requires_dhitl": True,
    }