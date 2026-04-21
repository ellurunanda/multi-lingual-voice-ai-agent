"""Doctor management REST API routes."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

from scheduler.appointment_engine import get_appointment_engine
from models.db_connection import get_db_context
from models.database import Doctor
from sqlalchemy import select, and_
import uuid

router = APIRouter()


class CreateDoctorRequest(BaseModel):
    name: str = Field(..., description="Doctor full name")
    specialization: str = Field(..., description="Medical specialization")
    phone: Optional[str] = Field(None)
    email: Optional[str] = Field(None)
    hospital: str = Field(..., description="Hospital name")
    consultation_duration: int = Field(default=30, description="Consultation duration in minutes")
    languages_spoken: List[str] = Field(default=["en"], description="Languages spoken")


@router.get("/")
async def list_doctors(
    specialization: Optional[str] = Query(None, description="Filter by specialization"),
    hospital: Optional[str] = Query(None, description="Filter by hospital"),
    language: Optional[str] = Query(None, description="Filter by language spoken"),
    limit: int = Query(20, ge=1, le=100)
):
    """List all available doctors with optional filters."""
    async with get_db_context() as db:
        conditions = [Doctor.is_available == True]

        if specialization:
            conditions.append(Doctor.specialization.ilike(f"%{specialization}%"))
        if hospital:
            conditions.append(Doctor.hospital.ilike(f"%{hospital}%"))

        result = await db.execute(
            select(Doctor).where(and_(*conditions)).limit(limit)
        )
        doctors = result.scalars().all()

        # Filter by language if specified
        if language:
            doctors = [d for d in doctors if language in (d.languages_spoken or [])]

        return {
            "doctors": [
                {
                    "id": d.id,
                    "name": d.name,
                    "specialization": d.specialization,
                    "hospital": d.hospital,
                    "consultation_duration": d.consultation_duration,
                    "languages_spoken": d.languages_spoken,
                }
                for d in doctors
            ],
            "count": len(doctors),
        }


@router.get("/{doctor_id}")
async def get_doctor(doctor_id: str):
    """Get doctor by ID."""
    async with get_db_context() as db:
        result = await db.execute(
            select(Doctor).where(Doctor.id == doctor_id)
        )
        doctor = result.scalar_one_or_none()

        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")

        return {
            "id": doctor.id,
            "name": doctor.name,
            "specialization": doctor.specialization,
            "phone": doctor.phone,
            "email": doctor.email,
            "hospital": doctor.hospital,
            "consultation_duration": doctor.consultation_duration,
            "languages_spoken": doctor.languages_spoken,
            "is_available": doctor.is_available,
        }


@router.get("/{doctor_id}/availability")
async def get_doctor_availability(
    doctor_id: str,
    date: str = Query(..., description="Date to check (YYYY-MM-DD)"),
    language: str = Query("en")
):
    """Get doctor availability for a specific date."""
    engine = get_appointment_engine()

    try:
        target_date = __import__("datetime").date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await engine.check_availability(
        doctor_id=doctor_id,
        target_date=target_date,
        language=language
    )

    return result


@router.post("/")
async def create_doctor(request: CreateDoctorRequest):
    """Create a new doctor record."""
    async with get_db_context() as db:
        doctor = Doctor(
            id=str(uuid.uuid4()),
            name=request.name,
            specialization=request.specialization,
            phone=request.phone,
            email=request.email,
            hospital=request.hospital,
            consultation_duration=request.consultation_duration,
            languages_spoken=request.languages_spoken,
            is_available=True,
        )
        db.add(doctor)
        await db.flush()

        return {
            "id": doctor.id,
            "name": doctor.name,
            "specialization": doctor.specialization,
            "hospital": doctor.hospital,
            "message": "Doctor created successfully",
        }


@router.get("/search/{specialization}")
async def search_doctors_by_specialization(
    specialization: str,
    language: Optional[str] = Query(None)
):
    """Search doctors by specialization."""
    engine = get_appointment_engine()
    doctors = await engine.find_doctors_by_specialization(
        specialization=specialization,
        language=language
    )
    return {"doctors": doctors, "count": len(doctors)}