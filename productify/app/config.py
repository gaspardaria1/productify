from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repo root, resolved from this file. Everything on disk is anchored here, so
# the app behaves identically no matter which directory uvicorn was launched from.
# A CWD-relative .env would silently not load, leaving MOCK at its default of True
# and turning every real model call into a mock — mid-demo, with no error.
ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Blank by default on purpose: the app must still boot and serve the gallery
    # with no key present. Station 2 runs this way all day.
    OPENAI_API_KEY: str = ""
    MOCK: bool = True
    MAX_IMAGE_CALLS: int = 40
    OUT_DIR: str = "out/pitches"


settings = Settings()

# Shared spend cap. One gpt-image-1 call per pitch, maximum.
_image_calls_used = 0


def can_call_image() -> bool:
    return _image_calls_used < settings.MAX_IMAGE_CALLS


def note_image_call() -> None:
    global _image_calls_used
    _image_calls_used += 1


def image_calls_used() -> int:
    return _image_calls_used
