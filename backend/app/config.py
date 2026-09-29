from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres@127.0.0.1:5432/comedk_compass"
    )
    APP_ENV: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    
    RAW_DATA_DIR: Path = Field(default=BASE_DIR / "data" / "raw" / "comedk")
    
    HTTP_TIMEOUT: float = Field(default=30.0)
    USER_AGENT: str = Field(default="COMEDK-Compass-Ingestion/1.0 (+https://comedk-compass.local)")
    
    PARSER_VERSION: str = Field(default="1.0.0")
    
    MIN_CUTOFF_THRESHOLD_ENGINEERING: int = Field(default=50)
    MIN_CUTOFF_THRESHOLD_ARCHITECTURE: int = Field(default=4)

settings = Settings()
