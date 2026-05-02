"""
tests/test_interview_agent.py

Unit tests for the MemorAI interview agent.
Run: pytest tests/ -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.interview_agent import InterviewAgent, CHAPTERS, CHAPTER_LABELS


@pytest.fixture
def agent():
    with patch("agents.interview_agent.CosmosDBService"), \
         patch("agents.interview_agent.AISearchService"), \
         patch("agents.interview_agent.sk.Kernel"), \
         patch("agents.interview_agent.AzureChatCompletion"):
        return InterviewAgent(senior_id="test-senior-001", language="Filipino")


@pytest.mark.asyncio
async def test_chapter_list_is_complete():
    """All 6 life chapters must be defined."""
    assert len(CHAPTERS) == 6
    for chapter in CHAPTERS:
        assert chapter in CHAPTER_LABELS


@pytest.mark.asyncio
async def test_get_session_state_returns_default_for_new_senior(agent):
    """A new senior should get a fresh session state."""
    agent.cosmos.get_profile = AsyncMock(return_value=None)

    state = await agent.get_session_state()

    assert state["senior_id"] == "test-senior-001"
    assert state["current_chapter_index"] == 0
    assert state["completed_chapters"] == []
    assert state["language"] == "Filipino"


@pytest.mark.asyncio
async def test_get_session_state_returns_existing_profile(agent):
    """An existing senior should get their saved state."""
    mock_profile = {
        "senior_id": "test-senior-001",
        "current_chapter_index": 2,
        "completed_chapters": ["childhood_and_family", "school_and_friendships"],
        "language": "Ilocano",
    }
    agent.cosmos.get_profile = AsyncMock(return_value=mock_profile)

    state = await agent.get_session_state()

    assert state["current_chapter_index"] == 2
    assert len(state["completed_chapters"]) == 2


@pytest.mark.asyncio
async def test_respond_saves_fragment(agent):
    """Each senior response must produce a saved story fragment."""
    agent.cosmos.get_profile = AsyncMock(return_value=None)
    agent.search.query_stories = AsyncMock(return_value=[])
    agent.cosmos.save_fragment = AsyncMock()
    agent.search.index_fragment = AsyncMock()
    agent.cosmos.count_fragments = AsyncMock(return_value=3)
    agent.cosmos.update_profile = AsyncMock()

    mock_response = MagicMock()
    mock_response.__str__ = lambda s: "That's a beautiful memory. Can you tell me more?"
    agent.chat_service.get_chat_message_content = AsyncMock(return_value=mock_response)

    result = await agent.respond(
        senior_message="I grew up in Ilocos Norte.",
        session_history=[],
    )

    agent.cosmos.save_fragment.assert_called_once()
    agent.search.index_fragment.assert_called_once()
    assert "agent_reply" in result
    assert "chapter" in result
    assert result["chapter"] == CHAPTERS[0]


@pytest.mark.asyncio
async def test_chapter_advances_after_threshold(agent):
    """Chapter should advance when 8+ fragments are collected."""
    agent.cosmos.get_profile = AsyncMock(return_value=None)
    agent.search.query_stories = AsyncMock(return_value=[])
    agent.cosmos.save_fragment = AsyncMock()
    agent.search.index_fragment = AsyncMock()
    agent.cosmos.count_fragments = AsyncMock(return_value=8)  # threshold reached
    agent.cosmos.update_profile = AsyncMock()

    mock_response = MagicMock()
    mock_response.__str__ = lambda s: "Let us move to the next chapter."
    agent.chat_service.get_chat_message_content = AsyncMock(return_value=mock_response)

    result = await agent.respond(
        senior_message="That is all I remember from my childhood.",
        session_history=[],
    )

    assert result["chapter_complete"] is True
    agent.cosmos.update_profile.assert_called_once()
