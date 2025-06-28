import hashlib
from typing import Tuple, Optional, List
from PIL import Image, ImageDraw, ImageStat
import numpy as np
import cv2
import os

from app.config import settings

class HashService:
    """Service for hash embedding and extraction operations."""
    
    def __init__(self):
        self.block_size = settings.hash_block_size
        self.spacing_y = settings.hash_spacing_y
        self.start_x = settings.hash_start_x
        self.start_y = settings.hash_start_y
        self.use_checksum = settings.use_checksum
    
    def generate_certificate_hash(self, image_path: str) -> str:
        """Generate SHA-256 hash of the certificate image."""
        hasher = hashlib.sha256()
        with open(image_path, 'rb') as f:
            chunk = f.read(4096)
            while chunk:
                hasher.update(chunk)
                chunk = f.read(4096)
        return hasher.hexdigest()
    
    def add_error_correction_to_hash(self, hash_string: str) -> str:
        """Add simple checksum for error detection."""
        checksum = hashlib.sha256(hash_string.encode()).hexdigest()[-4:]
        return hash_string + checksum
    
    def verify_hash_with_checksum(self, hash_with_checksum: str) -> Tuple[Optional[str], bool]:
        """Verify hash integrity using checksum."""
        if len(hash_with_checksum) < 68:
            return None, False
        
        hash_part = hash_with_checksum[:64]
        checksum_part = hash_with_checksum[64:]
        
        expected_checksum = hashlib.sha256(hash_part.encode()).hexdigest()[-4:]
        
        return hash_part, (checksum_part == expected_checksum)
    
    def encode_hash_char_robust(self, char: str) -> Tuple[int, int, int]:
        """Encode a hex character to grayscale value."""
        val = int(char, 16)
        gray_value = 240 - (val * 8)
        return (gray_value, gray_value, gray_value)
    
    def decode_hash_char_robust(self, gray_value: float) -> str:
        """Decode grayscale value back to hex character."""
        val = round((240 - gray_value) / 8)
        val = max(0, min(15, val))
        return hex(int(val))[2:]
    
    def get_embedding_pattern_vertical(
        self, 
        image_size: Tuple[int, int], 
        hash_length: int
    ) -> Tuple[List[Tuple[int, int]], int]:
        """Define vertical pattern for hash embedding on far-left margin."""
        pattern = []
        for i in range(hash_length):
            x = self.start_x
            y = self.start_y + (i * self.spacing_y)
            pattern.append((x, y))
        
        return pattern, self.block_size
    
    async def embed_hash_on_certificate(
        self, 
        image_path: str, 
        certificate_hash: str,
        output_path: str,
        use_checksum: Optional[bool] = None
    ) -> str:
        """Embed hash into certificate using vertical pattern."""
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        # Use setting if not specified
        if use_checksum is None:
            use_checksum = self.use_checksum
        
        # Add checksum if requested
        if use_checksum:
            certificate_hash = self.add_error_correction_to_hash(certificate_hash)
        
        pattern, block_size = self.get_embedding_pattern_vertical(
            img.size, 
            len(certificate_hash)
        )
        
        for i, char in enumerate(certificate_hash):
            x, y = pattern[i]
            color = self.encode_hash_char_robust(char)
            draw.rectangle(
                [x, y, x + block_size, y + block_size], 
                fill=color
            )
        
        img.save(output_path)
        return output_path
    
    async def extract_hash_from_certificate(
        self, 
        image_path: str,
        use_checksum: Optional[bool] = None
    ) -> Optional[str]:
        """Extract embedded hash from certificate."""
        try:
            if use_checksum is None:
                use_checksum = self.use_checksum
            
            hash_length = 68 if use_checksum else 64
            
            img = Image.open(image_path).convert("L")
            pattern, block_size = self.get_embedding_pattern_vertical(
                img.size, 
                hash_length
            )
            extracted_hash = []
            
            for x, y in pattern:
                if x + block_size <= img.width and y + block_size <= img.height:
                    box = (x, y, x + block_size, y + block_size)
                    region = img.crop(box)
                    stats = ImageStat.Stat(region)
                    median_gray_value = stats.median[0]
                    char = self.decode_hash_char_robust(median_gray_value)
                    extracted_hash.append(char)
            
            result = "".join(extracted_hash)
            
            # Verify checksum if used
            if use_checksum and len(result) == 68:
                hash_part, is_valid = self.verify_hash_with_checksum(result)
                if is_valid:
                    return hash_part
                else:
                    print("[WARNING] Checksum verification failed")
                    return result[:64]
            
            return result
        except Exception as e:
            print(f"Error extracting hash: {e}")
            return None
    
    async def extract_hash_enhanced(
        self, 
        image_path: str
    ) -> Tuple[Optional[str], float]:
        """Enhanced hash extraction with multiple strategies and confidence scoring."""
        try:
            img = Image.open(image_path).convert("L")
            pattern, block_size = self.get_embedding_pattern_vertical(img.size, 64)
            
            # Try multiple strategies
            strategies = [
                {'method': 'median', 'threshold': None, 'preprocess': None},
                {'method': 'mean', 'threshold': None, 'preprocess': None},
                {'method': 'median', 'threshold': 128, 'preprocess': None},
                {'method': 'median', 'threshold': None, 'preprocess': 'denoise'},
            ]
            
            best_hash = None
            best_confidence = 0
            
            for strategy in strategies:
                img_processed = img.copy()
                
                # Apply preprocessing if specified
                if strategy['preprocess'] == 'denoise':
                    img_array = np.array(img_processed)
                    img_array = cv2.fastNlMeansDenoising(img_array, None, 10, 7, 21)
                    img_processed = Image.fromarray(img_array)
                
                extracted_hash = []
                confidence_scores = []
                
                for x, y in pattern:
                    if x + block_size <= img.width and y + block_size <= img.height:
                        box = (x, y, x + block_size, y + block_size)
                        region = img_processed.crop(box)
                        stats = ImageStat.Stat(region)
                        
                        # Get gray value based on strategy
                        if strategy['method'] == 'median':
                            gray_value = stats.median[0]
                        else:
                            gray_value = stats.mean[0]
                        
                        # Apply threshold if specified
                        if strategy['threshold']:
                            gray_value = 255 if gray_value > strategy['threshold'] else 0
                        
                        char = self.decode_hash_char_robust(gray_value)
                        extracted_hash.append(char)
                        
                        # Calculate confidence
                        expected_gray = 240 - (int(char, 16) * 8)
                        confidence = 1 - abs(gray_value - expected_gray) / 255
                        confidence_scores.append(confidence)
                
                # Check if this looks like a valid hash
                hash_str = "".join(extracted_hash)
                avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
                
                # Valid hash should have varied characters
                unique_chars = len(set(hash_str))
                entropy_score = unique_chars / 16
                
                # Combined score
                combined_score = avg_confidence * 0.7 + entropy_score * 0.3
                
                if combined_score > best_confidence:
                    best_confidence = combined_score
                    best_hash = hash_str
            
            # Check if the best hash is likely corrupted
            if best_hash and len(set(best_hash)) < settings.min_entropy_threshold:
                print(f"[WARNING] Best extracted hash has low entropy (unique chars: {len(set(best_hash))})")
            
            return best_hash, best_confidence
            
        except Exception as e:
            print(f"Error in enhanced hash extraction: {e}")
            return None, 0
    
    def calculate_hash_similarity(self, hash1: str, hash2: str) -> float:
        """Calculate similarity between two hashes."""
        if not hash1 or not hash2:
            return 0.0
        
        # Ensure same length for comparison
        min_len = min(len(hash1), len(hash2))
        hash1 = hash1[:min_len]
        hash2 = hash2[:min_len]
        
        matching_chars = sum(1 for a, b in zip(hash1, hash2) if a == b)
        return matching_chars / min_len if min_len > 0 else 0.0

# Global service instance
hash_service = HashService()