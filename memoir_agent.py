"""
agents/memoir_agent.py

The MemorAI memoir compilation agent. Pulls all story fragments
from Cosmos DB and Azure AI Search, then uses Azure OpenAI to
generate a polished, chapter-structured memoir.
"""

import os
from typing import Optional

import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory

from services.cosmos_db import CosmosDBService
from services.ai_search import AISearchService
from services.translator import TranslatorService

MEMOIR_SYSTEM_PROMPT = """
You are a skilled biographer helping compile a memoir for a Filipino senior.
You will receive raw story fragments from recorded interviews and transform
them into beautifully written, flowing prose — warm, dignified, and personal.

Guidelines:
- Write in the first person, as if the senior is narrating
- Preserve the senior's personality — their humor, their values, their voice
- Do not invent facts; only use what is in the story fragments
- Names of people and places must be kept exactly as given
- Each chapter should open with a vivid, evocative sentence
- Tone: reflective, warm, slightly literary — like a cherished letter to grandchildren
"""

CHAPTER_PROMPT_TEMPLATE = """
Chapter: {chapter_label}

Here are the raw story fragments from the senior's interview sessions
for this chapter. Compile them into a flowing, 300–500 word memoir passage.

Story fragments:
{fragments}

Write the memoir passage now.
"""


class MemoirAgent:
    """
    Compiles a complete memoir from all recorded story fragments
    for a given senior. Supports output in multiple Philippine languages.
    """

    def __init__(self, senior_id: str):
        self.senior_id = senior_id
        self.cosmos = CosmosDBService()
        self.search = AISearchService()
        self.translator = TranslatorService()

        self.kernel = sk.Kernel()
        self.kernel.add_service(
            AzureChatCompletion(
                deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
            )
        )
        self.chat_service = self.kernel.get_service(AzureChatCompletion)

    async def compile_chapter(self, chapter: str, chapter_label: str) -> str:
        """Generate a memoir passage for a single chapter."""
        fragments = await self.search.get_all_fragments(
            senior_id=self.senior_id,
            chapter=chapter,
        )

        if not fragments:
            return ""

        fragment_text = "\n\n".join(
            [f"[Session {i+1}]: {f['content']}" for i, f in enumerate(fragments)]
        )

        history = ChatHistory()
        history.add_system_message(MEMOIR_SYSTEM_PROMPT)
        history.add_user_message(
            CHAPTER_PROMPT_TEMPLATE.format(
                chapter_label=chapter_label,
                fragments=fragment_text,
            )
        )

        response = await self.chat_service.get_chat_message_content(
            chat_history=history,
            settings=self.kernel.get_prompt_execution_settings_from_service_id(
                "default"
            ),
        )
        return str(response)

    async def compile_full_memoir(
        self,
        target_language: Optional[str] = None,
    ) -> dict:
        """
        Compile the complete memoir across all chapters.
        Optionally translate the result to a Philippine language.

        Args:
            target_language: ISO code — 'fil' (Filipino), 'ilo' (Ilocano),
                             'ceb' (Cebuano/Bisaya), or None for English.

        Returns:
            A dict with chapter titles as keys and memoir passages as values,
            plus metadata.
        """
        from agents.interview_agent import CHAPTERS, CHAPTER_LABELS

        profile = await self.cosmos.get_profile(self.senior_id)
        senior_name = profile.get("name", "Our Loved One") if profile else "Our Loved One"

        memoir = {
            "senior_id": self.senior_id,
            "senior_name": senior_name,
            "language": target_language or "en",
            "chapters": {},
            "completed_chapters": [],
        }

        for chapter in CHAPTERS:
            label = CHAPTER_LABELS[chapter]
            print(f"Compiling chapter: {label}")
            passage = await self.compile_chapter(chapter, label)

            if not passage:
                continue

            if target_language and target_language != "en":
                passage = await self.translator.translate(
                    text=passage,
                    target_language=target_language,
                )

            memoir["chapters"][chapter] = {
                "label": label,
                "content": passage,
            }
            memoir["completed_chapters"].append(chapter)

        # Persist the compiled memoir
        await self.cosmos.save_memoir(self.senior_id, memoir)

        return memoir

    async def generate_title_and_dedication(self, memoir: dict) -> dict:
        """Generate a memoir title and family dedication page."""
        chapter_summaries = " ".join(
            [c["content"][:200] for c in memoir["chapters"].values()]
        )

        history = ChatHistory()
        history.add_system_message(MEMOIR_SYSTEM_PROMPT)
        history.add_user_message(
            f"Based on this memoir for {memoir['senior_name']}, write: "
            f"1) A short, beautiful memoir title (max 8 words). "
            f"2) A one-paragraph dedication to the family. "
            f"Here is a summary of the memoir: {chapter_summaries}. "
            f"Return as JSON: {{\"title\": \"...\", \"dedication\": \"...\"}}"
        )

        response = await self.chat_service.get_chat_message_content(
            chat_history=history,
            settings=self.kernel.get_prompt_execution_settings_from_service_id(
                "default"
            ),
        )

        import json
        try:
            meta = json.loads(str(response))
            memoir["title"] = meta.get("title", f"The Story of {memoir['senior_name']}")
            memoir["dedication"] = meta.get("dedication", "")
        except json.JSONDecodeError:
            memoir["title"] = f"The Story of {memoir['senior_name']}"
            memoir["dedication"] = ""

        return memoir
