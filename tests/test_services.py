import pytest
import os
import sys
import tempfile
import shutil
from PIL import Image
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.hash_service import HashService
from app.services.ocr_service import OCRService
from app.services.watermark_service import WatermarkService
from app.services.verification_service import VerificationService
from app.database import CertificateDatabase
from app.models import VerificationStatus
from app.config import settings

# Test fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def sample_certificate(temp_dir):
    """Create a sample certificate image."""
    img = Image.new('RGB', (1200, 800), color='white')
    img_path = os.path.join(temp_dir, 'test_certificate.png')
    img.save(img_path)
    return img_path

@pytest.fixture
def hash_service():
    """Create a HashService instance."""
    return HashService()

@pytest.fixture
def ocr_service():
    """Create an OCRService instance."""
    return OCRService()

@pytest.fixture
def watermark_service():
    """Create a WatermarkService instance."""
    return WatermarkService()

@pytest.fixture
def verification_service():
    """Create a VerificationService instance."""
    return VerificationService()

@pytest.fixture
def test_database(temp_dir):
    """Create a test database."""
    db_path = os.path.join(temp_dir, 'test_db.json')
    return CertificateDatabase(db_path)

# Hash Service Tests
class TestHashService:
    def test_generate_certificate_hash(self, hash_service, sample_certificate):
        """Test hash generation from certificate."""
        hash_value = hash_service.generate_certificate_hash(sample_certificate)
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)
    
    def test_checksum_operations(self, hash_service):
        """Test checksum addition and verification."""
        test_hash = "a" * 64
        
        # Add checksum
        with_checksum = hash_service.add_error_correction_to_hash(test_hash)
        assert len(with_checksum) == 68
        
        # Verify checksum
        extracted_hash, is_valid = hash_service.verify_hash_with_checksum(with_checksum)
        assert extracted_hash == test_hash
        assert is_valid == True
        
        # Test invalid checksum
        invalid = with_checksum[:-1] + "0"
        extracted_hash, is_valid = hash_service.verify_hash_with_checksum(invalid)
        assert is_valid == False
    
    def test_hash_char_encoding_decoding(self, hash_service):
        """Test encoding and decoding of hash characters."""
        for hex_char in '0123456789abcdef':
            # Encode
            color = hash_service.encode_hash_char_robust(hex_char)
            assert len(color) == 3
            assert all(c == color[0] for c in color)  # All RGB values same (grayscale)
            
            # Decode
            decoded = hash_service.decode_hash_char_robust(color[0])
            assert decoded == hex_char
    
    @pytest.mark.asyncio
    async def test_embed_and_extract_hash(self, hash_service, sample_certificate, temp_dir):
        """Test embedding and extracting hash from certificate."""
        test_hash = "b7f069b63ad42d547a116fea8d49f878bb792beaa1fe07f2dfc3cd64f10c8801"
        output_path = os.path.join(temp_dir, 'embedded.png')
        
        # Embed hash
        result = await hash_service.embed_hash_on_certificate(
            sample_certificate, 
            test_hash, 
            output_path
        )
        assert os.path.exists(result)
        
        # Extract hash
        extracted = await hash_service.extract_hash_from_certificate(output_path)
        assert extracted == test_hash
    
    @pytest.mark.asyncio
    async def test_enhanced_extraction(self, hash_service, sample_certificate):
        """Test enhanced hash extraction with confidence scoring."""
        extracted, confidence = await hash_service.extract_hash_enhanced(sample_certificate)
        assert extracted is not None or confidence == 0
        assert 0 <= confidence <= 1
    
    def test_hash_similarity_calculation(self, hash_service):
        """Test hash similarity calculation."""
        hash1 = "a" * 64
        hash2 = "a" * 64
        hash3 = "b" * 64
        hash4 = "a" * 32 + "b" * 32
        
        assert hash_service.calculate_hash_similarity(hash1, hash2) == 1.0
        assert hash_service.calculate_hash_similarity(hash1, hash3) == 0.0
        assert hash_service.calculate_hash_similarity(hash1, hash4) == 0.5

# OCR Service Tests
class TestOCRService:
    def test_ocr_initialization(self, ocr_service):
        """Test OCR service initialization."""
        assert ocr_service is not None
    
    @pytest.mark.asyncio
    async def test_extract_certificate_data(self, ocr_service, temp_dir):
        """Test certificate data extraction."""
        # Create a more realistic certificate for OCR
        from PIL import ImageDraw
        img = Image.new('RGB', (1200, 800), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add text that OCR can read
        draw.text((600, 100), "FACULTY OF HEALTH SCIENCES AND MEDICAL RESEARCH", anchor="mm", fill="black")
        draw.text((600, 200), "Bachelor of Science Honours in Data Science and Analytics", anchor="mm", fill="black")
        draw.text((600, 300), "WE HEREBY CERTIFY THAT", anchor="mm", fill="black")
        draw.text((600, 350), "Test Student Name", anchor="mm", fill="black")
        draw.text((100, 700), "Date: 15 June 2025", fill="black")
        draw.text((900, 700), "BSc-TEST123", fill="black")
        
        img_path = os.path.join(temp_dir, 'ocr_test.png')
        img.save(img_path)
        
        # Extract data
        data = await ocr_service.extract_certificate_data(img_path)
        assert isinstance(data, dict)
        # Results depend on Tesseract installation

# Watermark Service Tests
class TestWatermarkService:
    @pytest.mark.asyncio
    async def test_add_visible_watermark(self, watermark_service, sample_certificate, temp_dir):
        """Test adding visible watermark."""
        output_path = os.path.join(temp_dir, 'watermarked.png')
        
        result = await watermark_service.add_visible_watermark(
            sample_certificate,
            output_path,
            "VERIFIED",
            pattern="diagonal",
            opacity=40,
            font_size=20
        )
        
        assert os.path.exists(result)
        assert os.path.getsize(result) > 0
    
    @pytest.mark.asyncio
    async def test_watermark_patterns(self, watermark_service, sample_certificate, temp_dir):
        """Test different watermark patterns."""
        patterns = ["diagonal", "grid", "corner"]
        
        for pattern in patterns:
            output_path = os.path.join(temp_dir, f'watermark_{pattern}.png')
            result = await watermark_service.add_visible_watermark(
                sample_certificate,
                output_path,
                "TEST",
                pattern=pattern
            )
            assert os.path.exists(result)
    
    @pytest.mark.asyncio
    async def test_add_security_pattern(self, watermark_service, sample_certificate, temp_dir):
        """Test adding security pattern."""
        output_path = os.path.join(temp_dir, 'security.png')
        
        result = await watermark_service.add_security_pattern(
            sample_certificate,
            output_path,
            "BSc-12700"
        )
        
        assert os.path.exists(result)

# Database Tests
class TestCertificateDatabase:
    @pytest.mark.asyncio
    async def test_add_and_get_certificate(self, test_database):
        """Test adding and retrieving certificate."""
        cert_data = {
            "Certificate Number": "BSc-TEST001",
            "Student Name": "Test Student",
            "hash": "a" * 64,
            "verification_status": "VERIFIED"
        }
        
        # Add certificate
        result = await test_database.add_certificate("BSc-TEST001", cert_data)
        assert result is not None
        
        # Get certificate
        retrieved = await test_database.get_certificate("BSc-TEST001")
        assert retrieved is not None
        assert retrieved["Certificate Number"] == "BSc-TEST001"
        assert retrieved["Student Name"] == "Test Student"
    
    @pytest.mark.asyncio
    async def test_search_certificates(self, test_database):
        """Test searching certificates."""
        # Add test certificates
        for i in range(3):
            await test_database.add_certificate(
                f"BSc-TEST{i:03d}",
                {
                    "student_name": f"Student {i}",
                    "degree_name": "Bachelor of Science"
                }
            )
        
        # Search by student name
        results = await test_database.search_certificates("Student 1")
        assert len(results) == 1
        assert results[0]["student_name"] == "Student 1"
    
    @pytest.mark.asyncio
    async def test_verification_history(self, test_database):
        """Test verification history tracking."""
        cert_number = "BSc-TEST001"
        
        # Add certificate
        await test_database.add_certificate(cert_number, {"hash": "test"})
        
        # Add verification records
        for i in range(3):
            await test_database.add_verification_record(
                cert_number,
                {"status": "VERIFIED", "confidence": 0.9 + i * 0.01}
            )
        
        # Get history
        history = await test_database.get_verification_history(cert_number)
        assert len(history) == 3
        assert all(record["status"] == "VERIFIED" for record in history)
    
    @pytest.mark.asyncio
    async def test_statistics(self, test_database):
        """Test database statistics."""
        # Add some certificates
        for i in range(5):
            await test_database.add_certificate(
                f"BSc-TEST{i:03d}",
                {"verification_status": "VERIFIED" if i % 2 == 0 else "FAILED"}
            )
        
        stats = await test_database.get_statistics()
        assert stats["total_certificates"] == 5
        assert "VERIFIED" in stats["status_distribution"]
        assert "FAILED" in stats["status_distribution"]

# Verification Service Tests
class TestVerificationService:
    @pytest.mark.asyncio
    async def test_verify_certificate_no_hash(self, verification_service, sample_certificate):
        """Test verification when no hash is found."""
        result = await verification_service.verify_certificate(
            sample_certificate,
            expected_hash=None,
            use_enhanced=True,
            check_database=False
        )
        
        assert result["verification_status"] in [
            VerificationStatus.NO_HASH, 
            VerificationStatus.CORRUPTED_HASH
        ]
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_verify_with_expected_hash(self, verification_service, hash_service, temp_dir):
        """Test verification with expected hash."""
        # Create certificate with embedded hash
        test_hash = "b7f069b63ad42d547a116fea8d49f878bb792beaa1fe07f2dfc3cd64f10c8801"
        
        img = Image.new('RGB', (1200, 800), color='white')
        img_path = os.path.join(temp_dir, 'test_cert.png')
        img.save(img_path)
        
        embedded_path = os.path.join(temp_dir, 'embedded_cert.png')
        await hash_service.embed_hash_on_certificate(img_path, test_hash, embedded_path)
        
        # Verify
        result = await verification_service.verify_certificate(
            embedded_path,
            expected_hash=test_hash,
            use_enhanced=False,
            check_database=False
        )
        
        assert result["hash"] == test_hash
        assert result["verification_status"] == VerificationStatus.VERIFIED

# Integration Tests
class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow(self, hash_service, verification_service, test_database, temp_dir):
        """Test complete workflow: create, embed, verify, store."""
        # Create certificate
        img = Image.new('RGB', (1200, 800), color='white')
        img_path = os.path.join(temp_dir, 'workflow_cert.png')
        img.save(img_path)
        
        # Generate and embed hash
        cert_hash = hash_service.generate_certificate_hash(img_path)
        embedded_path = os.path.join(temp_dir, 'workflow_embedded.png')
        await hash_service.embed_hash_on_certificate(img_path, cert_hash, embedded_path)
        
        # Verify certificate
        result = await verification_service.verify_certificate(
            embedded_path,
            expected_hash=cert_hash,
            use_enhanced=True,
            check_database=True
        )
        
        assert result["verification_status"] == VerificationStatus.VERIFIED
        assert result["hash"] == cert_hash

if __name__ == "__main__":
    pytest.main([__file__, "-v"])