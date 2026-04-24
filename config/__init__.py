"""
Configuration management for SAP Production Predictor
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    model_config = {"protected_namespaces": (), "extra": "ignore"}
    
    # Supabase (optional legacy support)
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    supabase_service_key: Optional[str] = None
    
    # Project
    project_name: str = "SAP Production Predictor"
    version: str = "1.0.0"
    debug: bool = True
    
    # Model
    model_version: str = "v1.0"
    model_path: str = "models/"
    
    # Feature Engineering
    feature_version: str = "v1.0"
    lookback_days: int = 30
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Database
    db_pool_size: int = 10
    db_max_overflow: int = 20
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "APSDB"
    postgres_user: str = "CNHUSUN"
    postgres_password: str = "lemon1977"
    postgres_schema: str = "public"
    postgres_ssl_mode: str = "disable"  # disable / require / verify-ca / verify-full
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "protected_namespaces": (),
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
