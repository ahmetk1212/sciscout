"""SciScout genel yapılandırması.

.env dosyasından ayarları yükler. Tüm modüller bu modülü kullanır.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # API anahtarları
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    cerebras_api_key: str = Field(default="", alias="CEREBRAS_API_KEY")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    semantic_scholar_api_key: str = Field(default="", alias="SEMANTIC_SCHOLAR_API_KEY")
    nasa_ads_api_key: str = Field(default="", alias="NASA_ADS_API_KEY")

    # Model seçimi
    model_primary: str = Field(default="groq:llama-3.3-70b-versatile", alias="SCI_MODEL_PRIMARY")
    model_fast: str = Field(default="cerebras:gemma-4-31b", alias="SCI_MODEL_FAST")
    model_fallback: str = Field(default="gemini:gemini-2.5-flash", alias="SCI_MODEL_FALLBACK")

    # Davranış
    log_level: str = Field(default="INFO", alias="SCI_LOG_LEVEL")
    max_papers_per_query: int = Field(default=12, alias="SCI_MAX_PAPERS_PER_QUERY")
    max_web_results: int = Field(default=10, alias="SCI_MAX_WEB_RESULTS")
    pdf_read: bool = Field(default=True, alias="SCI_PDF_READ")

    # Public (test/render)
    debug: bool = Field(default=False, alias="SCI_DEBUG")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Test vb. için cached settings'i sıfırla."""
    get_settings.cache_clear()
    return get_settings()


def required_keys() -> list[tuple[str, bool]]:
    """(env_name, is_required) listesi. LLM anahtarlarından en az biri dolu olmalı."""
    s = get_settings()
    llm_keys = [s.gemini_api_key, s.groq_api_key, s.openrouter_api_key, s.cerebras_api_key]
    has_llm = any(k for k in llm_keys)

    return [
        ("GEMINI_API_KEY", True if not has_llm else False),
        ("GROQ_API_KEY", False),
        ("OPENROUTER_API_KEY", False),
        ("CEREBRAS_API_KEY", False),
        ("TAVILY_API_KEY", s.tavily_api_key == "" and not has_llm),
    ]


def check_configuration() -> tuple[bool, list[str]]:
    """Konfigürasyon geçerli mi? En az bir LLM anahtarı olmalı."""
    s = get_settings()
    llm_keys = [s.gemini_api_key, s.groq_api_key, s.openrouter_api_key, s.cerebras_api_key]
    issues: list[str] = []
    if not any(llm_keys):
        issues.append(
            "Hiç LLM API anahtarı yok. .env dosyasında en az biri dolu olmalı: "
            "GEMINI_API_KEY / GROQ_API_KEY / OPENROUTER_API_KEY / CEREBRAS_API_KEY"
        )
    return len(issues) == 0, issues
