"""Patient management REST API routes."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

from memory.persistent_memory import get_persistent_memory
from models.db_connection import get_db_context
from models.database import Patient
from sqlalchemy import select
import uuid

router = APIRouter()


class CreatePatientRequest(BaseModel):
    name: str = Field(..., description="Patient full name")
    phone: str = Field(..., description="Phone number (unique)")
    email: Optional[str] = Field(None, description="Email address")
    date_of_birth: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    preferred_language: str = Field(default="en", description="Preferred language (en/hi/ta/te)")
    preferred_hospital: Optional[str] = Field(None, description="Preferred hospital")


class UpdatePatientRequest(BaseModel):
    preferred_language: Optional[str] = None
    preferred_hospital: Optional[str] = None
    email: Optional[str] = None


@router.post("/")
async def create_patient(request: CreatePatientRequest):
    """Create a new patient record."""
    memory = get_persistent_memory()

    # Check if phone already exists
    existing = await memory.get_patient_by_phone(request.phone)
    if existing:
        raise HTTPException(status_code=409, detail="Patient with this phone already exists")

    patient_data = {
        "id": str(uuid.uuid4()),
        "name": request.name,
        "phone": request.phone,
        "email": request.email,
        "preferred_language": request.preferred_language,
        "preferred_hospital": request.preferred_hospital,
        "medical_history": {},
    }

    if request.date_of_birth:
        try:
            patient_data["date_of_birth"] = date.fromisoformat(request.date_of_birth)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format for date_of_birth")

    patient = await memory.create_patient(patient_data)
    return patient


@router.get("/{patient_id}")
async def get_patient(patient_id: str):
    """Get patient by ID."""
    memory = get_persistent_memory()
    patient = await memory.get_patient_by_id(patient_id)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    return patient


@router.get("/phone/{phone}")
async def get_patient_by_phone(phone: str):
    """Get patient by phone number."""
    memory = get_persistent_memory()
    patient = await memory.get_patient_by_phone(phone)

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    return patient


@router.get("/{patient_id}/context")
async def get_patient_context(patient_id: str):
    """Get full patient context including preferences and history."""
    memory = get_persistent_memory()
    context = await memory.get_patient_context(patient_id)

    if not context:
        raise HTTPException(status_code=404, detail="Patient not found")

    return context


@router.patch("/{patient_id}")
async def update_patient(patient_id: str, request: UpdatePatientRequest):
    """Update patient preferences."""
    memory = get_persistent_memory()

    patient = await memory.get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if request.preferred_language:
        await memory.update_patient_language(patient_id, request.preferred_language)

    return {"success": True, "message": "Patient updated successfully"}


@router.get("/")
async def list_patients(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all patients (paginated)."""
    async with get_db_context() as db:
        result = await db.execute(
            select(Patient)
            .where(Patient.is_active == True)
            .offset(offset)
            .limit(limit)
        )
        patients = result.scalars().all()

        return {
            "patients": [
                {
                    "id": p.id,
                    "name": p.name,
                    "phone": p.phone,
                    "preferred_language": p.preferred_language,
                    "preferred_hospital": p.preferred_hospital,
                }
                for p in patients
            ],
            "count": len(patients),
            "offset": offset,
            "limit": limit,
        }