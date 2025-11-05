"""Configuration management for OCR pipeline."""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings."""
    
    # OpenAI Configuration
    openai_api_key: str
    
    # Database Configuration
    # Use absolute path to ensure database is created in project root
    _db_path = Path(__file__).parent.parent / "ocr_pipeline.db"
    database_url: str = f"sqlite:///{_db_path.absolute()}"
    
    # Retry Configuration
    max_retries: int = 2
    retry_backoff_multiplier: float = 2.0
    
    # Storage Paths
    upload_dir: str = "./uploads"
    processed_dir: str = "./processed"
    reports_dir: str = "./reports"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CrewAI Configuration
    crewai_timeout: int = 300  # Timeout in seconds for CrewAI execution
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.processed_dir, exist_ok=True)
os.makedirs(settings.reports_dir, exist_ok=True)

