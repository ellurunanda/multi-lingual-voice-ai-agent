"""API routes package."""
from .health import router as health_router
from .appointments import router as appointments_router
from .patients import router as patients_router
from .doctors import router as doctors_router
from .campaigns import router as campaigns_router

__all__ = [
    "health_router",
    "appointments_router",
    "patients_router",
    "doctors_router",
    "campaigns_router",
]