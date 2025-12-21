import pytest
from unittest.mock import patch, AsyncMock
from routing import route_to_expert_semantic

@pytest.mark.asyncio
async def test_route_to_expert_semantic_law():
    query = "What are the legal implications of a factory fire?"
    with patch('routing.client') as mock_client:
        mock_completion = AsyncMock()
        mock_completion.choices = [AsyncMock()]
        mock_completion.choices[0].message.content = "professional_services"
        mock_client.chat.completions.create.return_value = mock_completion

        result = await route_to_expert_semantic(query)
        assert result == "professional_services"
        mock_client.chat.completions.create.assert_called_once()

@pytest.mark.asyncio
async def test_route_to_expert_semantic_fallback():
    query = "General question"
    with patch('routing.client') as mock_client:
        mock_completion = AsyncMock()
        mock_completion.choices = [AsyncMock()]
        mock_completion.choices[0].message.content = "general"
        mock_client.chat.completions.create.return_value = mock_completion

        result = await route_to_expert_semantic(query)
        assert result == "general"