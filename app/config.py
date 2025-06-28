from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # API Settings
    app_name: str = "Certificate Verification API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = False
    
    # Security
    secret_key: str = "your-secret-key-change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # File Storage
    upload_dir: str = "data/certificates"
    processed_dir: str = "data/processed"
    database_dir: str = "data/database"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: set = {".png", ".jpg", ".jpeg", ".pdf"}
    
    # Certificate Processing
    hash_block_size: int = 12  # Larger blocks for better scan resistance
    hash_spacing_y: int = 20
    hash_start_x: int = 100
    hash_start_y: int = 300
    use_checksum: bool = True
    
    # OCR Settings
    tesseract_cmd: Optional[str] = None  # Path to tesseract if not in PATH
    ocr_timeout: int = 30
    
    # Database
    database_file: str = "certificate_database.json"
    
    # Verification Thresholds
    min_confidence_threshold: float = 0.8
    min_entropy_threshold: int = 10
    data_match_threshold: float = 0.8
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

# Create directories if they don't exist
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.processed_dir, exist_ok=True)
os.makedirs(settings.database_dir, exist_ok=True)