"""
Appointment management REST API routes.
Provides CRUD operations for appointments.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

from sqlalchemy import select
from models.database import Appointment, Patient, Doctor
from models.db_connection import get_db_context
from scheduler.appointment_engine import get_appointment_engine
from memory.persistent_memory import get_persistent_memory

router = APIRouter(redirect_slashes=False)


class BookAppointmentRequest(BaseModel):
    patient_id: str = Field(..., description="Patient unique ID")
    doctor_id: str = Field(..., description="Doctor unique ID")
    date: str = Field(..., description="Appointment date (YYYY-MM-DD)")
    time: str = Field(..., description="Appointment time (HH:MM)")
    reason: Optional[str] = Field(None, description="Reason for visit")
    language: str = Field(default="en", description="Language code (en/hi/ta/te)")


class CancelAppointmentRequest(BaseModel):
    patient_id: str = Field(..., description="Patient unique ID")
    reason: Optional[str] = Field(None, description="Cancellation reason")
    language: str = Field(default="en")


class RescheduleAppointmentRequest(BaseModel):
    patient_id: str = Field(..., description="Patient unique ID")
    new_date: str = Field(..., description="New appointment date (YYYY-MM-DD)")
    new_time: str = Field(..., description="New appointment time (HH:MM)")
    language: str = Field(default="en")


@router.get("/")
async def list_appointments(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
):
    """List all appointments with patient and doctor details."""
    try:
        async with get_db_context() as db:
            stmt = (
                select(Appointment, Patient, Doctor)
                .join(Patient, Appointment.patient_id == Patient.id)
                .join(Doctor, Appointment.doctor_id == Doctor.id)
            )
            if status:
                stmt = stmt.where(Appointment.status == status)
            stmt = stmt.order_by(
                Appointment.appointment_date.desc(),
                Appointment.appointment_time.desc()
            ).limit(limit)

            result = await db.execute(stmt)
            rows = result.all()

            appointments = []
            for appt, patient, doctor in rows:
                # Combine date + time into an ISO datetime string for the frontend
                try:
                    dt = datetime.strptime(
                        f"{appt.appointment_date} {appt.appointment_time}", "%Y-%m-%d %H:%M"
                    )
                    appointment_time_iso = dt.isoformat()
                except Exception:
                    appointment_time_iso = str(appt.appointment_date)

                appointments.append({
                    "id": appt.id,
                    "status": appt.status,
                    "appointment_time": appointment_time_iso,
                    "patient_name": patient.name,
                    "doctor_name": doctor.name,
                    "phone": patient.phone,
                    "reason": appt.reason,
                    "specialization": doctor.specialization,
                    "hospital": doctor.hospital,
                    "language_used": appt.language_used,
                    "created_at": appt.created_at.isoformat() if appt.created_at else None,
                })

            return {"appointments": appointments, "count": len(appointments)}

    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"Failed to list appointments: {exc}")
        return {"appointments": [], "count": 0}


@router.post("/book")
async def book_appointment(request: BookAppointmentRequest):
    """Book a new appointment."""
    engine = get_appointment_engine()

    try:
        appointment_date = date.fromisoformat(request.date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await engine.book_appointment(
        patient_id=request.patient_id,
        doctor_id=request.doctor_id,
        appointment_date=appointment_date,
        appointment_time=request.time,
        reason=request.reason,
        language=request.language,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Booking failed"))

    return result


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: str, request: CancelAppointmentRequest):
    """Cancel an existing appointment."""
    engine = get_appointment_engine()

    result = await engine.cancel_appointment(
        appointment_id=appointment_id,
        patient_id=request.patient_id,
        reason=request.reason,
        language=request.language,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Cancellation failed"))

    return result


@router.post("/{appointment_id}/reschedule")
async def reschedule_appointment(appointment_id: str, request: RescheduleAppointmentRequest):
    """Reschedule an existing appointment."""
    engine = get_appointment_engine()

    try:
        new_date = date.fromisoformat(request.new_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await engine.reschedule_appointment(
        appointment_id=appointment_id,
        patient_id=request.patient_id,
        new_date=new_date,
        new_time=request.new_time,
        language=request.language,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Rescheduling failed"))

    return result


@router.get("/patient/{patient_id}")
async def get_patient_appointments(
    patient_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(10, ge=1, le=50)
):
    """Get appointments for a patient."""
    engine = get_appointment_engine()
    appointments = await engine.get_patient_appointments(
        patient_id=patient_id,
        status_filter=status,
        limit=limit
    )
    return {"appointments": appointments, "count": len(appointments)}


@router.get("/availability/{doctor_id}")
async def check_availability(
    doctor_id: str,
    date: str = Query(..., description="Date to check (YYYY-MM-DD)"),
    language: str = Query("en", description="Language code")
):
    """Check doctor availability for a date."""
    engine = get_appointment_engine()

    try:
        target_date = date_obj = __import__("datetime").date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    result = await engine.check_availability(
        doctor_id=doctor_id,
        target_date=target_date,
        language=language
    )

    return result


@router.get("/next-slots/{doctor_id}")
async def get_next_available_slots(
    doctor_id: str,
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    days_ahead: int = Query(7, ge=1, le=30)
):
    """Get next available slots for a doctor."""
    engine = get_appointment_engine()

    if from_date:
        try:
            start_date = __import__("datetime").date.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        start_date = __import__("datetime").date.today()

    slots = await engine.get_next_available_slots(
        doctor_id=doctor_id,
        from_date=start_date,
        days_ahead=days_ahead
    )

    return {"available_dates": slots, "count": len(slots)}