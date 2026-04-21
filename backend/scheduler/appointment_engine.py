"""
Appointment Scheduling Engine.
Handles all appointment lifecycle operations:
- Booking with conflict detection
- Rescheduling
- Cancellation
- Availability checking
- Alternative slot suggestions
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
import uuid

from models.database import (
    Appointment, Doctor, DoctorSchedule, Patient,
    AppointmentStatus
)
from models.db_connection import get_db_context

logger = logging.getLogger(__name__)

# Default working hours
DEFAULT_START_HOUR = 9   # 9 AM
DEFAULT_END_HOUR = 18    # 6 PM
DEFAULT_SLOT_DURATION = 30  # minutes

# Multilingual response templates
RESPONSE_TEMPLATES = {
    "en": {
        "booked": "Your appointment with {doctor_name} is confirmed for {date} at {time}. Appointment ID: {appointment_id}",
        "cancelled": "Your appointment on {date} at {time} has been successfully cancelled.",
        "rescheduled": "Your appointment has been rescheduled to {date} at {time} with {doctor_name}.",
        "no_slots": "Sorry, no slots are available with {doctor_name} on {date}. Available dates: {alternatives}",
        "conflict": "That slot is already booked. Available slots on {date}: {slots}",
        "not_found": "No appointment found with the given details.",
        "past_time": "Cannot book appointments in the past. Please choose a future date.",
        "doctor_unavailable": "Dr. {doctor_name} is not available on {date}. Next available: {next_date}",
    },
    "hi": {
        "booked": "आपकी {doctor_name} के साथ {date} को {time} बजे अपॉइंटमेंट की पुष्टि हो गई है। अपॉइंटमेंट ID: {appointment_id}",
        "cancelled": "{date} को {time} बजे की आपकी अपॉइंटमेंट सफलतापूर्वक रद्द कर दी गई है।",
        "rescheduled": "आपकी अपॉइंटमेंट {doctor_name} के साथ {date} को {time} बजे के लिए बदल दी गई है।",
        "no_slots": "क्षमा करें, {date} को {doctor_name} के साथ कोई स्लॉट उपलब्ध नहीं है। उपलब्ध तिथियां: {alternatives}",
        "conflict": "वह स्लॉट पहले से बुक है। {date} को उपलब्ध स्लॉट: {slots}",
        "not_found": "दिए गए विवरण के साथ कोई अपॉइंटमेंट नहीं मिली।",
        "past_time": "पिछले समय में अपॉइंटमेंट बुक नहीं की जा सकती। कृपया भविष्य की तारीख चुनें।",
        "doctor_unavailable": "डॉ. {doctor_name} {date} को उपलब्ध नहीं हैं। अगली उपलब्धता: {next_date}",
    },
    "ta": {
        "booked": "உங்கள் {doctor_name} உடனான சந்திப்பு {date} அன்று {time} மணிக்கு உறுதிப்படுத்தப்பட்டது. சந்திப்பு ID: {appointment_id}",
        "cancelled": "{date} அன்று {time} மணிக்கான உங்கள் சந்திப்பு வெற்றிகரமாக ரத்து செய்யப்பட்டது.",
        "rescheduled": "உங்கள் சந்திப்பு {doctor_name} உடன் {date} அன்று {time} மணிக்கு மாற்றப்பட்டது.",
        "no_slots": "மன்னிக்கவும், {date} அன்று {doctor_name} உடன் இடங்கள் இல்லை. கிடைக்கும் தேதிகள்: {alternatives}",
        "conflict": "அந்த இடம் ஏற்கனவே பதிவு செய்யப்பட்டுள்ளது. {date} அன்று கிடைக்கும் இடங்கள்: {slots}",
        "not_found": "கொடுக்கப்பட்ட விவரங்களுடன் சந்திப்பு எதுவும் கிடைக்கவில்லை.",
        "past_time": "கடந்த காலத்தில் சந்திப்புகளை பதிவு செய்ய முடியாது. எதிர்கால தேதியை தேர்ந்தெடுக்கவும்.",
        "doctor_unavailable": "டாக்டர் {doctor_name} {date} அன்று கிடைக்கவில்லை. அடுத்த கிடைக்கும் தேதி: {next_date}",
    },
    "te": {
        "booked": "మీ {doctor_name} తో అపాయింట్‌మెంట్ {date} న {time} కి నిర్ధారించబడింది. అపాయింట్‌మెంట్ ID: {appointment_id}",
        "cancelled": "{date} న {time} కి మీ అపాయింట్‌మెంట్ విజయవంతంగా రద్దు చేయబడింది.",
        "rescheduled": "మీ అపాయింట్‌మెంట్ {doctor_name} తో {date} న {time} కి మార్చబడింది.",
        "no_slots": "క్షమించండి, {date} న {doctor_name} తో స్లాట్‌లు అందుబాటులో లేవు. అందుబాటులో ఉన్న తేదీలు: {alternatives}",
        "conflict": "ఆ స్లాట్ ఇప్పటికే బుక్ చేయబడింది. {date} న అందుబాటులో ఉన్న స్లాట్‌లు: {slots}",
        "not_found": "ఇచ్చిన వివరాలతో అపాయింట్‌మెంట్ కనుగొనబడలేదు.",
        "past_time": "గతంలో అపాయింట్‌మెంట్‌లు బుక్ చేయలేరు. భవిష్యత్ తేదీని ఎంచుకోండి.",
        "doctor_unavailable": "డాక్టర్ {doctor_name} {date} న అందుబాటులో లేరు. తదుపరి అందుబాటు: {next_date}",
    },
}


class AppointmentEngine:
    """
    Core appointment scheduling engine.
    Handles all CRUD operations with validation and conflict detection.
    """

    async def check_availability(
        self,
        doctor_id: str,
        target_date: date,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Check doctor availability for a specific date."""
        try:
            async with get_db_context() as db:
                doctor_result = await db.execute(
                    select(Doctor).where(Doctor.id == doctor_id)
                )
                doctor = doctor_result.scalar_one_or_none()

                if not doctor:
                    return {"success": False, "error": "Doctor not found", "slots": []}

                if not doctor.is_available:
                    return {
                        "success": False,
                        "error": f"Dr. {doctor.name} is currently not available",
                        "slots": []
                    }

                if target_date < date.today():
                    return {
                        "success": False,
                        "error": "Cannot check availability for past dates",
                        "slots": []
                    }

                schedule = await self._get_or_create_schedule(db, doctor_id, target_date, doctor.consultation_duration)
                available_slots = [
                    slot for slot in schedule.available_slots
                    if slot not in schedule.booked_slots
                ]

                return {
                    "success": True,
                    "doctor_id": doctor_id,
                    "doctor_name": doctor.name,
                    "specialization": doctor.specialization,
                    "hospital": doctor.hospital,
                    "date": target_date.isoformat(),
                    "available_slots": available_slots,
                    "booked_slots": schedule.booked_slots,
                    "total_slots": len(schedule.available_slots),
                    "available_count": len(available_slots),
                }
        except Exception as e:
            logger.warning(f"DB unavailable for check_availability: {e}")
            return {
                "success": False,
                "error": "Database is currently unavailable. Please try again later.",
                "slots": [],
                "available_slots": [],
            }

    async def book_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        appointment_date: date,
        appointment_time: str,
        reason: Optional[str] = None,
        language: str = "en",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Book a new appointment with full validation."""
        try:
          async with get_db_context() as db:
            # Validate patient exists
            patient_result = await db.execute(
                select(Patient).where(Patient.id == patient_id)
            )
            patient = patient_result.scalar_one_or_none()
            if not patient:
                return {"success": False, "error": "Patient not found"}

            # Validate doctor exists
            doctor_result = await db.execute(
                select(Doctor).where(Doctor.id == doctor_id)
            )
            doctor = doctor_result.scalar_one_or_none()
            if not doctor:
                return {"success": False, "error": "Doctor not found"}

            # Validate date/time is not in the past
            appointment_datetime = datetime.combine(
                appointment_date,
                datetime.strptime(appointment_time, "%H:%M").time()
            )
            if appointment_datetime < datetime.now():
                template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
                return {
                    "success": False,
                    "error": template["past_time"]
                }

            # Check for slot availability
            schedule = await self._get_or_create_schedule(
                db, doctor_id, appointment_date, doctor.consultation_duration
            )

            if appointment_time not in schedule.available_slots:
                return {
                    "success": False,
                    "error": f"Time slot {appointment_time} is not available",
                    "available_slots": [
                        s for s in schedule.available_slots
                        if s not in schedule.booked_slots
                    ]
                }

            # Check for double booking
            if appointment_time in schedule.booked_slots:
                available = [s for s in schedule.available_slots if s not in schedule.booked_slots]
                template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
                return {
                    "success": False,
                    "error": template["conflict"].format(
                        date=appointment_date.strftime("%B %d, %Y"),
                        slots=", ".join(available[:5])
                    ),
                    "available_slots": available
                }

            # Check patient doesn't already have appointment at same time
            existing_result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.patient_id == patient_id,
                        Appointment.appointment_date == appointment_date,
                        Appointment.appointment_time == appointment_time,
                        Appointment.status.in_([
                            AppointmentStatus.SCHEDULED,
                            AppointmentStatus.CONFIRMED
                        ])
                    )
                )
            )
            if existing_result.scalar_one_or_none():
                return {
                    "success": False,
                    "error": "You already have an appointment at this time"
                }

            # Create appointment
            appointment = Appointment(
                id=str(uuid.uuid4()),
                patient_id=patient_id,
                doctor_id=doctor_id,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                duration_minutes=doctor.consultation_duration,
                status=AppointmentStatus.CONFIRMED,
                reason=reason,
                language_used=language,
                session_id=session_id,
            )
            db.add(appointment)

            # Update schedule - mark slot as booked
            booked_slots = list(schedule.booked_slots)
            booked_slots.append(appointment_time)
            await db.execute(
                update(DoctorSchedule)
                .where(DoctorSchedule.id == schedule.id)
                .values(booked_slots=booked_slots)
            )

            await db.flush()

            template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
            confirmation_message = template["booked"].format(
                doctor_name=doctor.name,
                date=appointment_date.strftime("%B %d, %Y"),
                time=appointment_time,
                appointment_id=appointment.id[:8].upper()
            )

            logger.info(
                f"Appointment booked: {appointment.id} - "
                f"Patient {patient_id} with Dr. {doctor.name} on {appointment_date} at {appointment_time}"
            )

            return {
                "success": True,
                "appointment_id": appointment.id,
                "patient_name": patient.name,
                "doctor_name": doctor.name,
                "specialization": doctor.specialization,
                "hospital": doctor.hospital,
                "date": appointment_date.isoformat(),
                "time": appointment_time,
                "status": AppointmentStatus.CONFIRMED,
                "message": confirmation_message,
            }
        except Exception as e:
            logger.warning(f"DB unavailable for book_appointment: {e}")
            return {"success": False, "error": "Database is currently unavailable. Cannot book appointment."}

    async def cancel_appointment(
        self,
        appointment_id: str,
        patient_id: str,
        reason: Optional[str] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Cancel an existing appointment."""
        try:
          async with get_db_context() as db:
            # Find appointment
            result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.id == appointment_id,
                        Appointment.patient_id == patient_id,
                    )
                )
            )
            appointment = result.scalar_one_or_none()

            if not appointment:
                template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
                return {"success": False, "error": template["not_found"]}

            if appointment.status == AppointmentStatus.CANCELLED:
                return {"success": False, "error": "Appointment is already cancelled"}

            if appointment.status == AppointmentStatus.COMPLETED:
                return {"success": False, "error": "Cannot cancel a completed appointment"}

            # Update appointment status
            await db.execute(
                update(Appointment)
                .where(Appointment.id == appointment_id)
                .values(
                    status=AppointmentStatus.CANCELLED,
                    cancelled_at=datetime.utcnow(),
                    cancellation_reason=reason,
                    updated_at=datetime.utcnow()
                )
            )

            # Free up the slot in schedule
            schedule_result = await db.execute(
                select(DoctorSchedule).where(
                    and_(
                        DoctorSchedule.doctor_id == appointment.doctor_id,
                        DoctorSchedule.date == appointment.appointment_date
                    )
                )
            )
            schedule = schedule_result.scalar_one_or_none()

            if schedule:
                booked_slots = list(schedule.booked_slots)
                if appointment.appointment_time in booked_slots:
                    booked_slots.remove(appointment.appointment_time)
                    await db.execute(
                        update(DoctorSchedule)
                        .where(DoctorSchedule.id == schedule.id)
                        .values(booked_slots=booked_slots)
                    )

            template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
            message = template["cancelled"].format(
                date=appointment.appointment_date.strftime("%B %d, %Y"),
                time=appointment.appointment_time
            )

            logger.info(f"Appointment cancelled: {appointment_id}")

            return {
                "success": True,
                "appointment_id": appointment_id,
                "message": message,
                "cancelled_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.warning(f"DB unavailable for cancel_appointment: {e}")
            return {"success": False, "error": "Database is currently unavailable. Cannot cancel appointment."}

    async def reschedule_appointment(
        self,
        appointment_id: str,
        patient_id: str,
        new_date: date,
        new_time: str,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Reschedule an existing appointment to a new date/time."""
        try:
          async with get_db_context() as db:
            # Find existing appointment
            result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.id == appointment_id,
                        Appointment.patient_id == patient_id,
                        Appointment.status.in_([
                            AppointmentStatus.SCHEDULED,
                            AppointmentStatus.CONFIRMED
                        ])
                    )
                )
            )
            appointment = result.scalar_one_or_none()

            if not appointment:
                template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
                return {"success": False, "error": template["not_found"]}

            # Validate new date/time
            new_datetime = datetime.combine(
                new_date,
                datetime.strptime(new_time, "%H:%M").time()
            )
            if new_datetime < datetime.now():
                template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
                return {"success": False, "error": template["past_time"]}

            # Get doctor info
            doctor_result = await db.execute(
                select(Doctor).where(Doctor.id == appointment.doctor_id)
            )
            doctor = doctor_result.scalar_one_or_none()

            # Check new slot availability
            new_schedule = await self._get_or_create_schedule(
                db, appointment.doctor_id, new_date, doctor.consultation_duration
            )

            if new_time not in new_schedule.available_slots:
                return {
                    "success": False,
                    "error": f"Time slot {new_time} is not available on {new_date}",
                    "available_slots": [
                        s for s in new_schedule.available_slots
                        if s not in new_schedule.booked_slots
                    ]
                }

            if new_time in new_schedule.booked_slots:
                available = [s for s in new_schedule.available_slots if s not in new_schedule.booked_slots]
                return {
                    "success": False,
                    "error": f"Slot {new_time} is already booked",
                    "available_slots": available
                }

            # Free old slot
            old_schedule_result = await db.execute(
                select(DoctorSchedule).where(
                    and_(
                        DoctorSchedule.doctor_id == appointment.doctor_id,
                        DoctorSchedule.date == appointment.appointment_date
                    )
                )
            )
            old_schedule = old_schedule_result.scalar_one_or_none()

            if old_schedule:
                old_booked = list(old_schedule.booked_slots)
                if appointment.appointment_time in old_booked:
                    old_booked.remove(appointment.appointment_time)
                    await db.execute(
                        update(DoctorSchedule)
                        .where(DoctorSchedule.id == old_schedule.id)
                        .values(booked_slots=old_booked)
                    )

            # Book new slot
            new_booked = list(new_schedule.booked_slots)
            new_booked.append(new_time)
            await db.execute(
                update(DoctorSchedule)
                .where(DoctorSchedule.id == new_schedule.id)
                .values(booked_slots=new_booked)
            )

            # Update appointment
            await db.execute(
                update(Appointment)
                .where(Appointment.id == appointment_id)
                .values(
                    appointment_date=new_date,
                    appointment_time=new_time,
                    status=AppointmentStatus.RESCHEDULED,
                    original_appointment_id=appointment_id,
                    updated_at=datetime.utcnow()
                )
            )

            template = RESPONSE_TEMPLATES.get(language, RESPONSE_TEMPLATES["en"])
            message = template["rescheduled"].format(
                doctor_name=doctor.name,
                date=new_date.strftime("%B %d, %Y"),
                time=new_time
            )

            logger.info(f"Appointment rescheduled: {appointment_id} to {new_date} {new_time}")

            return {
                "success": True,
                "appointment_id": appointment_id,
                "doctor_name": doctor.name,
                "new_date": new_date.isoformat(),
                "new_time": new_time,
                "message": message,
            }
        except Exception as e:
            logger.warning(f"DB unavailable for reschedule_appointment: {e}")
            return {"success": False, "error": "Database is currently unavailable. Cannot reschedule appointment."}

    async def get_patient_appointments(
        self,
        patient_id: str,
        status_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get appointments for a patient."""
        try:
            async with get_db_context() as db:
                conditions = [Appointment.patient_id == patient_id]

                if status_filter:
                    conditions.append(Appointment.status == status_filter)

                result = await db.execute(
                    select(Appointment, Doctor)
                    .join(Doctor, Appointment.doctor_id == Doctor.id)
                    .where(and_(*conditions))
                    .order_by(Appointment.appointment_date.desc())
                    .limit(limit)
                )

                appointments = []
                for appointment, doctor in result.all():
                    appointments.append({
                        "id": appointment.id,
                        "doctor_name": doctor.name,
                        "specialization": doctor.specialization,
                        "hospital": doctor.hospital,
                        "date": appointment.appointment_date.isoformat(),
                        "time": appointment.appointment_time,
                        "status": appointment.status,
                        "reason": appointment.reason,
                    })

                return appointments
        except Exception as e:
            logger.warning(f"DB unavailable for get_patient_appointments: {e}")
            return []

    async def find_doctors_by_specialization(
        self,
        specialization: str,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find doctors by specialization."""
        try:
            async with get_db_context() as db:
                conditions = [
                    Doctor.specialization.ilike(f"%{specialization}%"),
                    Doctor.is_available == True
                ]

                result = await db.execute(
                    select(Doctor).where(and_(*conditions))
                )
                doctors = result.scalars().all()

                return [
                    {
                        "id": d.id,
                        "name": d.name,
                        "specialization": d.specialization,
                        "hospital": d.hospital,
                        "consultation_duration": d.consultation_duration,
                        "languages_spoken": d.languages_spoken,
                    }
                    for d in doctors
                ]
        except Exception as e:
            logger.warning(f"DB unavailable for find_doctors_by_specialization: {e}")
            return []

    async def get_next_available_slots(
        self,
        doctor_id: str,
        from_date: date,
        days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """Find next available slots for a doctor within a date range."""
        try:
            async with get_db_context() as db:
                doctor_result = await db.execute(
                    select(Doctor).where(Doctor.id == doctor_id)
                )
                doctor = doctor_result.scalar_one_or_none()
                if not doctor:
                    return []

                available_dates = []
                check_date = from_date

                for _ in range(days_ahead):
                    if check_date.weekday() < 6:
                        schedule = await self._get_or_create_schedule(
                            db, doctor_id, check_date, doctor.consultation_duration
                        )
                        free_slots = [
                            s for s in schedule.available_slots
                            if s not in schedule.booked_slots
                        ]
                        if free_slots:
                            available_dates.append({
                                "date": check_date.isoformat(),
                                "slots": free_slots[:5],
                            })

                    check_date += timedelta(days=1)

                return available_dates
        except Exception as e:
            logger.warning(f"DB unavailable for get_next_available_slots: {e}")
            return []

    async def _get_or_create_schedule(
        self,
        db: AsyncSession,
        doctor_id: str,
        target_date: date,
        slot_duration: int = DEFAULT_SLOT_DURATION
    ) -> DoctorSchedule:
        """
        Get existing schedule or create a default one for the date.
        """
        result = await db.execute(
            select(DoctorSchedule).where(
                and_(
                    DoctorSchedule.doctor_id == doctor_id,
                    DoctorSchedule.date == target_date
                )
            )
        )
        schedule = result.scalar_one_or_none()

        if not schedule:
            # Generate default slots
            slots = self._generate_time_slots(
                DEFAULT_START_HOUR,
                DEFAULT_END_HOUR,
                slot_duration
            )

            schedule = DoctorSchedule(
                id=str(uuid.uuid4()),
                doctor_id=doctor_id,
                date=target_date,
                available_slots=slots,
                booked_slots=[],
                is_holiday=target_date.weekday() == 6,  # Sunday is holiday
            )
            db.add(schedule)
            await db.flush()

        return schedule

    def _generate_time_slots(
        self,
        start_hour: int,
        end_hour: int,
        duration_minutes: int
    ) -> List[str]:
        """Generate time slots for a day."""
        slots = []
        current = datetime.combine(date.today(), time(start_hour, 0))
        end = datetime.combine(date.today(), time(end_hour, 0))

        while current < end:
            slots.append(current.strftime("%H:%M"))
            current += timedelta(minutes=duration_minutes)

        return slots

    def _format_date(self, d: date, language: str = "en") -> str:
        """Format date for display in given language."""
        return d.strftime("%B %d, %Y")


# Singleton instance
_appointment_engine: Optional[AppointmentEngine] = None


def get_appointment_engine() -> AppointmentEngine:
    """Get or create the appointment engine singleton."""
    global _appointment_engine
    if _appointment_engine is None:
        _appointment_engine = AppointmentEngine()
    return _appointment_engine