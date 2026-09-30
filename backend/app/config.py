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

    # CREDIT GUARD. Off by default: with a key present, every browser that
    # opens /ws/audio would otherwise start a billed AssemblyAI stream, and a
    # forgotten tab burns credit with nothing on screen to show for it.
    # Turn on deliberately for a real test, then turn it back off.
    stt_enabled: bool = False

    # Second net, for the case where it is on and a tab is left open. The SDK
    # will not hold a stream past this; a demo turn is seconds, not minutes.
    stt_max_session_seconds: int = 180

    # infra/docker-compose.yml publishes on 5433, not 5432 — see the comment
    # there. Empty means "run without a case record", not "fail to boot".
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
        """A key is configured. Says nothing about whether we may spend it."""
        return self._is_set(self.assemblyai_api_key)

    @property
    def stt_live(self) -> bool:
        """We are allowed to open a billed stream right now."""
        return self.has_stt and self.stt_enabled

    @property
    def has_gemini(self) -> bool:
        return self._is_set(self.gemini_api_key)

    @staticmethod
    def _is_set(value: str) -> bool:
        # .env.example ships placeholders; treating one as a real key produces
        # a 401 from the provider instead of an honest "missing key" message.
        return bool(value) and value not in ("your_key_here", "changeme")


@lru_cache
def get_settings() -> Settings:
    return Settings()
