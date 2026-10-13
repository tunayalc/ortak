from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_environment: Literal["development", "test", "production"] = Field(default="development", alias="APP_ENVIRONMENT")
    public_base_url: str = Field(default="", alias="PUBLIC_BASE_URL")
    session_secret: str = Field(default="", alias="SESSION_SECRET", repr=False)
    public_max_participants: int = Field(default=8, ge=2, le=12, alias="PUBLIC_MAX_PARTICIPANTS")
    public_max_candidates: int = Field(default=3, ge=3, le=20, alias="PUBLIC_MAX_CANDIDATES")
    public_max_k: int = Field(default=3, ge=1, le=20, alias="PUBLIC_MAX_K")
    google_budget_limit_tl: float = Field(default=1200, gt=0, allow_inf_nan=False, alias="GOOGLE_BUDGET_LIMIT_TL")
    google_budget_enforcement_enabled: bool = Field(default=False, alias="GOOGLE_BUDGET_ENFORCEMENT_ENABLED")
    google_unit_prices_tl: dict[str, float] = Field(default_factory=dict, alias="GOOGLE_UNIT_PRICES_TL")
    google_price_verified_at: Optional[datetime] = Field(default=None, alias="GOOGLE_PRICE_VERIFIED_AT")
    google_price_source: str = Field(default="", alias="GOOGLE_PRICE_SOURCE")
    google_ledger_watermark_path: str = Field(default="", alias="GOOGLE_LEDGER_WATERMARK_PATH")
    google_maps_api_key: Optional[str] = Field(default=None, alias="GOOGLE_MAPS_API_KEY")
    google_maps_calls_enabled: bool = Field(default=False, alias="GOOGLE_MAPS_CALLS_ENABLED")
    google_maps_daily_call_limit: int = Field(default=33, ge=0, alias="GOOGLE_MAPS_DAILY_CALL_LIMIT")
    google_maps_max_attempts: int = Field(default=3, ge=1, le=3, alias="GOOGLE_MAPS_MAX_ATTEMPTS")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    llm_provider: Literal["ollama", "openai", "disabled"] = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3:8b", alias="OLLAMA_MODEL")
    database_url: str = Field(default="sqlite:///./ortak.db", alias="DATABASE_URL")
    allowed_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
        alias="ALLOWED_ORIGINS",
    )
    osrm_base_url: str = Field(default="http://router.project-osrm.org", alias="OSRM_BASE_URL")

    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[1] / ".env", Path.cwd() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("google_price_verified_at", mode="before")
    @classmethod
    def blank_price_timestamp(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_production(self):
        if self.production:
            parsed = urlparse(self.public_base_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
                raise ValueError("PUBLIC_BASE_URL must be a single HTTPS origin.")
            self.public_base_url = self.public_base_url.rstrip("/")
            if len(self.session_secret) < 32:
                raise ValueError("Production requires a SESSION_SECRET of at least 32 characters.")
            if self.llm_provider != "ollama":
                raise ValueError("This release requires the explicitly selected Ollama provider.")
            if self.ollama_model != "llama3:8b":
                raise ValueError("This release requires llama3:8b; automatic model substitution is not allowed.")
            if self.google_budget_limit_tl > 1200:
                raise ValueError("The authorized release reserve cannot exceed 1200 TL.")
            if self.public_max_participants > 8 or self.public_max_candidates > 3 or self.public_max_k > 3:
                raise ValueError("Public beta limits are 8 participants, 3 candidates and Top-K 3.")
            if self.google_maps_daily_call_limit > 33:
                raise ValueError("The authorized daily Google call limit cannot exceed 33.")
        return self

    @property
    def production(self) -> bool:
        return self.app_environment == "production"

    @property
    def google_budget_protected(self) -> bool:
        return self.production or self.google_budget_enforcement_enabled

    @property
    def origins(self) -> list[str]:
        if self.production:
            return [self.public_base_url]
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def has_google_key(self) -> bool:
        return bool(self.google_maps_api_key and self.google_maps_api_key.strip())

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key and self.openai_api_key.strip())

    @property
    def llm_model(self) -> str:
        return self.ollama_model if self.llm_provider == "ollama" else self.openai_model if self.llm_provider == "openai" else ""

    @property
    def has_llm_config(self) -> bool:
        if self.llm_provider == "ollama":
            return bool(self.ollama_base_url.strip() and self.ollama_model.strip())
        return self.llm_provider == "openai" and self.has_openai_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
