"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    # Application
    app_name: str = Field(default="VoiceAI-Clinical-Agent", env="APP_NAME")
    app_env: str = Field(default="development", env="APP_ENV")
    app_port: int = Field(default=8000, env="APP_PORT")
    debug: bool = Field(default=True, env="DEBUG")

    # OpenAI
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", env="OPENAI_MODEL")
    openai_whisper_model: str = Field(default="whisper-1", env="OPENAI_WHISPER_MODEL")
    openai_tts_model: str = Field(default="tts-1", env="OPENAI_TTS_MODEL")
    openai_tts_voice: str = Field(default="alloy", env="OPENAI_TTS_VOICE")

    # Database
    database_url: str = Field(
        default="postgresql://voiceai:voiceai_password@localhost:5432/voiceai_db",
        env="DATABASE_URL"
    )
    postgres_user: str = Field(default="voiceai", env="POSTGRES_USER")
    postgres_password: str = Field(default="voiceai_password", env="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="voiceai_db", env="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: str = Field(default="", env="REDIS_PASSWORD")
    session_ttl: int = Field(default=3600, env="SESSION_TTL")

    # WebSocket
    ws_host: str = Field(default="0.0.0.0", env="WS_HOST")
    ws_port: int = Field(default=8001, env="WS_PORT")
    ws_max_connections: int = Field(default=100, env="WS_MAX_CONNECTIONS")

    # Frontend
    frontend_url: str = Field(default="http://localhost:3000", env="FRONTEND_URL")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        env="CORS_ORIGINS"
    )

    # Latency Targets (ms)
    target_stt_latency: int = Field(default=120, env="TARGET_STT_LATENCY")
    target_llm_latency: int = Field(default=200, env="TARGET_LLM_LATENCY")
    target_tts_latency: int = Field(default=100, env="TARGET_TTS_LATENCY")
    target_total_latency: int = Field(default=450, env="TARGET_TOTAL_LATENCY")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", env="LOG_FILE")

    # Campaign Scheduler
    campaign_scheduler_interval: int = Field(default=60, env="CAMPAIGN_SCHEDULER_INTERVAL")
    reminder_hours_before: int = Field(default=24, env="REMINDER_HOURS_BEFORE")

    # Language Support
    supported_languages: str = Field(default="en,hi,ta,te", env="SUPPORTED_LANGUAGES")
    default_language: str = Field(default="en", env="DEFAULT_LANGUAGE")

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def supported_languages_list(self) -> List[str]:
        return [lang.strip() for lang in self.supported_languages.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()