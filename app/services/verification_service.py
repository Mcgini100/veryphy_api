import os
import re
import time
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime, timezone

from app.config import settings
from app.models import VerificationStatus, CertificateData
from app.database import CertificateDatabase
from app.services.hash_service import hash_service
from app.services.ocr_service import ocr_service

class VerificationService:
    """Main service for certificate verification operations with enhanced ledger integration."""
    
    def __init__(self):
        self.db = CertificateDatabase()
    
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
            'message': '',
            'processing_time': None,
            'hash_match': False,
            'data_match': False,
            'certificate_number': None
        }
        
        start_time = time.time()
        
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
                    hash_comparison = self.compare_hashes(extracted_hash, expected_hash)
                    result['similarity_score'] = hash_comparison['similarity']
                    result['hash_match'] = hash_comparison['match']
                    
                    if hash_comparison['match']:
                        print("[SUCCESS] Hash verification PASSED!")
                        result['verification_status'] = VerificationStatus.VERIFIED
                        result['message'] = f"Certificate verified successfully via hash. {hash_comparison['reason']}"
                    else:
                        print(f"[WARNING] Hash verification FAILED! {hash_comparison['reason']}")
                        result['verification_status'] = VerificationStatus.FAILED
                        result['message'] = f"Hash verification failed. {hash_comparison['reason']}"
                else:
                    print("[INFO] No expected hash provided, will check against database after OCR...")
        else:
            print("[WARNING] No hash found in certificate")
            result['verification_status'] = VerificationStatus.NO_HASH
            result['message'] = "No embedded hash found in certificate"
        
        # Step 2: Extract certificate data using OCR
        print("\n[STEP 2] Extracting certificate data using OCR...")
        extracted_data = await ocr_service.extract_certificate_data(image_path)
        result['certificate_data'] = extracted_data
        result['certificate_number'] = extracted_data.get('Certificate Number')
        
        if not extracted_data:
            print("[ERROR] Failed to extract certificate data")
            result['message'] = "Failed to extract certificate data from image"
            result['processing_time'] = f"{(time.time() - start_time):.2f}s"
            return result
        
        # Step 3: Check against database if requested
        if check_database and extracted_hash:
            print("\n[STEP 3] Checking against database...")
            db_result = await self.verify_certificate_against_database(
                extracted_data, extracted_hash, image_path
            )
            
            # Merge database verification results
            result.update(db_result)
            
            # Store verification result in ledger
            await self._store_certificate_data(extracted_data, result)
        
        result['processing_time'] = f"{(time.time() - start_time):.2f}s"
        print(f"\n[COMPLETE] Verification finished in {result['processing_time']}")
        
        return result
    
    def compare_hashes(self, hash1: str, hash2: str, threshold: float = 0.90) -> Dict[str, Any]:
        """Compare two hashes with enhanced similarity calculation."""
        if not hash1 or not hash2:
            return {
                'match': False,
                'similarity': 0.0,
                'reason': 'One or both hashes are empty'
            }
        
        # Normalize hashes (remove whitespace, convert to lowercase)
        hash1_clean = hash1.strip().lower()
        hash2_clean = hash2.strip().lower()
        
        # Exact match check
        if hash1_clean == hash2_clean:
            return {
                'match': True,
                'similarity': 1.0,
                'reason': 'Exact match'
            }
        
        # Check if one hash is a substring of the other (common with extraction variations)
        if hash1_clean in hash2_clean or hash2_clean in hash1_clean:
            longer_hash = max(hash1_clean, hash2_clean, key=len)
            shorter_hash = min(hash1_clean, hash2_clean, key=len)
            similarity = len(shorter_hash) / len(longer_hash)
            
            return {
                'match': similarity >= threshold,
                'similarity': similarity,
                'reason': f'Substring match (similarity: {similarity:.2%})'
            }
        
        # Character-by-character similarity for partial corruption
        min_len = min(len(hash1_clean), len(hash2_clean))
        max_len = max(len(hash1_clean), len(hash2_clean))
        
        if min_len == 0:
            return {
                'match': False,
                'similarity': 0.0,
                'reason': 'Length mismatch'
            }
        
        # Calculate character similarity
        matching_chars = 0
        for i in range(min_len):
            if hash1_clean[i] == hash2_clean[i]:
                matching_chars += 1
        
        similarity = matching_chars / max_len
        
        return {
            'match': similarity >= threshold,
            'similarity': similarity,
            'reason': f'Character similarity: {similarity:.2%} (threshold: {threshold:.2%})'
        }
    
    async def verify_certificate_against_database(
        self,
        extracted_data: Dict[str, Any],
        extracted_hash: str,
        image_path: str
    ) -> Dict[str, Any]:
        """Verify certificate against database with improved hash and data comparison."""
        
        cert_number = extracted_data.get('Certificate Number')
        if not cert_number:
            return {
                'verification_status': VerificationStatus.NO_HASH,
                'message': 'No certificate number found in extracted data',
                'confidence': 0.0,
                'hash_match': False,
                'data_match': False
            }
        
        try:
            # Get certificate from database
            stored_certificate = await self.db.get_certificate(cert_number)
            
            if not stored_certificate:
                return {
                    'verification_status': VerificationStatus.FAILED,
                    'message': f'Certificate {cert_number} not found in database',
                    'confidence': 0.0,
                    'hash_match': False,
                    'data_match': False
                }
            
            stored_hash = stored_certificate.get('hash', '')
            
            print(f"Comparing extracted hash with stored hash...")
            print(f"Extracted: {extracted_hash}")
            print(f"Stored:    {stored_hash}")
            
            # Use improved hash comparison
            hash_comparison = self.compare_hashes(extracted_hash, stored_hash, threshold=0.90)
            
            print(f"Hash comparison result: {hash_comparison}")
            
            # Perform data comparison
            data_comparison = await self._compare_certificate_data(
                stored_certificate, 
                extracted_data
            )
            
            # Determine verification result
            if hash_comparison['match']:
                status = VerificationStatus.VERIFIED
                confidence = hash_comparison['similarity']
                message = f"Certificate verified by hash match. {hash_comparison['reason']}"
            elif data_comparison['match_score'] >= 0.8:  # 80% data match threshold
                status = VerificationStatus.VERIFIED_BY_DATA
                confidence = data_comparison['match_score']
                message = f"Certificate verified by data comparison ({data_comparison['matching_fields']:.1f}/{data_comparison['total_fields']} fields matched)"
            elif hash_comparison['similarity'] >= 0.70:  # Partial hash match
                status = VerificationStatus.VERIFIED_BY_DATA
                confidence = (hash_comparison['similarity'] + data_comparison['match_score']) / 2
                message = f"Certificate verified by partial hash match. {hash_comparison['reason']}"
            else:
                status = VerificationStatus.FAILED
                confidence = max(hash_comparison['similarity'], data_comparison['match_score'])
                message = f"Verification failed. Hash similarity: {hash_comparison['similarity']:.2%}, Data match: {data_comparison['match_score']:.2%}"
            
            # Store verification record in ledger
            verification_record = {
                'status': status.value,
                'confidence': confidence,
                'hash_comparison': hash_comparison,
                'data_comparison': data_comparison,
                'extracted_hash': extracted_hash,
                'stored_hash': stored_hash,
                'source': os.path.basename(image_path),
                'message': message,
                'verified_by': 'verification_service',
                'verification_method': 'hash_and_data_comparison'
            }
            
            await self.db.add_verification_record(cert_number, verification_record)
            
            return {
                'verification_status': status,
                'confidence': confidence,
                'message': message,
                'hash_match': hash_comparison['match'],
                'data_match': data_comparison['match_score'] >= 0.8,
                'hash_similarity': hash_comparison['similarity'],
                'data_similarity': data_comparison['match_score'],
                'certificate_number': cert_number,
                'extracted_hash': extracted_hash,
                'stored_hash': stored_hash,
                'certificate_data': stored_certificate
            }
            
        except Exception as e:
            print(f"Error during database verification: {e}")
            return {
                'verification_status': VerificationStatus.FAILED,
                'message': f'Database verification error: {str(e)}',
                'confidence': 0.0,
                'hash_match': False,
                'data_match': False
            }
    
    async def _compare_certificate_data(
        self,
        stored_data: Dict[str, Any],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhanced certificate data comparison with flexible matching."""
        
        matching_fields = 0
        total_fields = 0
        field_matches = {}
        
        # Enhanced comparison fields with more flexible matching
        comparison_fields = [
            'Student Name', 
            'Degree Name', 
            'Date', 
            'Faculty Name',
            'Degree Classification',
            'Certificate Number',
            'Institution Name',
            'Graduation Date'
        ]
        
        print(f"\n[DATA COMPARISON] Comparing certificate data...")
        
        for field in comparison_fields:
            # Check if field exists in either dataset
            stored_value = stored_data.get(field)
            extracted_value = extracted_data.get(field)
            
            # Skip if both values are None/empty
            if not stored_value and not extracted_value:
                continue
                
            total_fields += 1
            
            # Normalize values for comparison
            stored_str = str(stored_value).strip().lower() if stored_value else ""
            extracted_str = str(extracted_value).strip().lower() if extracted_value else ""
            
            print(f"  {field}:")
            print(f"    Stored:    '{stored_str}'")
            print(f"    Extracted: '{extracted_str}'")
            
            # Exact match
            if stored_str == extracted_str:
                matching_fields += 1
                field_matches[field] = True
                print(f"    ✅ EXACT MATCH")
            # Partial match for names and text fields
            elif field in ['Student Name', 'Faculty Name', 'Institution Name']:
                similarity = self._calculate_text_similarity(stored_str, extracted_str)
                if similarity >= 0.8:  # 80% similarity threshold
                    matching_fields += similarity  # Partial credit
                    field_matches[field] = True
                    print(f"    ✅ PARTIAL MATCH (similarity: {similarity:.2%})")
                else:
                    field_matches[field] = False
                    print(f"    ❌ NO MATCH (similarity: {similarity:.2%})")
            # Date field special handling
            elif field in ['Date', 'Graduation Date']:
                date_match = self._compare_dates(stored_str, extracted_str)
                if date_match:
                    matching_fields += 1
                    field_matches[field] = True
                    print(f"    ✅ DATE MATCH")
                else:
                    field_matches[field] = False
                    print(f"    ❌ DATE MISMATCH")
            else:
                field_matches[field] = False
                print(f"    ❌ NO MATCH")
        
        match_score = matching_fields / total_fields if total_fields > 0 else 0
        print(f"\n[DATA COMPARISON] Overall match: {matching_fields:.1f}/{total_fields} ({match_score:.1%})")
        
        return {
            'match_score': match_score,
            'matching_fields': matching_fields,
            'total_fields': total_fields,
            'field_matches': field_matches
        }
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        if not text1 or not text2:
            return 0.0
        
        if text1 == text2:
            return 1.0
        
        # Simple character-based similarity
        min_len = min(len(text1), len(text2))
        max_len = max(len(text1), len(text2))
        
        if max_len == 0:
            return 0.0
        
        # Count matching characters at the same positions
        matching_chars = sum(1 for i in range(min_len) if text1[i] == text2[i])
        
        # Calculate similarity considering length differences
        similarity = matching_chars / max_len
        
        # Bonus for substring matches
        if text1 in text2 or text2 in text1:
            similarity = max(similarity, min_len / max_len)
        
        return similarity
    
    def _compare_dates(self, date1: str, date2: str) -> bool:
        """Compare two date strings with flexible parsing."""
        if not date1 or not date2:
            return False
        
        if date1 == date2:
            return True
        
        # Try to extract year from both dates
        year_pattern = r'\b(19|20)\d{2}\b'
        years1 = re.findall(year_pattern, date1)
        years2 = re.findall(year_pattern, date2)
        
        # If both contain years and they match, consider it a match
        if years1 and years2 and years1[0] + years1[1] == years2[0] + years2[1]:
            return True
        
        # Check for month names
        months = ['january', 'february', 'march', 'april', 'may', 'june',
                  'july', 'august', 'september', 'october', 'november', 'december',
                  'jan', 'feb', 'mar', 'apr', 'may', 'jun',
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        date1_months = [month for month in months if month in date1.lower()]
        date2_months = [month for month in months if month in date2.lower()]
        
        if date1_months and date2_months:
            # Check if months match (accounting for abbreviations)
            month1 = date1_months[0]
            month2 = date2_months[0]
            
            if month1 == month2 or month1.startswith(month2[:3]) or month2.startswith(month1[:3]):
                return True
        
        return False
    
    async def _store_certificate_data(
        self,
        cert_data: Dict[str, Any],
        verification_result: Dict[str, Any]
    ):
        """Store certificate data and verification result in immutable ledger."""
        cert_number = cert_data.get('Certificate Number')
        if not cert_number:
            return
        
        try:
            # Check if certificate already exists
            existing_cert = await self.db.get_certificate(cert_number)
            
            if not existing_cert:
                # Prepare data for storage
                storage_data = {
                    **cert_data,
                    'hash': verification_result.get('hash'),
                    'verification_status': verification_result['verification_status'].value,
                    'confidence': verification_result.get('confidence', 0),
                    'source_image': os.path.basename(verification_result['image_path']),
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'processing_time': verification_result.get('processing_time'),
                    'hash_match': verification_result.get('hash_match', False),
                    'data_match': verification_result.get('data_match', False)
                }
                
                # Store certificate in ledger
                await self.db.add_certificate(cert_number, storage_data)
                print(f"\n[SUCCESS] Certificate data stored in immutable ledger with ID: {cert_number}")
            else:
                print(f"\n[INFO] Certificate {cert_number} already exists in ledger")
            
            # Always add verification record regardless
            verification_record = {
                'status': verification_result['verification_status'].value,
                'confidence': verification_result.get('confidence', 0),
                'source': os.path.basename(verification_result['image_path']),
                'similarity_score': verification_result.get('similarity_score'),
                'hash_match': verification_result.get('hash_match', False),
                'data_match': verification_result.get('data_match', False),
                'message': verification_result.get('message', ''),
                'processing_time': verification_result.get('processing_time'),
                'verified_at': datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.add_verification_record(cert_number, verification_record)
            print(f"[SUCCESS] Verification record added to ledger for {cert_number}")
            
        except Exception as e:
            print(f"[ERROR] Failed to store certificate data in ledger: {e}")
    
    async def extract_hash_from_certificate(
        self, 
        image_path: str, 
        use_enhanced: bool = True
    ) -> Dict[str, Any]:
        """Extract hash from certificate image."""
        try:
            if use_enhanced:
                extracted_hash, confidence = await hash_service.extract_hash_enhanced(image_path)
                return {
                    'extracted_hash': extracted_hash,
                    'confidence': confidence,
                    'method': 'enhanced_extraction'
                }
            else:
                extracted_hash = await hash_service.extract_hash_from_certificate(image_path)
                return {
                    'extracted_hash': extracted_hash,
                    'confidence': 1.0 if extracted_hash else 0.0,
                    'method': 'basic_extraction'
                }
        except Exception as e:
            print(f"Error extracting hash: {e}")
            return {
                'extracted_hash': None,
                'confidence': 0.0,
                'method': 'failed',
                'error': str(e)
            }
    
    async def verify_by_hash(
        self,
        certificate_number: str,
        provided_hash: str
    ) -> Dict[str, Any]:
        """Verify certificate by comparing provided hash with stored hash."""
        try:
            # Get certificate from database
            stored_certificate = await self.db.get_certificate(certificate_number)
            
            if not stored_certificate:
                return {
                    'verification_status': VerificationStatus.FAILED,
                    'message': f'Certificate {certificate_number} not found in database',
                    'confidence': 0.0,
                    'hash_match': False
                }
            
            stored_hash = stored_certificate.get('hash', '')
            
            # Compare hashes
            hash_comparison = self.compare_hashes(provided_hash, stored_hash)
            
            # Determine result
            if hash_comparison['match']:
                status = VerificationStatus.VERIFIED
                message = f"Hash verification successful. {hash_comparison['reason']}"
            else:
                status = VerificationStatus.FAILED
                message = f"Hash verification failed. {hash_comparison['reason']}"
            
            # Record verification attempt
            verification_record = {
                'status': status.value,
                'confidence': hash_comparison['similarity'],
                'provided_hash': provided_hash,
                'stored_hash': stored_hash,
                'verification_method': 'hash_comparison',
                'message': message,
                'verified_at': datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.add_verification_record(certificate_number, verification_record)
            
            return {
                'verification_status': status,
                'message': message,
                'confidence': hash_comparison['similarity'],
                'hash_match': hash_comparison['match'],
                'provided_hash': provided_hash,
                'stored_hash': stored_hash,
                'certificate_number': certificate_number
            }
            
        except Exception as e:
            print(f"Error in hash verification: {e}")
            return {
                'verification_status': VerificationStatus.FAILED,
                'message': f'Hash verification error: {str(e)}',
                'confidence': 0.0,
                'hash_match': False
            }

# Global service instance with enhanced ledger integration
verification_service = VerificationService()