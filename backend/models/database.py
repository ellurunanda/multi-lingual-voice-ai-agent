"""
SQLAlchemy database models for the Voice AI Clinical Appointment System.
Defines all tables: patients, doctors, appointments, schedules, campaigns.
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, Float,
    ForeignKey, Enum, JSON, Date, Time, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"


class CampaignStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CampaignType(str, enum.Enum):
    REMINDER = "reminder"
    FOLLOW_UP = "follow_up"
    VACCINATION = "vaccination"
    CHECKUP = "checkup"


class LanguageCode(str, enum.Enum):
    ENGLISH = "en"
    HINDI = "hi"
    TAMIL = "ta"
    TELUGU = "te"


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    email = Column(String(255), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    preferred_language = Column(String(5), default="en")
    preferred_doctor_id = Column(String(36), ForeignKey("doctors.id"), nullable=True)
    preferred_hospital = Column(String(255), nullable=True)
    medical_history = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    appointments = relationship("Appointment", back_populates="patient", foreign_keys="Appointment.patient_id")
    preferred_doctor = relationship("Doctor", foreign_keys=[preferred_doctor_id])
    memory_records = relationship("PatientMemory", back_populates="patient")

    def __repr__(self):
        return f"<Patient {self.name} ({self.phone})>"


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    specialization = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    hospital = Column(String(255), nullable=False)
    consultation_duration = Column(Integer, default=30)  # minutes
    languages_spoken = Column(JSON, default=list)  # ["en", "hi", "ta", "te"]
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointments = relationship("Appointment", back_populates="doctor")
    schedules = relationship("DoctorSchedule", back_populates="doctor")

    def __repr__(self):
        return f"<Doctor {self.name} - {self.specialization}>"


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    doctor_id = Column(String(36), ForeignKey("doctors.id"), nullable=False)
    date = Column(Date, nullable=False)
    available_slots = Column(JSON, default=list)  # ["09:00", "09:30", "10:00", ...]
    booked_slots = Column(JSON, default=list)
    is_holiday = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("doctor_id", "date", name="uq_doctor_date"),
    )

    # Relationships
    doctor = relationship("Doctor", back_populates="schedules")

    def __repr__(self):
        return f"<DoctorSchedule {self.doctor_id} on {self.date}>"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String(36), ForeignKey("doctors.id"), nullable=False)
    appointment_date = Column(Date, nullable=False)
    appointment_time = Column(String(10), nullable=False)  # "HH:MM"
    duration_minutes = Column(Integer, default=30)
    status = Column(String(20), default=AppointmentStatus.SCHEDULED)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    language_used = Column(String(5), default="en")
    session_id = Column(String(36), nullable=True)
    original_appointment_id = Column(String(36), ForeignKey("appointments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="appointments", foreign_keys=[patient_id])
    doctor = relationship("Doctor", back_populates="appointments")
    original_appointment = relationship("Appointment", remote_side=[id])

    def __repr__(self):
        return f"<Appointment {self.id} - {self.patient_id} with {self.doctor_id} on {self.appointment_date}>"


class PatientMemory(Base):
    __tablename__ = "patient_memory"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False)
    memory_type = Column(String(50), nullable=False)  # "preference", "history", "context"
    key = Column(String(255), nullable=False)
    value = Column(JSON, nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    patient = relationship("Patient", back_populates="memory_records")

    def __repr__(self):
        return f"<PatientMemory {self.patient_id} - {self.key}>"


class ConversationLog(Base):
    __tablename__ = "conversation_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=True)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    language = Column(String(5), default="en")
    audio_duration_ms = Column(Integer, nullable=True)
    stt_latency_ms = Column(Integer, nullable=True)
    llm_latency_ms = Column(Integer, nullable=True)
    tts_latency_ms = Column(Integer, nullable=True)
    total_latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ConversationLog {self.session_id} - {self.role}>"


class OutboundCampaign(Base):
    __tablename__ = "outbound_campaigns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    campaign_type = Column(String(50), nullable=False)
    target_patient_ids = Column(JSON, default=list)
    message_template = Column(Text, nullable=False)
    language = Column(String(5), default="en")
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String(20), default=CampaignStatus.PENDING)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<OutboundCampaign {self.name} - {self.status}>"


class LatencyMetric(Base):
    __tablename__ = "latency_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), nullable=False, index=True)
    stage = Column(String(50), nullable=False)  # "stt", "llm", "tts", "total"
    latency_ms = Column(Float, nullable=False)
    target_ms = Column(Float, nullable=True)
    met_target = Column(Boolean, nullable=True)
    language = Column(String(5), default="en")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LatencyMetric {self.stage}: {self.latency_ms}ms>"