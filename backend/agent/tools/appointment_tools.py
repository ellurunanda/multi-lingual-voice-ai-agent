"""
Tool definitions for the AI Agent's tool orchestration layer.
These tools are called by the LLM to perform appointment operations.
Follows OpenAI function calling format.
"""
import logging
import json
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta

from scheduler.appointment_engine import get_appointment_engine
from memory.persistent_memory import get_persistent_memory

logger = logging.getLogger(__name__)

# Tool definitions in OpenAI function calling format
APPOINTMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_doctor_availability",
            "description": "Check available appointment slots for a doctor on a specific date. Use this before booking to show available times.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The unique ID of the doctor"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date to check in YYYY-MM-DD format"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for response (en/hi/ta/te)",
                        "enum": ["en", "hi", "ta", "te"]
                    }
                },
                "required": ["doctor_id", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new appointment for a patient with a doctor. Always confirm details with patient before calling this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The unique ID of the patient"
                    },
                    "doctor_id": {
                        "type": "string",
                        "description": "The unique ID of the doctor"
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format"
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment time in HH:MM format (24-hour)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the appointment (optional)"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for response (en/hi/ta/te)",
                        "enum": ["en", "hi", "ta", "te"]
                    }
                },
                "required": ["patient_id", "doctor_id", "date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. Always confirm with patient before cancelling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "The unique ID of the appointment to cancel"
                    },
                    "patient_id": {
                        "type": "string",
                        "description": "The patient's ID for authorization"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for cancellation (optional)"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for response (en/hi/ta/te)",
                        "enum": ["en", "hi", "ta", "te"]
                    }
                },
                "required": ["appointment_id", "patient_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "The unique ID of the appointment to reschedule"
                    },
                    "patient_id": {
                        "type": "string",
                        "description": "The patient's ID for authorization"
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New appointment date in YYYY-MM-DD format"
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New appointment time in HH:MM format (24-hour)"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for response (en/hi/ta/te)",
                        "enum": ["en", "hi", "ta", "te"]
                    }
                },
                "required": ["appointment_id", "patient_id", "new_date", "new_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_doctors",
            "description": "Find doctors by specialization or name. Use this when patient mentions a type of doctor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialization": {
                        "type": "string",
                        "description": "Medical specialization to search for (e.g., cardiologist, dermatologist)"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for response (en/hi/ta/te)",
                        "enum": ["en", "hi", "ta", "te"]
                    }
                },
                "required": ["specialization"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_patient_appointments",
            "description": "Get list of appointments for a patient. Use when patient asks about their appointments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {
                        "type": "string",
                        "description": "The patient's unique ID"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (optional)",
                        "enum": ["scheduled", "confirmed", "cancelled", "completed", "rescheduled"]
                    }
                },
                "required": ["patient_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_next_available_slots",
            "description": "Get next available appointment slots for a doctor. Use when requested slot is unavailable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The doctor's unique ID"
                    },
                    "from_date": {
                        "type": "string",
                        "description": "Start date to search from in YYYY-MM-DD format"
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days to search ahead (default 7)",
                        "default": 7
                    }
                },
                "required": ["doctor_id", "from_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "register_patient",
            "description": "Register a new patient in the system. Use this when a patient says they are new or not registered. Collect their name and phone number first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Patient's full name"
                    },
                    "phone": {
                        "type": "string",
                        "description": "Patient's phone number (used as unique identifier)"
                    },
                    "preferred_language": {
                        "type": "string",
                        "description": "Patient's preferred language code",
                        "enum": ["en", "hi", "ta", "te"],
                        "default": "en"
                    },
                    "preferred_hospital": {
                        "type": "string",
                        "description": "Patient's preferred hospital (optional)"
                    }
                },
                "required": ["name", "phone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_patient_by_phone",
            "description": "Look up an existing patient by their phone number. Use this to find a patient's ID when they provide their phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Patient's phone number to search for"
                    }
                },
                "required": ["phone"]
            }
        }
    }
]


class ToolOrchestrator:
    """
    Orchestrates tool calls from the AI agent.
    Executes appointment operations and returns structured results.
    """

    def __init__(self):
        self.engine = get_appointment_engine()
        self.memory = get_persistent_memory()
        logger.info("Tool Orchestrator initialized")

    async def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool call from the AI agent.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            session_id: Optional session ID for tracking

        Returns:
            Tool execution result
        """
        logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

        try:
            if tool_name == "check_doctor_availability":
                return await self._check_availability(tool_args)

            elif tool_name == "book_appointment":
                return await self._book_appointment(tool_args, session_id)

            elif tool_name == "cancel_appointment":
                return await self._cancel_appointment(tool_args)

            elif tool_name == "reschedule_appointment":
                return await self._reschedule_appointment(tool_args)

            elif tool_name == "find_doctors":
                return await self._find_doctors(tool_args)

            elif tool_name == "get_patient_appointments":
                return await self._get_patient_appointments(tool_args)

            elif tool_name == "get_next_available_slots":
                return await self._get_next_available_slots(tool_args)

            elif tool_name == "register_patient":
                return await self._register_patient(tool_args)

            elif tool_name == "lookup_patient_by_phone":
                return await self._lookup_patient_by_phone(tool_args)

            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error for {tool_name}: {e}")
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}",
                "tool": tool_name
            }

    async def _check_availability(self, args: dict) -> dict:
        """Execute check_doctor_availability tool."""
        target_date = self._parse_date(args["date"])
        if not target_date:
            return {"success": False, "error": "Invalid date format"}

        return await self.engine.check_availability(
            doctor_id=args["doctor_id"],
            target_date=target_date,
            language=args.get("language", "en")
        )

    async def _book_appointment(self, args: dict, session_id: Optional[str]) -> dict:
        """Execute book_appointment tool."""
        appointment_date = self._parse_date(args["date"])
        if not appointment_date:
            return {"success": False, "error": "Invalid date format"}

        result = await self.engine.book_appointment(
            patient_id=args["patient_id"],
            doctor_id=args["doctor_id"],
            appointment_date=appointment_date,
            appointment_time=args["time"],
            reason=args.get("reason"),
            language=args.get("language", "en"),
            session_id=session_id
        )

        # Learn from successful booking
        if result.get("success"):
            await self.memory.learn_from_interaction(
                patient_id=args["patient_id"],
                interaction_data={
                    "doctor_id": args["doctor_id"],
                    "appointment_time": args["time"],
                    "language": args.get("language", "en"),
                }
            )

        return result

    async def _cancel_appointment(self, args: dict) -> dict:
        """Execute cancel_appointment tool."""
        return await self.engine.cancel_appointment(
            appointment_id=args["appointment_id"],
            patient_id=args["patient_id"],
            reason=args.get("reason"),
            language=args.get("language", "en")
        )

    async def _reschedule_appointment(self, args: dict) -> dict:
        """Execute reschedule_appointment tool."""
        new_date = self._parse_date(args["new_date"])
        if not new_date:
            return {"success": False, "error": "Invalid date format"}

        return await self.engine.reschedule_appointment(
            appointment_id=args["appointment_id"],
            patient_id=args["patient_id"],
            new_date=new_date,
            new_time=args["new_time"],
            language=args.get("language", "en")
        )

    async def _find_doctors(self, args: dict) -> dict:
        """Execute find_doctors tool."""
        doctors = await self.engine.find_doctors_by_specialization(
            specialization=args["specialization"],
            language=args.get("language", "en")
        )

        return {
            "success": True,
            "doctors": doctors,
            "count": len(doctors),
            "specialization": args["specialization"]
        }

    async def _get_patient_appointments(self, args: dict) -> dict:
        """Execute get_patient_appointments tool."""
        appointments = await self.engine.get_patient_appointments(
            patient_id=args["patient_id"],
            status_filter=args.get("status"),
            limit=10
        )

        return {
            "success": True,
            "appointments": appointments,
            "count": len(appointments)
        }

    async def _get_next_available_slots(self, args: dict) -> dict:
        """Execute get_next_available_slots tool."""
        from_date = self._parse_date(args["from_date"])
        if not from_date:
            from_date = date.today()

        slots = await self.engine.get_next_available_slots(
            doctor_id=args["doctor_id"],
            from_date=from_date,
            days_ahead=args.get("days_ahead", 7)
        )

        return {
            "success": True,
            "available_dates": slots,
            "count": len(slots)
        }

    async def _register_patient(self, args: dict) -> dict:
        """Register a new patient."""
        try:
            import uuid as _uuid
            existing = await self.memory.get_patient_by_phone(args["phone"])
            if existing:
                return {
                    "success": True,
                    "already_registered": True,
                    "patient_id": existing.get("id") or existing.id if hasattr(existing, "id") else str(existing.get("id", "")),
                    "name": existing.get("name") or getattr(existing, "name", ""),
                    "message": f"Patient already registered. Patient ID: {existing.get('id') or getattr(existing, 'id', '')}"
                }

            patient_data = {
                "id": str(_uuid.uuid4()),
                "name": args["name"],
                "phone": args["phone"],
                "preferred_language": args.get("preferred_language", "en"),
                "preferred_hospital": args.get("preferred_hospital"),
                "medical_history": {},
            }
            patient = await self.memory.create_patient(patient_data)
            if patient:
                pid = patient.get("id") if isinstance(patient, dict) else getattr(patient, "id", patient_data["id"])
                return {
                    "success": True,
                    "patient_id": pid,
                    "name": args["name"],
                    "message": f"Patient registered successfully. Patient ID: {pid}"
                }
            return {"success": False, "error": "Failed to create patient record"}
        except Exception as exc:
            logger.warning(f"register_patient failed: {exc}")
            return {"success": False, "error": str(exc)}

    async def _lookup_patient_by_phone(self, args: dict) -> dict:
        """Look up patient by phone number."""
        try:
            patient = await self.memory.get_patient_by_phone(args["phone"])
            if patient:
                pid = patient.get("id") if isinstance(patient, dict) else getattr(patient, "id", "")
                name = patient.get("name") if isinstance(patient, dict) else getattr(patient, "name", "")
                return {
                    "success": True,
                    "found": True,
                    "patient_id": pid,
                    "name": name,
                    "message": f"Patient found. Name: {name}, Patient ID: {pid}"
                }
            return {
                "success": True,
                "found": False,
                "message": "No patient found with that phone number. Please register first."
            }
        except Exception as exc:
            logger.warning(f"lookup_patient_by_phone failed: {exc}")
            return {"success": False, "error": str(exc)}

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None

        # Handle relative dates
        today = date.today()
        date_lower = date_str.lower().strip()

        if date_lower in ["today", "आज", "இன்று", "ఈరోజు"]:
            return today
        elif date_lower in ["tomorrow", "कल", "நாளை", "రేపు"]:
            return today + timedelta(days=1)
        elif date_lower in ["day after tomorrow", "परसों", "நாளை மறுநாள்", "ఎల్లుండి"]:
            return today + timedelta(days=2)

        # Try parsing standard formats
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y", "%d %B %Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def format_tool_result(self, result: dict) -> str:
        """Format tool result as JSON string for LLM."""
        return json.dumps(result, ensure_ascii=False, default=str)


# Singleton instance
_tool_orchestrator: Optional[ToolOrchestrator] = None


def get_tool_orchestrator() -> ToolOrchestrator:
    """Get or create the tool orchestrator singleton."""
    global _tool_orchestrator
    if _tool_orchestrator is None:
        _tool_orchestrator = ToolOrchestrator()
    return _tool_orchestrator