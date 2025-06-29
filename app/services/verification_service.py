import os
from typing import Dict, Optional, Any, Tuple
from datetime import datetime

from app.config import settings
from app.models import VerificationStatus, CertificateData
from app.database import db
from app.services.hash_service import hash_service
from app.services.ocr_service import ocr_service

class VerificationService:
    """Main service for certificate verification operations."""
    
    async def verify_certificate(
        self,
        image_path: str,
        expected_hash: Optional[str] = None,
        use_enhanced: bool = True,
        check_database: bool = True
    ) -> Dict[str, Any]:
        """Process certificate: verify hash first, fallback to OCR if needed."""
        print(f"\n{'='*60}")
        print(f"Processing certificate: {image_path}")
        print(f"{'='*60}")
        
        result = {
            'image_path': image_path,
            'verification_status': VerificationStatus.UNKNOWN,
            'extraction_method': None,
            'certificate_data': {},
            'hash': None,
            'confidence': 0,
            'similarity_score': None,
            'message': ''
        }
        
        # Step 1: Try to extract embedded hash
        print("\n[STEP 1] Attempting hash extraction...")
        
        if use_enhanced:
            extracted_hash, confidence = await hash_service.extract_hash_enhanced(image_path)
            result['confidence'] = confidence
        else:
            extracted_hash = await hash_service.extract_hash_from_certificate(image_path)
            result['confidence'] = 1.0 if extracted_hash else 0
        
        if extracted_hash:
            # Check for obvious corruption
            unique_chars = len(set(extracted_hash))
            if unique_chars < settings.min_entropy_threshold:
                print(f"[WARNING] Extracted hash appears corrupted (only {unique_chars} unique characters)")
                result['verification_status'] = VerificationStatus.CORRUPTED_HASH
                result['message'] = f"Hash appears corrupted with low entropy ({unique_chars} unique characters)"
            else:
                print(f"Extracted hash: {extracted_hash}")
                print(f"Confidence: {result['confidence']:.2%}")
                result['hash'] = extracted_hash
                
                # Check if hash matches expected hash
                if expected_hash:
                    if extracted_hash == expected_hash:
                        print("[SUCCESS] Hash verification PASSED!")
                        result['verification_status'] = VerificationStatus.VERIFIED
                        result['message'] = "Certificate verified successfully via hash"
                    else:
                        # Calculate similarity
                        similarity = hash_service.calculate_hash_similarity(extracted_hash, expected_hash)
                        result['similarity_score'] = similarity
                        print(f"[WARNING] Hash verification FAILED! Similarity: {similarity:.2%}")
                        result['verification_status'] = VerificationStatus.FAILED
                        result['message'] = f"Hash verification failed with {similarity:.2%} similarity"
                else:
                    # No expected hash provided - will check against database after OCR
                    print("[INFO] No expected hash provided, will check against database after OCR...")
                    result['verification_status'] = VerificationStatus.UNKNOWN
                    result['message'] = "Hash extracted, checking against database..."
        else:
            print("[WARNING] Could not extract hash from certificate.")
            result['verification_status'] = VerificationStatus.NO_HASH
            result['message'] = "No embedded hash found in certificate"
        
        # Step 2: Extract certificate data using OCR
        print("\n[STEP 2] Extracting certificate data using OCR...")
        cert_data = await ocr_service.extract_certificate_data(image_path)
        
        if cert_data and cert_data.get('Certificate Number'):
            result['certificate_data'] = cert_data
            result['extraction_method'] = 'OCR'
            cert_number = cert_data.get('Certificate Number')
            
            # Check database for certificate and hash verification
            if check_database and cert_number:
                stored_cert = await db.get_certificate(cert_number)
                
                if stored_cert:
                    print(f"[INFO] Found certificate in database: {cert_number}")
                    
                    # If we have an extracted hash but status is still UNKNOWN, verify against database
                    if result['hash'] and result['verification_status'] == VerificationStatus.UNKNOWN:
                        stored_hash = stored_cert.get('hash')
                        if stored_hash:
                            print(f"Comparing extracted hash with stored hash...")
                            print(f"Extracted: {result['hash']}")
                            print(f"Stored:    {stored_hash}")
                            
                            if result['hash'] == stored_hash:
                                print("[SUCCESS] Hash verification PASSED against database!")
                                result['verification_status'] = VerificationStatus.VERIFIED
                                result['message'] = "Certificate verified successfully via database hash"
                            else:
                                similarity = hash_service.calculate_hash_similarity(result['hash'], stored_hash)
                                result['similarity_score'] = similarity
                                print(f"[WARNING] Hash verification FAILED against database! Similarity: {similarity:.2%}")
                                result['verification_status'] = VerificationStatus.FAILED
                                result['message'] = f"Hash verification failed with {similarity:.2%} similarity"
                        else:
                            print("[INFO] No hash found in database record")
                    
                    # Additional verification through data matching for failed cases
                    if result['verification_status'] in [
                        VerificationStatus.FAILED, 
                        VerificationStatus.CORRUPTED_HASH, 
                        VerificationStatus.NO_HASH,
                        VerificationStatus.UNKNOWN
                    ]:
                        # Compare key fields
                        match_result = await self._compare_certificate_data(cert_data, stored_cert)
                        
                        if match_result['match_score'] >= settings.data_match_threshold:
                            print(f"[INFO] Certificate data matches database record ({match_result['match_score']:.0%} field match)")
                            result['verification_status'] = VerificationStatus.VERIFIED_BY_DATA
                            result['confidence'] = match_result['match_score']
                            result['message'] = f"Certificate verified by data matching ({match_result['match_score']:.0%} match)"
                            
                            # If we have a stored hash and no extracted hash, use the stored one
                            if not result['hash'] and 'hash' in stored_cert:
                                result['hash'] = stored_cert['hash']
                else:
                    print(f"[WARNING] Certificate {cert_number} not found in database")
                    # If no expected hash was provided and certificate not in database
                    if not expected_hash and result['verification_status'] == VerificationStatus.UNKNOWN:
                        result['verification_status'] = VerificationStatus.UNKNOWN
                        result['message'] = "Certificate not found in database for verification"
            
            # Generate hash if not extracted and not found in database
            if not result['hash']:
                result['hash'] = hash_service.generate_certificate_hash(image_path)
                print(f"Generated new hash: {result['hash']}")
            
            # Store in database (this will update existing records or create new ones)
            await self._store_certificate_data(cert_data, result)
            
        else:
            print("[ERROR] Failed to extract certificate data using OCR.")
            # If we had a hash but no OCR data, we can't verify against database
            if result['hash'] and result['verification_status'] == VerificationStatus.UNKNOWN:
                result['verification_status'] = VerificationStatus.UNKNOWN
                result['message'] = "Hash extracted but no certificate data found for database verification"
            elif not result['hash']:
                result['verification_status'] = VerificationStatus.NO_HASH
                result['message'] = "Failed to extract certificate data via OCR"
        
        # Final status check - ensure we don't leave status as UNKNOWN if we have useful information
        if result['verification_status'] == VerificationStatus.UNKNOWN:
            if result['hash']:
                # We have a hash but couldn't verify it - this is actually a limitation, not a failure
                result['verification_status'] = VerificationStatus.UNKNOWN
                result['message'] = "Hash extracted but could not be verified without database record"
            else:
                result['verification_status'] = VerificationStatus.NO_HASH
                result['message'] = "No hash found and no certificate data extracted"
        
        print(f"\n[FINAL RESULT] Status: {result['verification_status']}")
        print(f"[FINAL RESULT] Message: {result['message']}")
        print(f"{'='*60}\n")
        
        return result
    
    async def _compare_certificate_data(
        self,
        extracted_data: Dict[str, Any],
        stored_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare extracted certificate data with stored data."""
        matching_fields = 0
        total_fields = 0
        field_matches = {}
        
        comparison_fields = [
            'Student Name', 
            'Degree Name', 
            'Date', 
            'Faculty Name',
            'Degree Classification'
        ]
        
        print(f"\n[DATA COMPARISON] Comparing certificate data...")
        for field in comparison_fields:
            if field in stored_data and field in extracted_data:
                total_fields += 1
                stored_value = str(stored_data[field]).strip().lower() if stored_data[field] else ""
                extracted_value = str(extracted_data[field]).strip().lower() if extracted_data[field] else ""
                
                print(f"  {field}:")
                print(f"    Stored:    '{stored_value}'")
                print(f"    Extracted: '{extracted_value}'")
                
                if stored_value == extracted_value:
                    matching_fields += 1
                    field_matches[field] = True
                    print(f"    ✅ MATCH")
                else:
                    field_matches[field] = False
                    print(f"    ❌ NO MATCH")
        
        match_score = matching_fields / total_fields if total_fields > 0 else 0
        print(f"\n[DATA COMPARISON] Overall match: {matching_fields}/{total_fields} ({match_score:.1%})")
        
        return {
            'match_score': match_score,
            'matching_fields': matching_fields,
            'total_fields': total_fields,
            'field_matches': field_matches
        }
    
    async def _store_certificate_data(
        self,
        cert_data: Dict[str, Any],
        verification_result: Dict[str, Any]
    ):
        """Store certificate data and verification result in database."""
        cert_number = cert_data.get('Certificate Number')
        if not cert_number:
            return
        
        # Prepare data for storage
        storage_data = {
            **cert_data,
            'hash': verification_result.get('hash'),
            'verification_status': verification_result['verification_status'].value,
            'confidence': verification_result.get('confidence', 0),
            'source_image': os.path.basename(verification_result['image_path'])
        }
        
        # Store certificate
        await db.add_certificate(cert_number, storage_data)
        
        # Add verification record
        await db.add_verification_record(cert_number, {
            'status': verification_result['verification_status'].value,
            'confidence': verification_result.get('confidence', 0),
            'source': os.path.basename(verification_result['image_path']),
            'similarity_score': verification_result.get('similarity_score'),
            'message': verification_result.get('message', '')
        })
        
        print(f"\n[SUCCESS] Certificate data stored in database with ID: {cert_number}")

# Global service instance
verification_service = VerificationService()