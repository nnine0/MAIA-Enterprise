"""
Test fixtures for MAIA Enterprise tests.
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


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