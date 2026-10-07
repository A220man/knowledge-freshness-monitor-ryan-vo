"""Application settings and runtime environment configuration."""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    SECRET_KEY: str = "dev-secret-key-32-chars-long-minimum-kfm-monitor"
    DATABASE_URL: str = "sqlite:///./knowledge_freshness.db"

    # Authentication & OIDC Settings
    AUTH_METHOD: str = "demo"  # "demo" or "oidc"
    OIDC_ISSUER_URL: str = "http://127.0.0.1:8080/realms/knowledge-freshness"
    OIDC_CLIENT_ID: str = "knowledge-freshness-app"
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = "http://127.0.0.1:8000/api/auth/callback"
    SESSION_COOKIE_NAME: str = "kfm_session"
    COOKIE_SECURE: bool = False

    # Optional LLM Advisory Settings
    LLM_PROVIDER: str = "openai-compatible"  # "openai-compatible", "anthropic", "gemini", "ollama"
    LLM_MODEL: str = "qwen3.8-27b"
    LLM_BASE_URL: str = "https://llm.chris-vo.com/v1"
    LLM_API_KEY: str = ""
    LLM_REQUEST_TIMEOUT_SECONDS: int = 15

    def validate_production_guards(self) -> None:
        """Enforces security boundaries for production deployments."""
        normalized_env = self.ENVIRONMENT.strip().lower()
        if normalized_env == "production":
            if self.AUTH_METHOD.strip().lower() == "demo":
                raise RuntimeError(
                    "Startup refused: Local demo authentication is strictly forbidden in production mode. "
                    "Configure Keycloak OIDC issuer credentials and set AUTH_METHOD=oidc."
                )
            if "dev-secret-key" in self.SECRET_KEY:
                raise RuntimeError("Startup refused: Default insecure SECRET_KEY cannot be used in production.")


settings = Settings()
