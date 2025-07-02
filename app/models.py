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
    ERROR = "ERROR"  # Added for error cases

class CertificateData(BaseModel):
    certificate_number: Optional[str] = Field(None, alias="Certificate Number")
    faculty_name: Optional[str] = Field(None, alias="Faculty Name")
    degree_name: Optional[str] = Field(None, alias="Degree Name")
    student_name: Optional[str] = Field(None, alias="Student Name")
    degree_classification: Optional[str] = Field(None, alias="Degree Classification")
    institution_name: Optional[str] = Field(None, alias="Institution Name")
    date: Optional[str] = Field(None, alias="Date")
    research_focus_area: Optional[str] = Field(None, alias="Research Focus Area")
    
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
    certificate_exists_in_ledger: bool = False  # ✅ Added for frontend compatibility
    timestamp: datetime = Field(default_factory=datetime.now)

# ✅ NEW: Batch verification models
class BatchVerificationRequest(BaseModel):
    """Request model for batch verification."""
    use_enhanced_extraction: bool = True
    check_database: bool = True
    continue_on_error: bool = True
    expected_hashes: Optional[Dict[str, str]] = None  # filename -> expected_hash mapping

class IndividualVerificationResult(BaseModel):
    """Individual verification result within batch."""
    filename: str
    verification_status: str
    confidence: float
    hash: Optional[str] = None
    message: str = ""
    certificate_data: Optional[Dict[str, Any]] = None
    extraction_method: Optional[str] = None
    similarity_score: Optional[float] = None
    certificate_exists_in_ledger: bool = False

class BatchVerificationResult(BaseModel):
    """Response model for batch verification."""
    total_processed: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]  # List of individual verification results
    processing_time: float
    message: str = ""

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
            raise ValueError(f'Output format must be one of {allowed}')
        return v.lower()

class HashEmbedRequest(BaseModel):
    use_checksum: bool = True

class WatermarkRequest(BaseModel):
    text: str
    pattern: str = "diagonal"
    opacity: float = Field(default=40, ge=0, le=100)
    font_size: int = Field(default=32, ge=12, le=72)

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, bool]

class ResponseModel(BaseModel):
    """Generic response model for API endpoints."""
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# ✅ NEW: Ledger-specific models
class TransactionResponse(BaseModel):
    """Response model for ledger transactions."""
    transaction_id: str
    certificate_number: str
    block_number: int
    hash: str
    timestamp: datetime
    transaction_type: str

class LedgerIntegrityResponse(BaseModel):
    """Response model for ledger integrity checks."""
    is_valid: bool
    total_entries: int
    unique_certificates: int
    transaction_types: Dict[str, int]
    last_block_number: int
    last_hash: str

class CertificateHistoryResponse(BaseModel):
    """Response model for certificate history."""
    certificate_number: str
    total_transactions: int
    history: List[Dict[str, Any]]

# ✅ NEW: Statistics models
class DatabaseStatistics(BaseModel):
    """Statistics about the certificate database."""
    total_certificates: int
    total_verifications: int
    status_distribution: Dict[str, int]
    database_size_bytes: int
    unique_certificates: int
    
class VerificationStatistics(BaseModel):
    """Statistics about verification attempts."""
    total_verifications: int
    successful_verifications: int
    failed_verifications: int
    success_rate: float
    average_confidence: float
    
# ✅ NEW: User models (for future authentication)
class UserBase(BaseModel):
    email: str
    full_name: str
    is_admin: bool = False

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    created_at: datetime
    last_login: Optional[datetime] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# ✅ NEW: Export/Import models
class ExportRequest(BaseModel):
    format: str = Field(default="json", pattern=r"^(json|csv)$")  # ✅ Fixed: changed regex to pattern
    include_deleted: bool = False
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status_filter: Optional[List[str]] = None

class ImportResult(BaseModel):
    total_processed: int
    successful: int
    failed: int
    errors: List[str]
    processing_time: float

# ✅ NEW: Advanced verification models
class AdvancedVerificationRequest(BaseModel):
    """Request for advanced verification with multiple options."""
    expected_hash: Optional[str] = None
    use_enhanced_extraction: bool = True
    check_database: bool = True
    verify_against_blockchain: bool = False
    require_biometric_match: bool = False
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    
class VerificationContext(BaseModel):
    """Additional context for verification attempts."""
    user_id: Optional[str] = None
    verification_reason: Optional[str] = None
    location: Optional[str] = None
    device_info: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class DetailedVerificationResult(VerificationResult):
    """Extended verification result with additional details."""
    processing_time: float
    extraction_quality: Optional[float] = None
    hash_entropy: Optional[int] = None
    ocr_confidence: Optional[float] = None
    image_quality_score: Optional[float] = None
    verification_context: Optional[VerificationContext] = None