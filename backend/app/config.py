from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: Optional[str] = Field(default=None)
    TEST_DATABASE_URL: Optional[str] = Field(default=None)

    APP_ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Configurable CORS origins (comma-separated string)
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    )

    # Admin API key for internal health and operational endpoints
    ADMIN_API_KEY: Optional[str] = Field(default="dev-admin-key")

    RAW_DATA_DIR: Path = Field(default=BASE_DIR / "data" / "raw" / "comedk")

    HTTP_TIMEOUT: float = Field(default=30.0)
    USER_AGENT: str = Field(default="COMEDK-Compass-Ingestion/1.0 (+https://comedk-compass.local)")

    PARSER_VERSION: str = Field(default="1.0.0")

    MIN_CUTOFF_THRESHOLD_ENGINEERING: int = Field(default=50)
    MIN_CUTOFF_THRESHOLD_ARCHITECTURE: int = Field(default=4)

    @property
    def parsed_cors_origins(self) -> List[str]:
        """Returns clean list of allowed CORS origins from comma-separated string."""
        if not self.CORS_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Strict production security validation: fail closed on insecure configs."""
        is_prod = self.APP_ENV.lower() == "production"

        if is_prod:
            # 1. DATABASE_URL must be explicitly provided in production
            if not self.DATABASE_URL or not self.DATABASE_URL.strip():
                raise ValueError(
                    "Production configuration error: DATABASE_URL must be explicitly configured in production."
                )

            # 2. Reject obviously local development DB hosts in production
            lower_url = self.DATABASE_URL.lower()
            if any(h in lower_url for h in ("localhost", "127.0.0.1", "0.0.0.0", "::1")):
                raise ValueError(
                    "Production configuration error: DATABASE_URL cannot point to local development host (localhost/127.0.0.1) in production."
                )

            origins = self.parsed_cors_origins
            if not origins or "*" in origins:
                raise ValueError(
                    "Production configuration error: CORS_ORIGINS must be explicitly configured "
                    "with trusted origin(s) and cannot contain wildcard '*'."
                )
            if not self.ADMIN_API_KEY or self.ADMIN_API_KEY == "dev-admin-key":
                raise ValueError(
                    "Production configuration error: ADMIN_API_KEY must be set to a secure, "
                    "non-default secret in production."
                )
        else:
            # In development/test, provide default database URL if not set
            if not self.DATABASE_URL or not self.DATABASE_URL.strip():
                self.DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/comedk_compass"

        return self
settings = Settings()
