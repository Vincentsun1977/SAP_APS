"""
Configuration management for SAP Production Predictor
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
