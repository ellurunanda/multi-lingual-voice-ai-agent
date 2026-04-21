"""
Persistent Memory using PostgreSQL.
Stores long-term patient preferences, history, and learned context.
Enables personalized interactions across sessions.
Gracefully degrades when PostgreSQL is unavailable.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_

from models.database import Patient, PatientMemory, ConversationLog, Appointment, LatencyMetric
from models.db_connection import get_db_context

logger = logging.getLogger(__name__)


class PersistentMemory:
    """
    PostgreSQL-backed persistent memory for long-term patient context.
    Stores preferences, history, and learned patterns.
    All methods degrade gracefully when the database is unavailable.
    """

    async def get_patient_by_phone(self, phone: str) -> Optional[dict]:
        """Retrieve patient by phone number."""
        try:
            async with get_db_context() as db:
                result = await db.execute(
                    select(Patient).where(Patient.phone == phone)
                )
                patient = result.scalar_one_or_none()
                if patient:
                    return self._patient_to_dict(patient)
                return None
        except Exception as e:
            logger.warning(f"DB unavailable, get_patient_by_phone skipped: {e}")
            return None

    async def get_patient_by_id(self, patient_id: str) -> Optional[dict]:
        """Retrieve patient by ID."""
        try:
            async with get_db_context() as db:
                result = await db.execute(
                    select(Patient).where(Patient.id == patient_id)
                )
                patient = result.scalar_one_or_none()
                if patient:
                    return self._patient_to_dict(patient)
                return None
        except Exception as e:
            logger.warning(f"DB unavailable, get_patient_by_id skipped: {e}")
            return None

    async def create_patient(self, patient_data: dict) -> Optional[dict]:
        """Create a new patient record."""
        try:
            async with get_db_context() as db:
                patient = Patient(**patient_data)
                db.add(patient)
                await db.flush()
                await db.refresh(patient)
                logger.info(f"Created patient: {patient.id} - {patient.name}")
                return self._patient_to_dict(patient)
        except Exception as e:
            logger.warning(f"DB unavailable, create_patient skipped: {e}")
            return None

    async def update_patient_language(self, patient_id: str, language: str) -> bool:
        """Update patient's preferred language."""
        try:
            async with get_db_context() as db:
                await db.execute(
                    update(Patient)
                    .where(Patient.id == patient_id)
                    .values(preferred_language=language, updated_at=datetime.utcnow())
                )
                logger.info(f"Updated language for patient {patient_id}: {language}")
                return True
        except Exception as e:
            logger.warning(f"DB unavailable, update_patient_language skipped: {e}")
            return False

    async def store_memory(
        self,
        patient_id: str,
        memory_type: str,
        key: str,
        value: Any,
        confidence: float = 1.0,
        expires_in_days: Optional[int] = None
    ) -> bool:
        """Store a memory record for a patient."""
        try:
            async with get_db_context() as db:
                expires_at = None
                if expires_in_days:
                    expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

                result = await db.execute(
                    select(PatientMemory).where(
                        and_(
                            PatientMemory.patient_id == patient_id,
                            PatientMemory.memory_type == memory_type,
                            PatientMemory.key == key
                        )
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    await db.execute(
                        update(PatientMemory)
                        .where(PatientMemory.id == existing.id)
                        .values(
                            value=value if isinstance(value, dict) else {"data": value},
                            confidence=confidence,
                            expires_at=expires_at,
                            updated_at=datetime.utcnow()
                        )
                    )
                else:
                    memory = PatientMemory(
                        patient_id=patient_id,
                        memory_type=memory_type,
                        key=key,
                        value=value if isinstance(value, dict) else {"data": value},
                        confidence=confidence,
                        expires_at=expires_at,
                    )
                    db.add(memory)

                logger.debug(f"Stored memory for patient {patient_id}: {memory_type}/{key}")
                return True
        except Exception as e:
            logger.warning(f"DB unavailable, store_memory skipped: {e}")
            return False

    async def get_memory(
        self,
        patient_id: str,
        memory_type: Optional[str] = None,
        key: Optional[str] = None
    ) -> List[dict]:
        """Retrieve memory records for a patient."""
        try:
            async with get_db_context() as db:
                conditions = [
                    PatientMemory.patient_id == patient_id,
                    (PatientMemory.expires_at.is_(None)) |
                    (PatientMemory.expires_at > datetime.utcnow())
                ]

                if memory_type:
                    conditions.append(PatientMemory.memory_type == memory_type)
                if key:
                    conditions.append(PatientMemory.key == key)

                result = await db.execute(
                    select(PatientMemory)
                    .where(and_(*conditions))
                    .order_by(PatientMemory.updated_at.desc())
                )
                memories = result.scalars().all()
                return [self._memory_to_dict(m) for m in memories]
        except Exception as e:
            logger.warning(f"DB unavailable, get_memory skipped: {e}")
            return []

    async def get_patient_context(self, patient_id: str) -> dict:
        """Get comprehensive patient context for AI agent."""
        patient = await self.get_patient_by_id(patient_id)
        if not patient:
            return {}

        memories = await self.get_memory(patient_id)
        recent_appointments = await self.get_recent_appointments(patient_id, limit=5)

        preferences = {}
        history = {}
        context = {}

        for mem in memories:
            mem_type = mem["memory_type"]
            k = mem["key"]
            v = mem["value"]
            if mem_type == "preference":
                preferences[k] = v
            elif mem_type == "history":
                history[k] = v
            elif mem_type == "context":
                context[k] = v

        return {
            "patient": patient,
            "preferences": preferences,
            "history": history,
            "context": context,
            "recent_appointments": recent_appointments,
        }

    async def get_recent_appointments(
        self,
        patient_id: str,
        limit: int = 5
    ) -> List[dict]:
        """Get recent appointments for a patient."""
        try:
            async with get_db_context() as db:
                result = await db.execute(
                    select(Appointment)
                    .where(Appointment.patient_id == patient_id)
                    .order_by(Appointment.created_at.desc())
                    .limit(limit)
                )
                appointments = result.scalars().all()
                return [self._appointment_to_dict(a) for a in appointments]
        except Exception as e:
            logger.warning(f"DB unavailable, get_recent_appointments skipped: {e}")
            return []

    async def log_conversation(
        self,
        session_id: str,
        patient_id: Optional[str],
        role: str,
        content: str,
        language: str = "en",
        latency_data: Optional[dict] = None
    ) -> bool:
        """Log a conversation turn to the database."""
        try:
            async with get_db_context() as db:
                log = ConversationLog(
                    session_id=session_id,
                    patient_id=patient_id,
                    role=role,
                    content=content,
                    language=language,
                    stt_latency_ms=latency_data.get("stt_ms") if latency_data else None,
                    llm_latency_ms=latency_data.get("llm_ms") if latency_data else None,
                    tts_latency_ms=latency_data.get("tts_ms") if latency_data else None,
                    total_latency_ms=latency_data.get("total_ms") if latency_data else None,
                )
                db.add(log)
                return True
        except Exception as e:
            logger.warning(f"DB unavailable, log_conversation skipped: {e}")
            return False

    async def log_latency_metric(
        self,
        session_id: str,
        stage: str,
        latency_ms: float,
        target_ms: float,
        language: str = "en"
    ) -> bool:
        """Log a latency metric to the database."""
        try:
            async with get_db_context() as db:
                metric = LatencyMetric(
                    session_id=session_id,
                    stage=stage,
                    latency_ms=latency_ms,
                    target_ms=target_ms,
                    met_target=latency_ms <= target_ms,
                    language=language,
                )
                db.add(metric)
                return True
        except Exception as e:
            logger.warning(f"DB unavailable, log_latency_metric skipped: {e}")
            return False

    async def learn_from_interaction(
        self,
        patient_id: str,
        interaction_data: dict
    ) -> bool:
        """Learn and store patterns from patient interactions."""
        try:
            if "language" in interaction_data:
                await self.store_memory(
                    patient_id, "preference", "preferred_language",
                    {"language": interaction_data["language"]},
                    confidence=0.9
                )
            if "doctor_id" in interaction_data:
                await self.store_memory(
                    patient_id, "preference", "last_doctor",
                    {"doctor_id": interaction_data["doctor_id"]},
                    confidence=0.8
                )
            if "hospital" in interaction_data:
                await self.store_memory(
                    patient_id, "preference", "preferred_hospital",
                    {"hospital": interaction_data["hospital"]},
                    confidence=0.8
                )
            if "appointment_time" in interaction_data:
                await self.store_memory(
                    patient_id, "preference", "preferred_time",
                    {"time": interaction_data["appointment_time"]},
                    confidence=0.7,
                    expires_in_days=30
                )
            logger.info(f"Learned from interaction for patient {patient_id}")
            return True
        except Exception as e:
            logger.error(f"Error learning from interaction: {e}")
            return False

    def _patient_to_dict(self, patient: Patient) -> dict:
        """Convert Patient model to dict."""
        return {
            "id": patient.id,
            "name": patient.name,
            "phone": patient.phone,
            "email": patient.email,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "preferred_language": patient.preferred_language,
            "preferred_doctor_id": patient.preferred_doctor_id,
            "preferred_hospital": patient.preferred_hospital,
            "medical_history": patient.medical_history,
            "created_at": patient.created_at.isoformat() if patient.created_at else None,
        }

    def _memory_to_dict(self, memory: PatientMemory) -> dict:
        """Convert PatientMemory model to dict."""
        return {
            "id": memory.id,
            "patient_id": memory.patient_id,
            "memory_type": memory.memory_type,
            "key": memory.key,
            "value": memory.value,
            "confidence": memory.confidence,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
            "expires_at": memory.expires_at.isoformat() if memory.expires_at else None,
        }

    def _appointment_to_dict(self, appointment: Appointment) -> dict:
        """Convert Appointment model to dict."""
        return {
            "id": appointment.id,
            "patient_id": appointment.patient_id,
            "doctor_id": appointment.doctor_id,
            "appointment_date": appointment.appointment_date.isoformat() if appointment.appointment_date else None,
            "appointment_time": appointment.appointment_time,
            "status": appointment.status,
            "reason": appointment.reason,
            "language_used": appointment.language_used,
            "created_at": appointment.created_at.isoformat() if appointment.created_at else None,
        }


# Singleton instance
_persistent_memory: Optional[PersistentMemory] = None


def get_persistent_memory() -> PersistentMemory:
    """Get or create the persistent memory singleton."""
    global _persistent_memory
    if _persistent_memory is None:
        _persistent_memory = PersistentMemory()
    return _persistent_memory