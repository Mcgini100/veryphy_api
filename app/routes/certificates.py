from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Form
from fastapi.responses import FileResponse
from fastapi import BackgroundTasks
import tempfile
from typing import Optional, List
import os
import shutil
from datetime import datetime
import logging

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

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload")
async def upload_certificate(
    file: UploadFile = File(...),
    embed_hash: bool = Form(True),
    add_watermark: bool = Form(False),
    watermark_text: Optional[str] = Form(None),
    use_checksum: bool = Form(True)
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
        
        # Extract certificate data using OCR to get certificate number
        try:
            from app.services.ocr_service import OCRService
            ocr_service = OCRService()
            certificate_data = await ocr_service.extract_certificate_data(file_path)
            certificate_number = certificate_data.get('Certificate Number')
            
            # If no certificate number found, generate one
            if not certificate_number:
                certificate_number = f"CERT-{timestamp}"
        except Exception as ocr_error:
            print(f"OCR extraction failed: {ocr_error}")
            certificate_number = f"CERT-{timestamp}"
            certificate_data = {}
        
        # Process based on options
        processed_path = file_path
        processed_filename = None
        
        if embed_hash:
            processed_filename = f"embedded_{filename}"
            output_path = os.path.join(settings.processed_dir, processed_filename)
            
            processed_path = await hash_service.embed_hash_on_certificate(
                file_path, 
                certificate_hash, 
                output_path,
                use_checksum=use_checksum
            )
            
            print(f"Hash embedded into certificate: {processed_filename}")
        
        if add_watermark and watermark_text:
            watermark_filename = f"watermarked_{processed_filename or filename}"
            watermark_path = os.path.join(settings.processed_dir, watermark_filename)
            
            processed_path = await watermark_service.add_visible_watermark(
                processed_path,
                watermark_path,
                watermark_text
            )
            processed_filename = watermark_filename
        
        # Store certificate in database
        certificate_db_data = {
            'certificate_number': certificate_number,
            'certificate_data': certificate_data or {},
            'hash': certificate_hash,
            'verification_status': 'UPLOADED',
            'confidence': 1.0,
            'source_image': filename,
            'processed_filename': processed_filename,
            'processed': embed_hash or add_watermark,
            'created_at': datetime.now().isoformat(),
            'processing_options': {
                'embed_hash': embed_hash,
                'add_watermark': add_watermark,
                'watermark_text': watermark_text,
                'use_checksum': use_checksum
            }
        }
        
        # Save to database
        await db.add_certificate(certificate_number, certificate_db_data)
        
        print(f"Certificate saved to database: {certificate_number}")
        
        return {
            "message": "Certificate uploaded successfully",
            "certificate_number": certificate_number,  # Include certificate number
            "filename": filename,
            "hash": certificate_hash,
            "processed": embed_hash or add_watermark,
            "processed_filename": processed_filename,
            "certificate_data": certificate_data
        }
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(file_path):
            os.remove(file_path)
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[CertificateResponse])
async def list_certificates(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    sortBy: Optional[str] = Query("created_at"),
    sortOrder: Optional[str] = Query("desc"),
    minConfidence: Optional[float] = Query(0.0),
    maxConfidence: Optional[float] = Query(1.0)
):
    """List all certificates or search for specific ones."""
    try:
        if search:
            certificates = await db.search_certificates(search)
        else:
            certificates = await db.get_all_certificates(limit=limit, offset=offset)
        
        # Convert string dates to datetime objects for proper handling
        def safe_datetime_parse(date_str):
            if isinstance(date_str, str):
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    return datetime.now()
            return date_str or datetime.now()
        
        return [
            CertificateResponse(
                certificate_number=cert.get('certificate_number', cert.get('Certificate Number', 'UNKNOWN')),
                certificate_data=cert,
                hash=cert.get('hash', ''),
                verification_status=cert.get('verification_status', 'UNKNOWN'),
                confidence=cert.get('confidence', 0),
                source_image=cert.get('source_image'),
                created_at=safe_datetime_parse(cert.get('created_at')),
                last_verified=safe_datetime_parse(cert.get('last_verified')) if cert.get('last_verified') else None
            )
            for cert in certificates
        ]
    except Exception as e:
        logger.error(f"Error in list_certificates: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving certificates: {str(e)}")

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
    
    # Embed hash
    output_filename = f"embedded_{certificate_number}_{source_image}"
    output_path = os.path.join(settings.processed_dir, output_filename)
    
    try:
        certificate_hash = certificate.get('hash')
        if not certificate_hash:
            # Generate new hash if not exists
            certificate_hash = hash_service.generate_certificate_hash(source_path)
            await db.update_certificate(certificate_number, {
                'hash': certificate_hash
            })
        
        await hash_service.embed_hash_on_certificate(
            source_path,
            certificate_hash,
            output_path,
            use_checksum=request.use_checksum
        )
        
        # Update database with processed filename
        await db.update_certificate(certificate_number, {
            'processed_filename': output_filename,
            'processed': True
        })
        
        return {
            "message": "Hash embedded successfully",
            "certificate_number": certificate_number,
            "hash": certificate_hash,
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
        
        # Update database with processed filename
        await db.update_certificate(certificate_number, {
            'processed_filename': output_filename,
            'processed': True
        })
        
        return {
            "message": "Watermark added successfully",
            "certificate_number": certificate_number,
            "output_filename": output_filename,
            "watermark_text": request.text,
            "pattern": request.pattern
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# app/routes/certificates.py - Fixed download endpoint
# app/routes/certificates.py - SIMPLE FIX

@router.get("/{certificate_number}/download/processed")
async def download_processed_certificate(
    certificate_number: str,
    include_markers: bool = Query(True, description="Include visual markers"),
    format: str = Query("png", description="Output format")
):
    """Download the processed certificate with visual markers."""
    print(f"Download processed request for: {certificate_number}, format: {format}")
    
    certificate = await db.get_certificate(certificate_number)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    # First check if we have a processed file
    processed_filename = certificate.get('processed_filename')
    if processed_filename:
        processed_path = os.path.join(settings.processed_dir, processed_filename)
        if os.path.exists(processed_path):
            print(f"Serving existing processed file: {processed_path}")
            
            # ✅ SIMPLE FIX: Always serve as PNG with correct headers
            return FileResponse(
                processed_path,
                media_type="image/png",  # ✅ Fixed: Always PNG
                filename=f"{certificate_number}_with_markers.png",  # ✅ Fixed: Always PNG extension
                headers={"Content-Disposition": f"attachment; filename={certificate_number}_with_markers.png"}
            )
    
    # If no processed file exists, create one
    source_image = certificate.get('source_image')
    if not source_image:
        raise HTTPException(status_code=400, detail="No source image found")
    
    source_path = os.path.join(settings.upload_dir, source_image)
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source image not found")
    
    try:
        print(f"Creating processed version for: {certificate_number}")
        
        # Get hash
        cert_hash = certificate.get('hash')
        if not cert_hash:
            cert_hash = hash_service.generate_certificate_hash(source_path)
        
        # ✅ FIXED: Always create as PNG with .png extension
        base_name = os.path.splitext(source_image)[0]
        processed_filename = f"embedded_{base_name}.png"
        processed_path = os.path.join(settings.processed_dir, processed_filename)
        
        # Use your existing embed_hash_on_certificate function (already creates PNG)
        await hash_service.embed_hash_on_certificate(
            source_path,
            cert_hash,
            processed_path,
            use_checksum=certificate.get('processing_options', {}).get('use_checksum', True)
        )
        
        # Update database
        await db.update_certificate(certificate_number, {
            'processed_filename': processed_filename,
            'hash': cert_hash,
            'processed': True
        })
        
        print(f"Created and saved processed file: {processed_path}")
        
        # ✅ FIXED: Always serve as PNG with correct headers
        return FileResponse(
            processed_path,
            media_type="image/png",  # ✅ Fixed: Always PNG
            filename=f"{certificate_number}_with_markers.png",  # ✅ Fixed: Always PNG extension
            headers={"Content-Disposition": f"attachment; filename={certificate_number}_with_markers.png"}
        )
        
    except Exception as e:
        print(f"Error creating processed version: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate processed version: {str(e)}")


# ✅ ALSO FIX: Original download endpoint
@router.get("/{certificate_number}/download/original")
async def download_original_certificate(
    certificate_number: str,
    format: str = Query("png", description="Output format")  # Keep parameter for API compatibility
):
    """Download the original certificate."""
    print(f"Download original request for: {certificate_number}")
    
    certificate = await db.get_certificate(certificate_number)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    source_image = certificate.get('source_image')
    if not source_image:
        raise HTTPException(status_code=400, detail="No source image found")
    
    source_path = os.path.join(settings.upload_dir, source_image)
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source image not found")
    
    # ✅ FIXED: Determine actual file type and serve correctly
    file_extension = os.path.splitext(source_image)[1].lower()
    
    if file_extension == '.png':
        media_type = "image/png"
        filename = f"{certificate_number}_original.png"
    elif file_extension in ['.jpg', '.jpeg']:
        media_type = "image/jpeg"
        filename = f"{certificate_number}_original.jpg"
    elif file_extension == '.pdf':
        media_type = "application/pdf"
        filename = f"{certificate_number}_original.pdf"
    else:
        # Default to PNG for unknown types
        media_type = "image/png"
        filename = f"{certificate_number}_original.png"
    
    return FileResponse(
        source_path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/stats/summary")
async def get_statistics():
    """Get certificate database statistics."""
    stats = await db.get_statistics()
    return stats