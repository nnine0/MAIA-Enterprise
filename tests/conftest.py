import pytest
from unittest.mock import AsyncMock, Mock
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