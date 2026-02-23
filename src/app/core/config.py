from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MAX_FRAMES_PER_POST: int = 12
    FRAME_SAMPLE_FPS: float = 1.0
    REQUEST_TIMEOUT: int = 30

    MEDIA_ROOT: str = "/tmp/ai_content_analysis"

    ASSEMBLYAI_API_KEY: str
    SIGHTENGINE_API_USER: str
    SIGHTENGINE_API_SECRET: str
    CLAUDE_API_KEY: str

    RETRY_ATTEMPTS: int = 3

    TRANSCRIPTION_POLL_SECONDS: float = 2.0
    TRANSCRIPTION_MAX_POLLS: int = 120

    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
    CLAUDE_MAX_TOKENS: int = 800
    CLAUDE_TEMPERATURE: float = 0.2

    REDIS_URL: str = "redis://redis:6379/0"
    
settings = Settings()