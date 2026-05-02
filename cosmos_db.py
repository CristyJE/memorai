"""
services/cosmos_db.py

Azure Cosmos DB wrapper for MemorAI story fragment and profile storage.
Uses the NoSQL (Core) API with a document-per-fragment pattern.
"""

import os
import uuid
from datetime import datetime
from typing import Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions


class CosmosDBService:
    """
    Manages all Cosmos DB operations for MemorAI:
    - Senior profiles and interview state
    - Story fragments (one document per interview turn)
    - Compiled memoir storage
    """

    def __init__(self):
        self.client = CosmosClient(
            url=os.environ["COSMOS_ENDPOINT"],
            credential=os.environ["COSMOS_KEY"],
        )
        self.db_name = os.environ["COSMOS_DB_NAME"]
        self.stories_container = os.environ.get(
            "COSMOS_CONTAINER_STORIES", "stories"
        )
        self.profiles_container = os.environ.get(
            "COSMOS_CONTAINER_PROFILES", "profiles"
        )

    async def _get_container(self, container_name: str):
        db = self.client.get_database_client(self.db_name)
        return db.get_container_client(container_name)

    # ── Profiles ──────────────────────────────────────────────────────────

    async def get_profile(self, senior_id: str) -> Optional[dict]:
        """Retrieve a senior's profile and interview state."""
        container = await self._get_container(self.profiles_container)
        try:
            item = await container.read_item(
                item=senior_id, partition_key=senior_id
            )
            return item
        except exceptions.CosmosResourceNotFoundError:
            return None

    async def create_profile(self, profile: dict) -> dict:
        """Create a new senior profile."""
        profile["id"] = profile.get("senior_id", str(uuid.uuid4()))
        profile["created_at"] = datetime.utcnow().isoformat()
        container = await self._get_container(self.profiles_container)
        return await container.create_item(body=profile)

    async def update_profile(self, senior_id: str, updates: dict) -> dict:
        """Update an existing senior profile (upsert)."""
        updates["id"] = senior_id
        updates["senior_id"] = senior_id
        updates["updated_at"] = datetime.utcnow().isoformat()
        container = await self._get_container(self.profiles_container)
        return await container.upsert_item(body=updates)

    # ── Story fragments ───────────────────────────────────────────────────

    async def save_fragment(self, fragment: dict) -> dict:
        """
        Save a single story fragment from an interview turn.

        Fragment schema:
            id: auto-generated UUID
            senior_id: partition key
            chapter: e.g. 'childhood_and_family'
            content: the senior's spoken text (transcribed)
            timestamp: ISO 8601
            language: 'Filipino' | 'Ilocano' | 'Bisaya' | 'English'
        """
        fragment["id"] = str(uuid.uuid4())
        fragment.setdefault("timestamp", datetime.utcnow().isoformat())
        container = await self._get_container(self.stories_container)
        return await container.create_item(body=fragment)

    async def get_fragments(
        self,
        senior_id: str,
        chapter: Optional[str] = None,
        limit: int = 50,
    ) -> list:
        """
        Retrieve story fragments for a senior, optionally filtered by chapter.
        """
        container = await self._get_container(self.stories_container)

        if chapter:
            query = (
                "SELECT * FROM c WHERE c.senior_id = @senior_id "
                "AND c.chapter = @chapter ORDER BY c.timestamp ASC "
                f"OFFSET 0 LIMIT {limit}"
            )
            params = [
                {"name": "@senior_id", "value": senior_id},
                {"name": "@chapter", "value": chapter},
            ]
        else:
            query = (
                "SELECT * FROM c WHERE c.senior_id = @senior_id "
                f"ORDER BY c.timestamp ASC OFFSET 0 LIMIT {limit}"
            )
            params = [{"name": "@senior_id", "value": senior_id}]

        items = []
        async for item in container.query_items(
            query=query,
            parameters=params,
            partition_key=senior_id,
        ):
            items.append(item)
        return items

    async def count_fragments(self, senior_id: str, chapter: str) -> int:
        """Count story fragments for a given chapter."""
        fragments = await self.get_fragments(senior_id, chapter)
        return len(fragments)

    # ── Memoir ────────────────────────────────────────────────────────────

    async def save_memoir(self, senior_id: str, memoir: dict) -> dict:
        """Persist the compiled memoir document."""
        memoir["id"] = f"memoir_{senior_id}"
        memoir["senior_id"] = senior_id
        memoir["compiled_at"] = datetime.utcnow().isoformat()
        container = await self._get_container(self.profiles_container)
        return await container.upsert_item(body=memoir)

    async def get_memoir(self, senior_id: str) -> Optional[dict]:
        """Retrieve the compiled memoir for a senior."""
        container = await self._get_container(self.profiles_container)
        try:
            return await container.read_item(
                item=f"memoir_{senior_id}",
                partition_key=senior_id,
            )
        except exceptions.CosmosResourceNotFoundError:
            return None
