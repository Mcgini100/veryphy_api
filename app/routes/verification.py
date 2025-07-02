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
            message=result.get('message', ''),
            certificate_exists_in_ledger=result.get('certificate_exists_in_ledger', False)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/batch")
async def verify_certificates_batch(
    files: List[UploadFile] = File(...),
    use_enhanced_extraction: bool = Form(True),
    check_database: bool = Form(True),
    continue_on_error: bool = Form(True)
):
    """Verify multiple certificates in batch."""
    
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > 10:  # Limit batch size
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed per batch")
    
    print(f"\n🔄 Starting batch verification of {len(files)} files...")
    
    start_time = time.time()
    results = []
    successful = 0
    failed = 0
    
    for i, file in enumerate(files):
        print(f"\n📁 Processing file {i+1}/{len(files)}: {file.filename}")
        
        try:
            # Validate file
            validation_error = validate_file(file)
            if validation_error:
                print(f"❌ Validation failed: {validation_error}")
                if continue_on_error:
                    failed += 1
                    results.append({
                        "filename": file.filename,
                        "verification_status": "ERROR",
                        "confidence": 0,
                        "message": f"Validation error: {validation_error}",
                        "hash": None,
                        "certificate_data": None,
                        "extraction_method": None,
                        "similarity_score": None
                    })
                    continue
                else:
                    raise HTTPException(status_code=400, detail=f"File {file.filename}: {validation_error}")
            
            # Save temporary file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_filename = f"batch_{timestamp}_{i}_{file.filename}"
            temp_path = os.path.join(settings.upload_dir, temp_filename)
            
            try:
                # Save file
                with open(temp_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                print(f"💾 File saved to: {temp_path}")
                
                # Perform verification
                result = await verification_service.verify_certificate(
                    temp_path,
                    expected_hash=None,
                    use_enhanced=use_enhanced_extraction,
                    check_database=check_database
                )
                
                print(f"✅ Verification completed: {result['verification_status']}")
                
                # Format result for response
                verification_result = {
                    "filename": file.filename,
                    "verification_status": result['verification_status'].value if hasattr(result['verification_status'], 'value') else result['verification_status'],
                    "confidence": result['confidence'],
                    "hash": result.get('hash'),
                    "message": result.get('message', ''),
                    "certificate_data": result.get('certificate_data', {}),
                    "extraction_method": result.get('extraction_method'),
                    "similarity_score": result.get('similarity_score'),
                    "certificate_exists_in_ledger": result.get('certificate_exists_in_ledger', False)
                }
                
                results.append(verification_result)
                
                # Count success/failure
                if result['verification_status'] in ['VERIFIED', 'VERIFIED_BY_DATA'] or result.get('certificate_exists_in_ledger'):
                    successful += 1
                    print(f"✅ File {file.filename}: SUCCESS")
                else:
                    failed += 1
                    print(f"❌ File {file.filename}: FAILED")
                    
            except Exception as verification_error:
                print(f"❌ Verification error: {str(verification_error)}")
                if continue_on_error:
                    failed += 1
                    results.append({
                        "filename": file.filename,
                        "verification_status": "ERROR",
                        "confidence": 0,
                        "message": f"Verification error: {str(verification_error)}",
                        "hash": None,
                        "certificate_data": None,
                        "extraction_method": None,
                        "similarity_score": None
                    })
                else:
                    raise HTTPException(status_code=500, detail=f"File {file.filename}: {str(verification_error)}")
                    
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    print(f"🗑️  Cleaned up: {temp_path}")
                    
        except Exception as e:
            print(f"❌ File processing error: {str(e)}")
            if continue_on_error:
                failed += 1
                results.append({
                    "filename": file.filename,
                    "verification_status": "ERROR",
                    "confidence": 0,
                    "message": f"Processing error: {str(e)}",
                    "hash": None,
                    "certificate_data": None,
                    "extraction_method": None,
                    "similarity_score": None
                })
            else:
                raise HTTPException(status_code=500, detail=f"File {file.filename}: {str(e)}")
    
    processing_time = time.time() - start_time
    
    print(f"\n🎉 Batch verification completed!")
    print(f"📊 Results: {successful} successful, {failed} failed")
    print(f"⏱️  Processing time: {processing_time:.2f}s")
    
    return {
        "total_processed": len(files),
        "successful": successful,
        "failed": failed,
        "results": results,
        "processing_time": processing_time,
        "message": f"Batch verification completed: {successful}/{len(files)} successful"
    }

@router.post("/by-hash")
async def verify_by_hash(
    certificate_number: str = Form(...),
    provided_hash: str = Form(...)
):
    """Verify a certificate by comparing hash with database."""
    from app.database import db
    
    try:
        # Get certificate from database
        certificate = await db.get_certificate(certificate_number)
        if not certificate:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        # Get stored hash
        stored_hash = certificate.get('hash')
        if not stored_hash:
            return {
                "verified": False,
                "message": "No hash found in database record",
                "certificate_number": certificate_number
            }
        
        # Compare hashes
        is_match = stored_hash.strip().lower() == provided_hash.strip().lower()
        
        if is_match:
            return {
                "verified": True,
                "message": "Certificate hash matches database record",
                "certificate_number": certificate_number
            }
        else:
            return {
                "verified": False,
                "message": "Certificate hash does not match database record",
                "certificate_number": certificate_number
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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