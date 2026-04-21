"""
Main FastAPI Application Entry Point.
Real-Time Multilingual Voice AI Agent for Clinical Appointment Booking.

Features:
- WebSocket for real-time voice communication
- REST API for appointment management
- Multilingual support: English, Hindi, Tamil, Telugu
- Sub-450ms latency pipeline
"""
import logging
import asyncio
import uuid
import base64
import json
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from config import settings
from models.db_connection import create_tables, get_db
from services.speech_to_text import get_stt_service
from services.text_to_speech import get_tts_service
from services.language_detection import get_language_detection_service
from agent.reasoning.agent_core import get_agent_core
from memory.session_memory import get_session_memory
from memory.persistent_memory import get_persistent_memory
from scheduler.campaign_scheduler import get_campaign_scheduler
from api.routes import appointments, patients, doctors, campaigns, health

# Ensure log directory exists before configuring file handler
if settings.log_file:
    from pathlib import Path
    Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)

# UTF-8 stream handler — prevents UnicodeEncodeError on Windows cp1252 consoles
import sys
import io as _io
_utf8_stream = _io.TextIOWrapper(
    sys.stdout.buffer if hasattr(sys.stdout, 'buffer') else _io.BytesIO(),
    encoding='utf-8',
    errors='replace',
    line_buffering=True,
)
_stream_handler = logging.StreamHandler(_utf8_stream)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        _stream_handler,
        logging.FileHandler(settings.log_file, encoding='utf-8') if settings.log_file else logging.NullHandler(),
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - startup and shutdown."""
    # Startup
    logger.info("Starting Voice AI Clinical Agent...")

    # Initialize database tables (non-fatal if DB is unavailable)
    try:
        await create_tables()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.warning(f"Database unavailable at startup, skipping table creation: {e}")

    try:
        # Start campaign scheduler
        scheduler = get_campaign_scheduler()
        scheduler.start()
        logger.info("Campaign scheduler started")

        # Warm up services
        _ = get_stt_service()
        _ = get_tts_service()
        _ = get_language_detection_service()
        _ = get_agent_core()
        logger.info("AI services initialized")

        logger.info(f"Voice AI Agent ready on port {settings.app_port}")
        logger.info(f"Target latency: <{settings.target_total_latency}ms")
        logger.info(f"Supported languages: {settings.supported_languages}")

    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)

    yield

    # Shutdown
    logger.info("🛑 Shutting down Voice AI Agent...")
    scheduler = get_campaign_scheduler()
    scheduler.stop()

    session_memory = get_session_memory()
    await session_memory.close()

    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Voice AI Clinical Appointment Agent",
    description="Real-Time Multilingual Voice AI Agent for Clinical Appointment Booking",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["Appointments"])
app.include_router(patients.router, prefix="/api/patients", tags=["Patients"])
app.include_router(doctors.router, prefix="/api/doctors", tags=["Doctors"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])


# WebSocket Connection Manager
class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id} (total: {len(self.active_connections)})")

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        logger.info(f"WebSocket disconnected: {session_id} (total: {len(self.active_connections)})")

    async def send_json(self, session_id: str, data: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(data)

    async def send_bytes(self, session_id: str, data: bytes):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_bytes(data)

    def get_active_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()


@app.websocket("/ws/voice/{session_id}")
async def voice_websocket(
    websocket: WebSocket,
    session_id: str,
    patient_id: Optional[str] = None,
    language: Optional[str] = None
):
    """
    Main WebSocket endpoint for real-time voice conversation.

    Message types from client:
    - {"type": "audio", "data": "<base64_audio>", "format": "webm"}
    - {"type": "text", "data": "<text_message>"}
    - {"type": "start_session", "patient_id": "...", "language": "en"}
    - {"type": "end_session"}

    Message types to client:
    - {"type": "transcript", "text": "...", "language": "..."}
    - {"type": "response_text", "text": "...", "language": "..."}
    - {"type": "audio_response", "data": "<base64_audio>", "format": "mp3"}
    - {"type": "latency", "metrics": {...}}
    - {"type": "error", "message": "..."}
    - {"type": "session_started", "session_id": "..."}
    """
    await manager.connect(websocket, session_id)

    # Initialize services
    stt_service = get_stt_service()
    tts_service = get_tts_service()
    agent = get_agent_core()
    session_memory = get_session_memory()

    # Create session
    session = await session_memory.create_session(session_id, patient_id)
    if language:
        await session_memory.set_language(session_id, language)

    # Send session started confirmation
    await websocket.send_json({
        "type": "session_started",
        "session_id": session_id,
        "language": language or settings.default_language,
        "message": "Voice AI Agent connected. How can I help you?"
    })

    # Send greeting audio
    try:
        greeting_text = await agent.get_greeting(
            language=language or settings.default_language
        )
        greeting_audio, _ = await tts_service.synthesize(
            greeting_text,
            language=language or settings.default_language
        )
        await websocket.send_json({
            "type": "response_text",
            "text": greeting_text,
            "language": language or settings.default_language,
        })
        await websocket.send_json({
            "type": "audio_response",
            "data": base64.b64encode(greeting_audio).decode("utf-8"),
            "format": "mp3",
        })
    except Exception as e:
        logger.warning(f"Failed to send greeting: {e}")

    try:
        while True:
            # Receive message from client
            raw_message = await websocket.receive()

            if "text" in raw_message:
                message = json.loads(raw_message["text"])
                msg_type = message.get("type", "")

                if msg_type == "audio":
                    # Process audio message
                    await handle_audio_message(
                        websocket=websocket,
                        message=message,
                        session_id=session_id,
                        patient_id=patient_id,
                        stt_service=stt_service,
                        tts_service=tts_service,
                        agent=agent,
                        session_memory=session_memory,
                    )

                elif msg_type == "text":
                    # Process text message (for testing without audio)
                    await handle_text_message(
                        websocket=websocket,
                        message=message,
                        session_id=session_id,
                        patient_id=patient_id,
                        tts_service=tts_service,
                        agent=agent,
                        session_memory=session_memory,
                    )

                elif msg_type == "end_session":
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id,
                        "message": "Session ended. Goodbye!"
                    })
                    break

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

            elif "bytes" in raw_message:
                # Handle raw binary audio data
                audio_bytes = raw_message["bytes"]
                await handle_raw_audio(
                    websocket=websocket,
                    audio_bytes=audio_bytes,
                    session_id=session_id,
                    patient_id=patient_id,
                    stt_service=stt_service,
                    tts_service=tts_service,
                    agent=agent,
                    session_memory=session_memory,
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": "An error occurred. Please try again."
            })
        except Exception:
            pass
    finally:
        manager.disconnect(session_id)


async def handle_audio_message(
    websocket: WebSocket,
    message: dict,
    session_id: str,
    patient_id: Optional[str],
    stt_service,
    tts_service,
    agent,
    session_memory,
):
    """Handle incoming audio message through the full pipeline."""
    pipeline_start = time.time()

    try:
        # Decode base64 audio
        audio_data = base64.b64decode(message["data"])
        audio_format = message.get("format", "webm")
        language_hint = message.get("language_hint")

        # Get current session language
        session_language = await session_memory.get_language(session_id)

        # Step 1: Speech-to-Text
        await websocket.send_json({"type": "processing", "stage": "stt"})

        transcript, detected_language, stt_latency = await stt_service.transcribe_with_fallback(
            audio_data=audio_data,
            language_hint=language_hint or session_language,
            audio_format=audio_format
        )

        if not transcript.strip():
            await websocket.send_json({
                "type": "error",
                "message": "Could not understand audio. Please speak clearly."
            })
            return

        # Send transcript to client
        await websocket.send_json({
            "type": "transcript",
            "text": transcript,
            "language": detected_language,
            "stt_latency_ms": stt_latency,
        })

        # Step 2: Process through AI agent
        await websocket.send_json({"type": "processing", "stage": "llm"})

        agent_result = await agent.process_text(
            text=transcript,
            session_id=session_id,
            patient_id=patient_id,
            detected_language=detected_language,
            stt_latency_ms=stt_latency,
        )

        response_text = agent_result["response_text"]
        response_language = agent_result["language"]

        # Send text response
        await websocket.send_json({
            "type": "response_text",
            "text": response_text,
            "language": response_language,
            "llm_latency_ms": agent_result["latency"].get("stages", {}).get("llm_ms", 0),
        })

        # Step 3: Text-to-Speech
        await websocket.send_json({"type": "processing", "stage": "tts"})

        audio_response, tts_latency = await tts_service.synthesize(
            text=response_text,
            language=response_language
        )

        # Send audio response
        await websocket.send_json({
            "type": "audio_response",
            "data": base64.b64encode(audio_response).decode("utf-8"),
            "format": "mp3",
            "tts_latency_ms": tts_latency,
        })

        # Send latency metrics
        total_latency = int((time.time() - pipeline_start) * 1000)
        latency_report = {
            "stt_ms": stt_latency,
            "llm_ms": agent_result["latency"].get("stages", {}).get("llm_ms", 0),
            "tts_ms": tts_latency,
            "total_ms": total_latency,
            "target_ms": settings.target_total_latency,
            "met_target": total_latency <= settings.target_total_latency,
        }

        await websocket.send_json({
            "type": "latency",
            "metrics": latency_report,
        })

        logger.info(
            f"Pipeline complete [{session_id[:8]}]: "
            f"STT={stt_latency}ms LLM={latency_report['llm_ms']}ms "
            f"TTS={tts_latency}ms Total={total_latency}ms "
            f"{'✅' if latency_report['met_target'] else '⚠️'}"
        )

    except Exception as e:
        logger.error(f"Audio pipeline error: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": "Failed to process audio. Please try again."
        })


async def handle_text_message(
    websocket: WebSocket,
    message: dict,
    session_id: str,
    patient_id: Optional[str],
    tts_service,
    agent,
    session_memory,
):
    """Handle text message (bypasses STT)."""
    pipeline_start = time.time()

    try:
        text = message.get("data", "").strip()
        if not text:
            return

        language_hint = message.get("language")
        session_language = await session_memory.get_language(session_id)

        # Process through AI agent
        agent_result = await agent.process_text(
            text=text,
            session_id=session_id,
            patient_id=patient_id,
            detected_language=language_hint or session_language,
            stt_latency_ms=0,
        )

        response_text = agent_result["response_text"]
        response_language = agent_result["language"]

        # Send text response
        await websocket.send_json({
            "type": "response_text",
            "text": response_text,
            "language": response_language,
        })

        # Generate and send audio
        audio_response, tts_latency = await tts_service.synthesize(
            text=response_text,
            language=response_language
        )

        await websocket.send_json({
            "type": "audio_response",
            "data": base64.b64encode(audio_response).decode("utf-8"),
            "format": "mp3",
        })

        total_latency = int((time.time() - pipeline_start) * 1000)
        await websocket.send_json({
            "type": "latency",
            "metrics": {
                "stt_ms": 0,
                "llm_ms": agent_result["latency"].get("stages", {}).get("llm_ms", 0),
                "tts_ms": tts_latency,
                "total_ms": total_latency,
                "target_ms": settings.target_total_latency,
                "met_target": total_latency <= settings.target_total_latency,
            }
        })

    except Exception as e:
        logger.error(f"Text pipeline error: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": "Failed to process message. Please try again."
        })


async def handle_raw_audio(
    websocket: WebSocket,
    audio_bytes: bytes,
    session_id: str,
    patient_id: Optional[str],
    stt_service,
    tts_service,
    agent,
    session_memory,
):
    """Handle raw binary audio data."""
    await handle_audio_message(
        websocket=websocket,
        message={"data": base64.b64encode(audio_bytes).decode(), "format": "webm"},
        session_id=session_id,
        patient_id=patient_id,
        stt_service=stt_service,
        tts_service=tts_service,
        agent=agent,
        session_memory=session_memory,
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Voice AI Clinical Appointment Agent",
        "version": "1.0.0",
        "status": "running",
        "supported_languages": settings.supported_languages_list,
        "target_latency_ms": settings.target_total_latency,
        "active_connections": manager.get_active_count(),
    }


@app.get("/api/ws-info")
async def websocket_info():
    """WebSocket connection information."""
    return {
        "websocket_url": f"ws://localhost:{settings.app_port}/ws/voice/{{session_id}}",
        "params": {
            "session_id": "unique session identifier",
            "patient_id": "optional patient ID",
            "language": "optional language hint (en/hi/ta/te)"
        },
        "message_types": {
            "client_to_server": ["audio", "text", "start_session", "end_session", "ping"],
            "server_to_client": ["transcript", "response_text", "audio_response", "latency", "error", "session_started"]
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.ws_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )