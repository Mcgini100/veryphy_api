from fastapi import APIRouter
from datetime import datetime
import os
import cv2
import pytesseract

from app.models import HealthResponse
from app.config import settings

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health status of the API and its dependencies."""
    services = {}
    
    # Check database
    try:
        db_path = os.path.join(settings.database_dir, settings.database_file)
        services['database'] = os.path.exists(db_path)
    except:
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
    
    overall_status = "healthy" if all(services.values()) else "degraded"
    
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
        "docs": f"{settings.api_prefix}/docs"
    }