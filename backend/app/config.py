"""Settings, loaded from .env (CLAUDE.MD §8).

§7 is explicit that API keys live only here, never in React. Nothing in this
module should ever be serialised into a WS#1 event.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    assemblyai_api_key: str = ""
    gemini_api_key: str = ""

    # Not used until M2 (create_case). Postgres is not installed locally yet,
    # so the backend deliberately does not open a connection at startup.
    database_url: str = ""

    # §5 VOICE CASTING
    tts_voice_agent: str = "hi-IN-SwaraNeural"
    tts_voice_scammer: str = "hi-IN-MadhurNeural"

    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # §7.3 — AssemblyAI Realtime requires 16kHz PCM16 mono.
    sample_rate: int = 16_000

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def has_stt(self) -> bool:
        return bool(self.assemblyai_api_key) and self.assemblyai_api_key != "your_key_here"


@lru_cache
def get_settings() -> Settings:
    return Settings()
