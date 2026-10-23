"""Application configuration module using Pydantic Settings."""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment and .env file."""

    # Application metadata
    app_name: str = "TrueBasket Backend API"
    app_version: str = "0.1.0"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # CORS configuration
    cors_origins_env: Optional[str] = None
    frontend_origin: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"

    # Tavily Web Search API
    tavily_api_key: Optional[str] = None
    tavily_api_base_url: str = "https://api.tavily.com"
    tavily_timeout_seconds: float = 15.0
    tavily_max_results_default: int = 5
    tavily_max_results_limit: int = 10

    # Gemma 4 LLM & Multimodal Configuration
    # Options for gemma_provider: "google" | "openai_compatible"
    gemma_provider: str = "google"
    gemma_model: str = "gemma-4-26b-a4b-it"
    gemma_api_key: Optional[str] = None
    gemma_api_base_url: Optional[str] = None
    gemma_timeout_seconds: float = 60.0
    gemma_temperature: float = 0.2
    gemma_max_output_tokens: int = 4096

    # OpenRouter AI Vision Configuration (PillSync Approach)
    ai_vision_provider: str = "google"
    openrouter_api_key: Optional[str] = None
    openrouter_vision_model: str = "google/gemma-4-26b-a4b-it"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: float = 45.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated frontend origins into a list from CORS_ORIGINS or FRONTEND_ORIGIN."""
        import os
        raw = os.getenv("CORS_ORIGINS") or self.cors_origins_env or self.frontend_origin
        if not raw:
            return ["*"]
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        for default_origin in ["http://localhost:5173", "http://127.0.0.1:5173"]:
            if default_origin not in origins and "*" not in origins:
                origins.append(default_origin)
        return origins

    @property
    def is_tavily_configured(self) -> bool:
        """Check if Tavily API key is set and not a placeholder."""
        if not self.tavily_api_key:
            return False
        clean = self.tavily_api_key.strip()
        return bool(clean and not clean.startswith("tvly-your-") and clean != "your_tavily_api_key")

    @property
    def is_gemma_configured(self) -> bool:
        """Check if Gemma 4 inference is configured properly for the chosen provider."""
        provider = (self.gemma_provider or "").lower()
        if provider == "google":
            if not self.gemma_api_key:
                return False
            clean = self.gemma_api_key.strip()
            return bool(clean and not clean.startswith("your-") and clean != "your_gemma_api_key")
        elif provider == "openai_compatible":
            return bool(self.gemma_api_base_url and self.gemma_api_base_url.strip())
        return False

    @property
    def is_openrouter_configured(self) -> bool:
        """Check if OpenRouter API key is set and not a placeholder."""
        if not self.openrouter_api_key:
            return False
        clean = self.openrouter_api_key.strip()
        return bool(clean and not clean.startswith("your_") and not clean.startswith("sk-or-v1-your-"))

    @property
    def active_vision_provider(self) -> str:
        """Determine active vision provider ('openrouter' or 'google' / 'openai_compatible')."""
        prov = (self.ai_vision_provider or "").lower().strip()
        if prov == "openrouter":
            if self.is_openrouter_configured:
                return "openrouter"
            if self.is_gemma_configured:
                return (self.gemma_provider or "google").lower().strip()
            return "openrouter"
        return prov or "openrouter"


@lru_cache()
def get_settings() -> Settings:
    """Retrieve and cache settings singleton."""
    return Settings()
