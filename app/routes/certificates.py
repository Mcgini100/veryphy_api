from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form
from typing import Optional, List
import os
import shutil
from datetime import datetime

from app.models import (
    CertificateResponse, 
    CertificateCreate,
    ProcessingOptions,
    HashEmbedRequest,
    WatermarkRequest,
    ErrorResponse
)
from app.database import db
from app.config import settings
from app.services.hash_service import hash_service
from app.services.watermark_service import watermark_service
from app.utils.validators import validate_file

router = APIRouter()

@router.post("/upload")
async def upload_certificate(
    file: UploadFile = File(...),
    embed_hash: bool = Form(True),
    add_watermark: bool = Form(False),
    watermark_text: Optional[str] = Form(None)
):
    """Upload a certificate image for processing."""
    # Validate file
    validation_error = validate_file(file)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)
    
    # Create unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, filename)
    
    try:
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Generate hash
        certificate_hash = hash_service.generate_certificate_hash(file_path)
        
        # Process based on options
        processed_path = file_path
        
        if embed_hash:
            output_path = os.path.join(
                settings.processed_dir, 
                f"embedded_{filename}"
            )
            processed_path = await hash_service.embed_hash_on_certificate(
                file_path, 
                certificate_hash, 
                output_path,
                use_checksum=settings.use_checksum
            )
        
        if add_watermark and watermark_text:
            output_path = os.path.join(
                settings.processed_dir, 
                f"watermarked_{filename}"
            )
            processed_path = await watermark_service.add_visible_watermark(
                processed_path,
                output_path,
                watermark_text
            )
        
        return {
            "message": "Certificate uploaded successfully",
            "filename": filename,
            "hash": certificate_hash,
            "processed": embed_hash or add_watermark,
            "processed_filename": os.path.basename(processed_path) if processed_path != file_path else None
        }
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[CertificateResponse])
async def list_certificates(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None
):
    """List all certificates or search for specific ones."""
    if search:
        certificates = await db.search_certificates(search)
    else:
        certificates = await db.get_all_certificates(limit=limit, offset=offset)
    
    return [
        CertificateResponse(
            certificate_number=cert.get('certificate_number', cert.get('Certificate Number')),
            certificate_data=cert,
            hash=cert.get('hash', ''),
            verification_status=cert.get('verification_status', 'UNKNOWN'),
            confidence=cert.get('confidence', 0),
            source_image=cert.get('source_image'),
            created_at=cert.get('created_at', datetime.now()),
            last_verified=cert.get('last_verified')
        )
        for cert in certificates
    ]

@router.get("/{certificate_number}", response_model=CertificateResponse)
async def get_certificate(certificate_number: str):
    """Get a specific certificate by its number."""
    certificate = await db.get_certificate(certificate_number)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    return CertificateResponse(
        certificate_number=certificate_number,
        certificate_data=certificate,
        hash=certificate.get('hash', ''),
        verification_status=certificate.get('verification_status', 'UNKNOWN'),
        confidence=certificate.get('confidence', 0),
        source_image=certificate.get('source_image'),
        created_at=certificate.get('created_at', datetime.now()),
        last_verified=certificate.get('last_verified')
    )

@router.delete("/{certificate_number}")
async def delete_certificate(certificate_number: str):
    """Delete a certificate from the database."""
    success = await db.delete_certificate(certificate_number)
    if not success:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    return {"message": f"Certificate {certificate_number} deleted successfully"}

@router.get("/{certificate_number}/history")
async def get_verification_history(
    certificate_number: str,
    limit: Optional[int] = Query(None, ge=1, le=100)
):
    """Get verification history for a certificate."""
    history = await db.get_verification_history(certificate_number, limit=limit)
    if not history:
        raise HTTPException(
            status_code=404, 
            detail="Certificate not found or no verification history"
        )
    
    return {
        "certificate_number": certificate_number,
        "history": history,
        "total_verifications": len(history)
    }

@router.post("/{certificate_number}/embed-hash")
async def embed_hash_in_certificate(
    certificate_number: str,
    request: HashEmbedRequest = HashEmbedRequest()
):
    """Embed hash into an existing certificate image."""
    certificate = await db.get_certificate(certificate_number)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    # Find the source image
    source_image = certificate.get('source_image')
    if not source_image:
        raise HTTPException(status_code=400, detail="No source image found for certificate")
    
    source_path = os.path.join(settings.upload_dir, source_image)
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source image file not found")
    
    # Determine hash to use
    hash_value = request.hash_value
    if not hash_value:
        if certificate.get('hash'):
            hash_value = certificate['hash']
        elif request.generate_if_missing:
            hash_value = hash_service.generate_certificate_hash(source_path)
        else:
            raise HTTPException(status_code=400, detail="No hash provided or found")
    
    # Embed hash
    output_filename = f"embedded_{certificate_number}_{source_image}"
    output_path = os.path.join(settings.processed_dir, output_filename)
    
    try:
        await hash_service.embed_hash_on_certificate(
            source_path,
            hash_value,
            output_path,
            use_checksum=request.use_checksum
        )
        
        return {
            "message": "Hash embedded successfully",
            "certificate_number": certificate_number,
            "hash": hash_value,
            "output_filename": output_filename,
            "use_checksum": request.use_checksum
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{certificate_number}/watermark")
async def add_watermark_to_certificate(
    certificate_number: str,
    request: WatermarkRequest
):
    """Add watermark to an existing certificate image."""
    certificate = await db.get_certificate(certificate_number)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    # Find the source image
    source_image = certificate.get('source_image')
    if not source_image:
        raise HTTPException(status_code=400, detail="No source image found for certificate")
    
    source_path = os.path.join(settings.upload_dir, source_image)
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source image file not found")
    
    # Add watermark
    output_filename = f"watermarked_{certificate_number}_{source_image}"
    output_path = os.path.join(settings.processed_dir, output_filename)
    
    try:
        await watermark_service.add_visible_watermark(
            source_path,
            output_path,
            request.text,
            pattern=request.pattern,
            opacity=request.opacity,
            font_size=request.font_size
        )
        
        return {
            "message": "Watermark added successfully",
            "certificate_number": certificate_number,
            "output_filename": output_filename,
            "watermark_text": request.text,
            "pattern": request.pattern
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/summary")
async def get_statistics():
    """Get certificate database statistics."""
    stats = await db.get_statistics()
    return stats