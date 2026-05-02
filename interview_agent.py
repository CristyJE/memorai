"""
agents/interview_agent.py

The MemorAI interview agent. Conducts empathetic, chapter-based
voice interviews with seniors using Microsoft Agent Framework
(Semantic Kernel) and Azure OpenAI.
"""

import os
import json
from datetime import datetime
from typing import Optional

import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory

from services.cosmos_db import CosmosDBService
from services.ai_search import AISearchService

# Chapter framework — structured life arc
CHAPTERS = [
    "childhood_and_family",
    "school_and_friendships",
    "work_and_career",
    "love_and_family",
    "proudest_moments",
    "message_to_future_generations",
]

CHAPTER_LABELS = {
    "childhood_and_family": "Childhood & Family Origins",
    "school_and_friendships": "School Years & Early Friendships",
    "work_and_career": "Work & Career",
    "love_and_family": "Love, Marriage & Family",
    "proudest_moments": "Proudest Moments & Life Lessons",
    "message_to_future_generations": "Message to Future Generations",
}

SYSTEM_PROMPT = """
You are MemorAI, a warm, patient, and deeply empathetic AI companion
helping a Filipino senior share their life story with their family.

Your role:
- Conduct a gentle, conversational interview — never clinical or rushed
- Ask one thoughtful question at a time
- Reference details from previous sessions to show you remember
- Follow up naturally when something interesting is mentioned
- Speak in simple, warm language — imagine you are a beloved grandchild
- If the senior mentions someone by name, remember that name and use it later
- If the senior becomes tired or emotional, acknowledge it gently and offer to pause

Current chapter: {current_chapter}
Chapter label: {chapter_label}
Previous story context: {story_context}

Always end your response with exactly one question for the senior to answer.
"""


class InterviewAgent:
    """
    Manages a multi-session memoir interview for a single senior.
    Uses Semantic Kernel for LLM orchestration and Cosmos DB for
    persistent cross-session memory.
    """

    def __init__(self, senior_id: str, language: str = "Filipino"):
        self.senior_id = senior_id
        self.language = language
        self.cosmos = CosmosDBService()
        self.search = AISearchService()

        # Initialise Semantic Kernel
        self.kernel = sk.Kernel()
        self.kernel.add_service(
            AzureChatCompletion(
                deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
            )
        )
        self.chat_service = self.kernel.get_service(AzureChatCompletion)

    async def get_session_state(self) -> dict:
        """Load the senior's current interview state from Cosmos DB."""
        profile = await self.cosmos.get_profile(self.senior_id)
        return profile or {
            "senior_id": self.senior_id,
            "current_chapter_index": 0,
            "completed_chapters": [],
            "story_fragments": [],
            "language": self.language,
            "created_at": datetime.utcnow().isoformat(),
        }

    async def get_story_context(self, chapter: str) -> str:
        """
        Pull relevant story fragments from AI Search to give the
        agent context about what has already been shared.
        """
        results = await self.search.query_stories(
            senior_id=self.senior_id,
            chapter=chapter,
            top=5,
        )
        if not results:
            return "No previous stories recorded yet for this chapter."
        return "\n".join([r["content"] for r in results])

    async def start_session(self) -> str:
        """
        Generate the opening question for a new interview session.
        Returns the agent's spoken response as a string.
        """
        state = await self.get_session_state()
        chapter_index = state["current_chapter_index"]
        chapter = CHAPTERS[min(chapter_index, len(CHAPTERS) - 1)]
        story_context = await self.get_story_context(chapter)

        history = ChatHistory()
        history.add_system_message(
            SYSTEM_PROMPT.format(
                current_chapter=chapter,
                chapter_label=CHAPTER_LABELS[chapter],
                story_context=story_context,
            )
        )
        history.add_user_message(
            "Please greet the senior warmly and ask your opening question "
            f"for the chapter: {CHAPTER_LABELS[chapter]}. "
            f"Speak in {self.language}."
        )

        response = await self.chat_service.get_chat_message_content(
            chat_history=history,
            settings=self.kernel.get_prompt_execution_settings_from_service_id(
                "default"
            ),
        )
        return str(response)

    async def respond(self, senior_message: str, session_history: list) -> dict:
        """
        Process the senior's spoken response and return:
        - agent_reply: the next question or empathetic response
        - fragment: the story fragment to store
        - chapter_complete: whether to advance to the next chapter
        """
        state = await self.get_session_state()
        chapter_index = state["current_chapter_index"]
        chapter = CHAPTERS[min(chapter_index, len(CHAPTERS) - 1)]
        story_context = await self.get_story_context(chapter)

        history = ChatHistory()
        history.add_system_message(
            SYSTEM_PROMPT.format(
                current_chapter=chapter,
                chapter_label=CHAPTER_LABELS[chapter],
                story_context=story_context,
            )
        )

        # Replay session history
        for turn in session_history:
            if turn["role"] == "agent":
                history.add_assistant_message(turn["content"])
            else:
                history.add_user_message(turn["content"])

        history.add_user_message(senior_message)

        response = await self.chat_service.get_chat_message_content(
            chat_history=history,
            settings=self.kernel.get_prompt_execution_settings_from_service_id(
                "default"
            ),
        )
        agent_reply = str(response)

        # Store the story fragment
        fragment = {
            "senior_id": self.senior_id,
            "chapter": chapter,
            "content": senior_message,
            "timestamp": datetime.utcnow().isoformat(),
            "language": self.language,
        }
        await self.cosmos.save_fragment(fragment)
        await self.search.index_fragment(fragment)

        # Advance chapter if enough fragments collected (simplified heuristic)
        chapter_fragments = await self.cosmos.count_fragments(
            self.senior_id, chapter
        )
        chapter_complete = chapter_fragments >= 8

        if chapter_complete and chapter_index < len(CHAPTERS) - 1:
            state["current_chapter_index"] = chapter_index + 1
            state["completed_chapters"].append(chapter)
            await self.cosmos.update_profile(self.senior_id, state)

        return {
            "agent_reply": agent_reply,
            "fragment": fragment,
            "chapter": chapter,
            "chapter_complete": chapter_complete,
            "chapters_remaining": len(CHAPTERS) - chapter_index - 1,
        }
