from fastapi import APIRouter
from datetime import datetime
import os
import cv2
import pytesseract

from app.models import HealthResponse
from app.config import settings
from app.database import CertificateDatabase

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health status of the API and its dependencies."""
    services = {}
    
    # Check immutable ledger database
    try:
        db = CertificateDatabase()
        # Validate ledger integrity
        integrity_result = await db.validate_integrity()
        services['database'] = integrity_result['is_valid']
        # Note: Don't add ledger_entries and unique_certificates here since HealthResponse expects only booleans
    except Exception as e:
        services['database'] = False
    
    # Check Tesseract
    try:
        pytesseract.get_tesseract_version()
        services['tesseract'] = True
    except:
        services['tesseract'] = False
    
    # Check OpenCV
    try:
        cv2.__version__
        services['opencv'] = True
    except:
        services['opencv'] = False
    
    # Check file storage
    try:
        services['storage'] = all([
            os.path.exists(settings.upload_dir),
            os.path.exists(settings.processed_dir),
            os.path.exists(settings.database_dir)
        ])
    except:
        services['storage'] = False
    
    # Check ledger file specifically
    try:
        ledger_path = os.path.join(settings.database_dir, "certificate_ledger.json")
        services['ledger_file'] = os.path.exists(ledger_path)
    except:
        services['ledger_file'] = False
    
    overall_status = "healthy" if all([
        services.get('database', False),
        services.get('tesseract', False),
        services.get('opencv', False),
        services.get('storage', False)
    ]) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version=settings.app_version,
        timestamp=datetime.now(),
        services=services
    )

@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": f"{settings.api_prefix}/docs",
        "storage_type": "immutable_ledger"
    }

@router.get("/ledger/integrity")
async def check_ledger_integrity():
    """Check the integrity of the immutable ledger."""
    try:
        db = CertificateDatabase()
        integrity_result = await db.validate_integrity()
        return {
            "status": "success",
            "integrity": integrity_result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/ledger/stats")
async def get_ledger_stats():
    """Get statistics about the immutable ledger."""
    try:
        db = CertificateDatabase()
        integrity_result = await db.validate_integrity()
        
        # Get additional stats
        certificates = await db.list_certificates(limit=1000)  # Get all for stats
        
        active_count = 0
        deleted_count = 0
        
        for cert in certificates['certificates']:
            if cert['data'].get('deleted', False):
                deleted_count += 1
            else:
                active_count += 1
        
        return {
            "status": "success",
            "stats": {
                "total_entries": integrity_result['total_entries'],
                "unique_certificates": integrity_result['unique_certificates'],
                "active_certificates": active_count,
                "deleted_certificates": deleted_count,
                "transaction_types": integrity_result['transaction_types'],
                "last_block_number": integrity_result['last_block_number'],
                "last_hash": integrity_result['last_hash']
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }