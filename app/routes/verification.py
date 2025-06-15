from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional, List, Dict
import os
import shutil
from datetime import datetime
import time

from app.models import (
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    CertificateData,
    BatchVerificationRequest,
    BatchVerificationResult
)
from app.config import settings
from app.services.verification_service import verification_service
from app.utils.validators import validate_file

router = APIRouter()

@router.post("/", response_model=VerificationResult)
async def verify_certificate(
    file: UploadFile = File(...),
    expected_hash: Optional[str] = Form(None),
    use_enhanced_extraction: bool = Form(True),
    check_database: bool = Form(True)
):
    """Verify a certificate by uploading an image."""
    # Validate file
    validation_error = validate_file(file)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)
    
    # Save temporary file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filename = f"verify_{timestamp}_{file.filename}"
    temp_path = os.path.join(settings.upload_dir, temp_filename)
    
    try:
        # Save uploaded file
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Perform verification
        result = await verification_service.verify_certificate(
            temp_path,
            expected_hash=expected_hash,
            use_enhanced=use_enhanced_extraction,
            check_database=check_database
        )
        
        # Convert to response model
        return VerificationResult(
            verification_status=result['verification_status'],
            confidence=result['confidence'],
            hash=result.get('hash'),
            expected_hash=expected_hash,
            certificate_data=CertificateData(**result['certificate_data']) if result['certificate_data'] else None,
            extraction_method=result.get('extraction_method'),
            similarity_score=result.get('similarity_score'),
            message=result.get('message', '')
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/batch", response_model=BatchVerificationResult)
async def verify_certificates_batch(
    files: List[UploadFile] = File(...),
    request: BatchVerificationRequest = BatchVerificationRequest()
):
    """Verify multiple certificates in batch."""
    start_time = time.time()
    results = []
    successful = 0
    failed = 0
    
    for i, file in enumerate(files):
        try:
            # Validate file
            validation_error = validate_file(file)
            if validation_error:
                if request.continue_on_error:
                    failed += 1
                    results.append(VerificationResult(
                        verification_status=VerificationStatus.UNKNOWN,
                        confidence=0,
                        message=f"Validation error: {validation_error}",
                        certificate_data=None
                    ))
                    continue
                else:
                    raise HTTPException(status_code=400, detail=validation_error)
            
            # Save temporary file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"batch_{timestamp}_{i}_{file.filename}"
            temp_path = os.path.join(settings.upload_dir, temp_filename)
            
            try:
                with open(temp_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # Get expected hash if provided
                expected_hash = None
                if request.expected_hashes and file.filename in request.expected_hashes:
                    expected_hash = request.expected_hashes[file.filename]
                
                # Perform verification
                result = await verification_service.verify_certificate(
                    temp_path,
                    expected_hash=expected_hash,
                    use_enhanced=request.use_enhanced_extraction,
                    check_database=True
                )
                
                # Add to results
                results.append(VerificationResult(
                    verification_status=result['verification_status'],
                    confidence=result['confidence'],
                    hash=result.get('hash'),
                    expected_hash=expected_hash,
                    certificate_data=CertificateData(**result['certificate_data']) if result['certificate_data'] else None,
                    extraction_method=result.get('extraction_method'),
                    similarity_score=result.get('similarity_score'),
                    message=result.get('message', '')
                ))
                
                if result['verification_status'] in [VerificationStatus.VERIFIED, VerificationStatus.VERIFIED_BY_DATA]:
                    successful += 1
                else:
                    failed += 1
                    
            finally:
                # Clean up
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            if request.continue_on_error:
                failed += 1
                results.append(VerificationResult(
                    verification_status=VerificationStatus.UNKNOWN,
                    confidence=0,
                    message=f"Error: {str(e)}",
                    certificate_data=None
                ))
            else:
                raise HTTPException(status_code=500, detail=str(e))
    
    processing_time = time.time() - start_time
    
    return BatchVerificationResult(
        total_processed=len(files),
        successful=successful,
        failed=failed,
        results=results,
        processing_time=processing_time
    )

@router.post("/by-hash")
async def verify_by_hash(
    certificate_number: str = Form(...),
    provided_hash: str = Form(...)
):
    """Verify a certificate by comparing hash with database."""
    from app.database import db
    
    is_valid = await db.verify_certificate_hash(certificate_number, provided_hash)
    
    if is_valid:
        return {
            "verified": True,
            "message": "Certificate hash matches database record",
            "certificate_number": certificate_number
        }
    else:
        certificate = await db.get_certificate(certificate_number)
        if not certificate:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        return {
            "verified": False,
            "message": "Certificate hash does not match database record",
            "certificate_number": certificate_number
        }

@router.post("/extract-hash")
async def extract_hash_from_image(
    file: UploadFile = File(...),
    use_enhanced: bool = Form(True)
):
    """Extract embedded hash from a certificate image."""
    # Validate file
    validation_error = validate_file(file)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)
    
    # Save temporary file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filename = f"extract_{timestamp}_{file.filename}"
    temp_path = os.path.join(settings.upload_dir, temp_filename)
    
    try:
        # Save uploaded file
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract hash
        from app.services.hash_service import hash_service
        
        if use_enhanced:
            extracted_hash, confidence = await hash_service.extract_hash_enhanced(temp_path)
        else:
            extracted_hash = await hash_service.extract_hash_from_certificate(temp_path)
            confidence = 1.0 if extracted_hash else 0
        
        if not extracted_hash:
            raise HTTPException(status_code=404, detail="No hash found in certificate")
        
        # Check entropy
        unique_chars = len(set(extracted_hash))
        is_corrupted = unique_chars < settings.min_entropy_threshold
        
        return {
            "hash": extracted_hash,
            "confidence": confidence,
            "unique_characters": unique_chars,
            "is_corrupted": is_corrupted,
            "message": "Hash appears corrupted due to low entropy" if is_corrupted else "Hash extracted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)