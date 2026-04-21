"""
Session Memory using Redis.
Stores short-term conversation context with TTL expiration.
Tracks: current intent, conversation history, pending actions, language preference.
"""
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)


class SessionMemory:
    """
    Redis-backed session memory for conversation context.
    Falls back to an in-memory dict when Redis is unavailable.
    Each session has a TTL (default 1 hour) for automatic cleanup.
    """

    def __init__(self):
        self.redis_url = settings.redis_url
        self.session_ttl = settings.session_ttl
        self._client: Optional[aioredis.Redis] = None
        self._redis_available: bool = True
        self._in_memory_store: Dict[str, dict] = {}
        logger.info(f"Session Memory initialized with TTL={self.session_ttl}s")

    async def get_client(self) -> Optional[aioredis.Redis]:
        """Get or create Redis client. Returns None if Redis is unavailable."""
        if not self._redis_available:
            return None
        if self._client is None:
            try:
                self._client = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20,
                    socket_connect_timeout=2,
                )
                # Verify connection
                await self._client.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
                self._client = None
                self._redis_available = False
        return self._client

    async def create_session(self, session_id: str, patient_id: Optional[str] = None) -> dict:
        """
        Create a new conversation session.

        Args:
            session_id: Unique session identifier
            patient_id: Optional patient ID if known

        Returns:
            Initial session state
        """
        session_data = {
            "session_id": session_id,
            "patient_id": patient_id,
            "language": settings.default_language,
            "conversation_history": [],
            "current_intent": None,
            "pending_slots": {},
            "confirmed_slots": {},
            "last_action": None,
            "turn_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        await self.save_session(session_id, session_data)
        logger.info(f"Created new session: {session_id}")
        return session_data

    async def get_session(self, session_id: str) -> Optional[dict]:
        """
        Retrieve session data from Redis.

        Args:
            session_id: Session identifier

        Returns:
            Session data dict or None if not found
        """
        client = await self.get_client()
        key = self._session_key(session_id)

        if client is None:
            # In-memory fallback
            return self._in_memory_store.get(key)

        try:
            data = await client.get(key)
            if data:
                session = json.loads(data)
                # Refresh TTL on access
                await client.expire(key, self.session_ttl)
                return session
            return None
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return self._in_memory_store.get(key)

    async def save_session(self, session_id: str, session_data: dict) -> bool:
        """
        Save session data to Redis with TTL.

        Args:
            session_id: Session identifier
            session_data: Session data to save

        Returns:
            True if saved successfully
        """
        client = await self.get_client()
        key = self._session_key(session_id)
        session_data["updated_at"] = datetime.utcnow().isoformat()

        if client is None:
            # In-memory fallback
            self._in_memory_store[key] = session_data
            return True

        try:
            await client.setex(
                key,
                self.session_ttl,
                json.dumps(session_data, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.error(f"Error saving session {session_id}: {e}")
            # Fall back to in-memory on Redis write failure
            self._in_memory_store[key] = session_data
            return True

    async def update_session(self, session_id: str, updates: dict) -> Optional[dict]:
        """
        Update specific fields in a session.

        Args:
            session_id: Session identifier
            updates: Dict of fields to update

        Returns:
            Updated session data or None
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for update")
            return None

        session.update(updates)
        await self.save_session(session_id, session)
        return session

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        language: str = "en",
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Add a message to conversation history.

        Args:
            session_id: Session identifier
            role: Message role (user/assistant/system)
            content: Message content
            language: Language code
            metadata: Optional metadata (latency, etc.)

        Returns:
            True if added successfully
        """
        session = await self.get_session(session_id)
        if not session:
            session = await self.create_session(session_id)

        message = {
            "role": role,
            "content": content,
            "language": language,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if metadata:
            message["metadata"] = metadata

        session["conversation_history"].append(message)
        session["turn_count"] = session.get("turn_count", 0) + 1

        # Keep only last 20 messages to prevent memory bloat
        if len(session["conversation_history"]) > 20:
            session["conversation_history"] = session["conversation_history"][-20:]

        return await self.save_session(session_id, session)

    async def get_conversation_history(
        self,
        session_id: str,
        max_turns: int = 10
    ) -> List[dict]:
        """
        Get recent conversation history for LLM context.

        Args:
            session_id: Session identifier
            max_turns: Maximum number of turns to return

        Returns:
            List of message dicts
        """
        session = await self.get_session(session_id)
        if not session:
            return []

        history = session.get("conversation_history", [])
        return history[-max_turns * 2:]  # Each turn = user + assistant

    async def set_intent(self, session_id: str, intent: str, slots: dict = None) -> bool:
        """Set current conversation intent and slots."""
        updates = {
            "current_intent": intent,
            "pending_slots": slots or {},
        }
        result = await self.update_session(session_id, updates)
        return result is not None

    async def update_slots(self, session_id: str, slots: dict) -> bool:
        """Update pending slots for current intent."""
        session = await self.get_session(session_id)
        if not session:
            return False

        pending = session.get("pending_slots", {})
        pending.update(slots)
        session["pending_slots"] = pending

        return await self.save_session(session_id, session)

    async def confirm_slots(self, session_id: str) -> bool:
        """Move pending slots to confirmed slots."""
        session = await self.get_session(session_id)
        if not session:
            return False

        session["confirmed_slots"] = session.get("pending_slots", {})
        session["pending_slots"] = {}

        return await self.save_session(session_id, session)

    async def set_language(self, session_id: str, language: str) -> bool:
        """Update session language preference."""
        return await self.update_session(session_id, {"language": language}) is not None

    async def get_language(self, session_id: str) -> str:
        """Get current session language."""
        session = await self.get_session(session_id)
        if session:
            return session.get("language", settings.default_language)
        return settings.default_language

    async def clear_intent(self, session_id: str) -> bool:
        """Clear current intent after completion."""
        updates = {
            "current_intent": None,
            "pending_slots": {},
            "confirmed_slots": {},
            "last_action": None,
        }
        result = await self.update_session(session_id, updates)
        return result is not None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from Redis or in-memory store."""
        client = await self.get_client()
        key = self._session_key(session_id)

        self._in_memory_store.pop(key, None)

        if client is None:
            logger.info(f"Deleted session (in-memory): {session_id}")
            return True

        try:
            await client.delete(key)
            logger.info(f"Deleted session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    async def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        client = await self.get_client()

        if client is None:
            return len([k for k in self._in_memory_store if k.startswith("session:")])

        try:
            keys = await client.keys("session:*")
            return len(keys)
        except Exception as e:
            logger.error(f"Error counting sessions: {e}")
            return len([k for k in self._in_memory_store if k.startswith("session:")])

    async def extend_session_ttl(self, session_id: str, extra_seconds: int = 1800) -> bool:
        """Extend session TTL (no-op for in-memory fallback)."""
        client = await self.get_client()

        if client is None:
            return True  # No-op for in-memory

        key = self._session_key(session_id)
        try:
            await client.expire(key, self.session_ttl + extra_seconds)
            return True
        except Exception as e:
            logger.error(f"Error extending session TTL: {e}")
            return False

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"session:{session_id}"

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


# Singleton instance
_session_memory: Optional[SessionMemory] = None


def get_session_memory() -> SessionMemory:
    """Get or create the session memory singleton."""
    global _session_memory
    if _session_memory is None:
        _session_memory = SessionMemory()
    return _session_memory