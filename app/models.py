from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime
from enum import Enum

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    VERIFIED_BY_DATA = "VERIFIED_BY_DATA"
    FAILED = "FAILED"
    CORRUPTED_HASH = "CORRUPTED_HASH"
    NO_HASH = "NO_HASH"
    UPLOADED = "UPLOADED"  # Added missing status
    UNKNOWN = "UNKNOWN"

class CertificateData(BaseModel):
    certificate_number: Optional[str] = Field(None, alias="Certificate Number")
    faculty_name: Optional[str] = Field(None, alias="Faculty Name")
    degree_name: Optional[str] = Field(None, alias="Degree Name")
    student_name: Optional[str] = Field(None, alias="Student Name")
    degree_classification: Optional[str] = Field(None, alias="Degree Classification")
    date: Optional[str] = Field(None, alias="Date")
    
    model_config = {"populate_by_name": True}

class CertificateCreate(BaseModel):
    certificate_data: CertificateData
    hash: Optional[str] = None
    embed_hash: bool = True
    add_watermark: bool = True

class CertificateResponse(BaseModel):
    certificate_number: str
    certificate_data: Dict[str, Any]
    hash: str
    verification_status: VerificationStatus
    confidence: float
    source_image: Optional[str]
    created_at: datetime
    last_verified: Optional[datetime]

class VerificationRequest(BaseModel):
    expected_hash: Optional[str] = None
    use_enhanced_extraction: bool = True
    check_database: bool = True

class VerificationResult(BaseModel):
    verification_status: VerificationStatus
    confidence: float
    hash: Optional[str]
    expected_hash: Optional[str]
    certificate_data: Optional[CertificateData]
    extraction_method: Optional[str]
    similarity_score: Optional[float]
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

class ProcessingOptions(BaseModel):
    embed_hash: bool = True
    use_checksum: bool = True
    add_watermark: bool = False
    watermark_text: Optional[str] = None
    output_format: str = "png"
    
    @field_validator('output_format')
    @classmethod
    def validate_format(cls, v):
        allowed = ['png', 'jpg', 'jpeg']
        if v.lower() not in allowed:
            raise ValueError(f"Output format must be one of {allowed}")
        return v.lower()

class HashEmbedRequest(BaseModel):
    hash_value: Optional[str] = None
    use_checksum: bool = True
    generate_if_missing: bool = True

class WatermarkRequest(BaseModel):
    text: str
    opacity: int = Field(40, ge=0, le=100)
    font_size: int = Field(20, ge=10, le=100)
    pattern: str = Field("diagonal", pattern="^(diagonal|grid|corner)$")

class BatchVerificationRequest(BaseModel):
    expected_hashes: Optional[Dict[str, str]] = None
    use_enhanced_extraction: bool = True
    continue_on_error: bool = True

class BatchVerificationResult(BaseModel):
    total_processed: int
    successful: int
    failed: int
    results: List[VerificationResult]
    processing_time: float

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, bool]

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int
    timestamp: datetime = Field(default_factory=datetime.now)