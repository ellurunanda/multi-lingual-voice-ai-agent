"""Health check and system status endpoints."""
from fastapi import APIRouter
from datetime import datetime
from config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "app_name": settings.app_name,
    }


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health check with service status."""
    services = {}

    # Check Redis
    try:
        from memory.session_memory import get_session_memory
        session_mem = get_session_memory()
        client = await session_mem.get_client()
        await client.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"

    # Check Database
    try:
        from models.db_connection import async_engine
        async with async_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        services["database"] = "healthy"
    except Exception as e:
        services["database"] = f"unhealthy: {str(e)}"

    # Check OpenAI
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        services["openai"] = "configured" if settings.openai_api_key else "not configured"
    except Exception as e:
        services["openai"] = f"error: {str(e)}"

    overall = "healthy" if all(
        v == "healthy" or v == "configured"
        for v in services.values()
    ) else "degraded"

    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
        "services": services,
        "config": {
            "supported_languages": settings.supported_languages_list,
            "target_latency_ms": settings.target_total_latency,
            "model": settings.openai_model,
        }
    }