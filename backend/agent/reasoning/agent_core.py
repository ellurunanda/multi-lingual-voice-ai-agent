"""
Core AI Agent reasoning engine.
Orchestrates the full conversation pipeline:
STT → Language Detection → LLM Reasoning → Tool Calls → TTS
Measures and logs latency at each stage.
"""
import time
import logging
import json
import asyncio
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime
import openai

from config import settings
from agent.prompt.system_prompts import build_system_prompt, INTENT_EXTRACTION_PROMPT
from agent.tools.appointment_tools import APPOINTMENT_TOOLS, get_tool_orchestrator
from memory.session_memory import get_session_memory
from memory.persistent_memory import get_persistent_memory
from services.language_detection import get_language_detection_service

logger = logging.getLogger(__name__)

# Fallback messages per language when LLM fails
FALLBACK_MESSAGES = {
    "en": "I'm having trouble processing that request. Could you please repeat?",
    "hi": "मुझे आपका अनुरोध समझने में परेशानी हो रही है। क्या आप दोबारा कह सकते हैं?",
    "ta": "உங்கள் கோரிக்கையை புரிந்துகொள்வதில் சிரமம் உள்ளது. மீண்டும் சொல்ல முடியுமா?",
    "te": "మీ అభ్యర్థనను అర్థం చేసుకోవడంలో సమస్య ఉంది. మళ్ళీ చెప్పగలరా?",
}

GREETING_MESSAGES = {
    "en": "Hello! I'm Arogya AI, your healthcare appointment assistant. How can I help you today?",
    "hi": "नमस्ते! मैं आरोग्य AI हूं, आपका स्वास्थ्य सेवा अपॉइंटमेंट सहायक। आज मैं आपकी कैसे मदद कर सकता हूं?",
    "ta": "வணக்கம்! நான் ஆரோக்ய AI, உங்கள் சுகாதார சந்திப்பு உதவியாளர். இன்று நான் உங்களுக்கு எப்படி உதவ முடியும்?",
    "te": "నమస్కారం! నేను ఆరోగ్య AI, మీ ఆరోగ్య సేవా అపాయింట్‌మెంట్ సహాయకుడు. ఈరోజు నేను మీకు ఎలా సహాయం చేయగలను?",
}


class LatencyTracker:
    """Tracks latency at each pipeline stage."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.pipeline_start = time.time()
        self.stages: Dict[str, float] = {}

    def mark(self, stage: str):
        """Mark the end of a pipeline stage."""
        self.stages[stage] = (time.time() - self.pipeline_start) * 1000

    def get_stage_latency(self, stage: str) -> int:
        """Get latency for a specific stage in ms."""
        return int(self.stages.get(stage, 0))

    def get_total_latency(self) -> int:
        """Get total pipeline latency in ms."""
        return int((time.time() - self.pipeline_start) * 1000)

    def get_report(self) -> Dict[str, Any]:
        """Get full latency report."""
        total = self.get_total_latency()
        report = {
            "session_id": self.session_id,
            "total_ms": total,
            "target_ms": settings.target_total_latency,
            "met_target": total <= settings.target_total_latency,
            "stages": {k: int(v) for k, v in self.stages.items()},
        }
        return report

    def log_report(self):
        """Log the latency report."""
        report = self.get_report()
        status = "✅" if report["met_target"] else "⚠️"
        logger.info(
            f"{status} Latency Report [{self.session_id[:8]}]: "
            f"Total={report['total_ms']}ms (target={report['target_ms']}ms) | "
            f"Stages: {report['stages']}"
        )
        return report


class AgentCore:
    """
    Core AI Agent that orchestrates the full voice conversation pipeline.
    Handles multilingual conversations with tool-augmented LLM reasoning.
    """

    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.session_memory = get_session_memory()
        self.persistent_memory = get_persistent_memory()
        self.language_detector = get_language_detection_service()
        self.tool_orchestrator = get_tool_orchestrator()
        logger.info(f"Agent Core initialized with model: {self.model}")

    async def process_text(
        self,
        text: str,
        session_id: str,
        patient_id: Optional[str] = None,
        detected_language: Optional[str] = None,
        stt_latency_ms: int = 0
    ) -> Dict[str, Any]:
        """
        Process transcribed text through the AI pipeline.

        Args:
            text: Transcribed user text
            session_id: Session identifier
            patient_id: Optional patient ID
            detected_language: Language detected by STT
            stt_latency_ms: STT latency for tracking

        Returns:
            Dict with response text, language, and latency metrics
        """
        tracker = LatencyTracker(session_id)
        tracker.stages["stt_ms"] = stt_latency_ms

        try:
            # Step 1: Detect/confirm language
            if not detected_language:
                lang, confidence = await self.language_detector.detect(text)
                detected_language = lang
            tracker.mark("language_detection_ms")

            # Step 2: Get/create session
            session = await self.session_memory.get_session(session_id)
            if not session:
                session = await self.session_memory.create_session(session_id, patient_id)

            # Update session language if changed
            session_language = session.get("language", settings.default_language)
            if detected_language and detected_language != session_language:
                await self.session_memory.set_language(session_id, detected_language)
                session_language = detected_language

            # Step 3: Add user message to session history
            await self.session_memory.add_message(
                session_id, "user", text, session_language
            )

            # Step 4: Get patient context for personalization
            patient_context = ""
            if patient_id:
                context_data = await self.persistent_memory.get_patient_context(patient_id)
                patient_context = self._format_patient_context(context_data)

            # Step 5: Build conversation history for LLM
            history = await self.session_memory.get_conversation_history(session_id, max_turns=8)
            history_text = self._format_history(history)

            # Step 6: Build system prompt
            system_prompt = build_system_prompt(
                language=session_language,
                patient_context=patient_context,
                conversation_history=history_text,
                current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )

            # Step 7: Call LLM with tool support
            llm_start = time.time()
            response_text, tool_calls_made = await self._call_llm_with_tools(
                system_prompt=system_prompt,
                user_message=text,
                session_id=session_id,
                patient_id=patient_id,
                language=session_language,
                history=history
            )
            llm_latency_ms = int((time.time() - llm_start) * 1000)
            tracker.stages["llm_ms"] = llm_latency_ms
            tracker.mark("llm_complete_ms")

            # Step 8: Add assistant response to session
            await self.session_memory.add_message(
                session_id, "assistant", response_text, session_language,
                metadata={"latency_ms": llm_latency_ms}
            )

            # Step 9: Log to persistent storage
            await self.persistent_memory.log_conversation(
                session_id=session_id,
                patient_id=patient_id,
                role="assistant",
                content=response_text,
                language=session_language,
                latency_data={
                    "stt_ms": stt_latency_ms,
                    "llm_ms": llm_latency_ms,
                    "total_ms": tracker.get_total_latency()
                }
            )

            # Step 10: Log latency metrics
            latency_report = tracker.log_report()

            return {
                "success": True,
                "response_text": response_text,
                "language": session_language,
                "session_id": session_id,
                "latency": latency_report,
                "tool_calls": tool_calls_made,
            }

        except Exception as e:
            logger.error(f"Agent processing error: {e}", exc_info=True)
            fallback = FALLBACK_MESSAGES.get(
                detected_language or "en",
                FALLBACK_MESSAGES["en"]
            )
            return {
                "success": False,
                "response_text": fallback,
                "language": detected_language or "en",
                "session_id": session_id,
                "error": str(e),
                "latency": tracker.get_report(),
            }

    async def _call_llm_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        session_id: str,
        patient_id: Optional[str],
        language: str,
        history: List[dict]
    ) -> tuple[str, List[dict]]:
        """
        Call LLM with tool support and handle tool execution loop.

        Returns:
            Tuple of (response_text, list_of_tool_calls_made)
        """
        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history (excluding current message)
        for msg in history[:-1]:  # Exclude last message (current user input)
            if msg["role"] in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        tool_calls_made = []
        max_iterations = 5  # Prevent infinite tool call loops

        for iteration in range(max_iterations):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=APPOINTMENT_TOOLS,
                    tool_choice="auto",
                    temperature=0.3,
                    max_tokens=500,
                )

                message = response.choices[0].message

                # Check if LLM wants to call tools
                if message.tool_calls:
                    # Add assistant message with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}

                        # Add patient_id and language to tool args if not present
                        if patient_id and "patient_id" not in tool_args:
                            tool_args["patient_id"] = patient_id
                        if "language" not in tool_args:
                            tool_args["language"] = language

                        logger.info(f"Calling tool: {tool_name}")
                        tool_result = await self.tool_orchestrator.execute_tool(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            session_id=session_id
                        )

                        tool_calls_made.append({
                            "tool": tool_name,
                            "args": tool_args,
                            "result": tool_result
                        })

                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result, ensure_ascii=False, default=str)
                        })

                    # Continue loop to get final response
                    continue

                else:
                    # No more tool calls - return final response
                    return message.content or FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES["en"]), tool_calls_made

            except openai.APIError as e:
                logger.error(f"OpenAI API error in LLM call: {e}")
                raise

        # If we hit max iterations, return fallback
        logger.warning(f"Hit max tool call iterations ({max_iterations}) for session {session_id}")
        return FALLBACK_MESSAGES.get(language, FALLBACK_MESSAGES["en"]), tool_calls_made

    async def get_greeting(self, language: str = "en", patient_name: Optional[str] = None) -> str:
        """Get greeting message in specified language."""
        greeting = GREETING_MESSAGES.get(language, GREETING_MESSAGES["en"])
        if patient_name:
            # Personalize greeting
            if language == "en":
                greeting = f"Hello {patient_name}! " + greeting.split("Hello! ")[1]
            elif language == "hi":
                greeting = f"नमस्ते {patient_name}! " + greeting.split("नमस्ते! ")[1]
            elif language == "ta":
                greeting = f"வணக்கம் {patient_name}! " + greeting.split("வணக்கம்! ")[1]
            elif language == "te":
                greeting = f"నమస్కారం {patient_name}! " + greeting.split("నమస్కారం! ")[1]
        return greeting

    def _format_patient_context(self, context_data: dict) -> str:
        """Format patient context for LLM prompt."""
        if not context_data:
            return "No patient context available"

        patient = context_data.get("patient", {})
        preferences = context_data.get("preferences", {})
        recent_appointments = context_data.get("recent_appointments", [])

        lines = []
        if patient:
            lines.append(f"Patient: {patient.get('name', 'Unknown')}")
            lines.append(f"Phone: {patient.get('phone', 'Unknown')}")
            lines.append(f"Preferred Language: {patient.get('preferred_language', 'en')}")
            if patient.get("preferred_hospital"):
                lines.append(f"Preferred Hospital: {patient['preferred_hospital']}")

        if preferences:
            if "last_doctor" in preferences:
                lines.append(f"Last Doctor: {preferences['last_doctor'].get('data', {})}")
            if "preferred_time" in preferences:
                lines.append(f"Preferred Time: {preferences['preferred_time'].get('data', {})}")

        if recent_appointments:
            lines.append(f"Recent Appointments: {len(recent_appointments)} found")
            for appt in recent_appointments[:2]:
                lines.append(
                    f"  - {appt.get('appointment_date')} at {appt.get('appointment_time')} "
                    f"(Status: {appt.get('status')})"
                )

        return "\n".join(lines)

    def _format_history(self, history: List[dict]) -> str:
        """Format conversation history for LLM prompt."""
        if not history:
            return "No previous conversation"

        lines = []
        for msg in history[-6:]:  # Last 3 turns
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")

        return "\n".join(lines)


# Singleton instance
_agent_core: Optional[AgentCore] = None


def get_agent_core() -> AgentCore:
    """Get or create the agent core singleton."""
    global _agent_core
    if _agent_core is None:
        _agent_core = AgentCore()
    return _agent_core