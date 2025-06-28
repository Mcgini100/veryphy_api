import cv2
import pytesseract
import re
import numpy as np
from typing import Dict, Optional, List, Any

from app.config import settings

class OCRService:
    """Service for OCR operations on certificates."""
    
    def __init__(self):
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    
    def correct_skew(self, image: np.ndarray) -> np.ndarray:
        """Correct skew in scanned images."""
        inverted = cv2.bitwise_not(image)
        thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        deskewed = cv2.warpAffine(
            image, M, (w, h), 
            flags=cv2.INTER_CUBIC, 
            borderMode=cv2.BORDER_CONSTANT, 
            borderValue=(255, 255, 255)
        )
        return deskewed
    
    def preprocess_image_enhanced(self, image_path: str) -> np.ndarray:
        """Preprocess image for better OCR results."""
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f"Image not found at path: {image_path}")
        deskewed = self.correct_skew(image)
        processed = cv2.adaptiveThreshold(
            deskewed, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 15, 4
        )
        return processed
    
    def find_anchor_indices(
        self, 
        ocr_data: Dict[str, List], 
        anchor_keywords: List[str]
    ) -> Optional[List[int]]:
        """Find indices of anchor keywords in OCR data."""
        num_boxes = len(ocr_data['level'])
        full_anchor_text = ' '.join(anchor_keywords).lower()
        current_phrase = []
        start_index = -1
        
        for i in range(num_boxes):
            word = ocr_data['text'][i].strip().lower()
            if not word:
                current_phrase = []
                start_index = -1
                continue
            if not current_phrase:
                start_index = i
            current_phrase.append(word)
            current_joined_phrase = ' '.join(current_phrase)
            if current_joined_phrase == full_anchor_text:
                return list(range(start_index, i + 1))
            if not full_anchor_text.startswith(current_joined_phrase):
                current_phrase = [word]
                start_index = i
        return None
    
    def find_full_line_below_anchor(
        self, 
        ocr_data: Dict[str, List], 
        anchor_keywords: List[str], 
        line_threshold: int = 15
    ) -> Optional[str]:
        """Find full line of text below anchor keywords."""
        try:
            anchor_indices = self.find_anchor_indices(ocr_data, anchor_keywords)
            if not anchor_indices:
                return None
            last_anchor_word_index = anchor_indices[-1]
            anchor_bottom = ocr_data['top'][last_anchor_word_index] + ocr_data['height'][last_anchor_word_index]
            next_line_top = float('inf')
            
            for i in range(len(ocr_data['text'])):
                word_top = ocr_data['top'][i]
                if word_top > anchor_bottom and ocr_data['text'][i].strip():
                    if word_top < next_line_top:
                        next_line_top = word_top
                        
            if next_line_top == float('inf'):
                return None
                
            line_words = []
            for i in range(len(ocr_data['text'])):
                if abs(ocr_data['top'][i] - next_line_top) < line_threshold:
                    if ocr_data['text'][i].strip():
                        line_words.append((ocr_data['left'][i], ocr_data['text'][i]))
            line_words.sort()
            return ' '.join([word[1] for word in line_words])
        except Exception:
            return None
    
    def find_value_based_on_anchor(
        self, 
        ocr_data: Dict[str, List], 
        anchor_keywords: List[str], 
        line_threshold: int = 15
    ) -> Optional[str]:
        """Find value based on anchor keywords."""
        try:
            anchor_indices = self.find_anchor_indices(ocr_data, anchor_keywords)
            if not anchor_indices:
                return None
            last_anchor_word_index = anchor_indices[-1]
            anchor_top = ocr_data['top'][last_anchor_word_index]
            value_words = []
            
            for i in range(last_anchor_word_index + 1, len(ocr_data['text'])):
                if abs(ocr_data['top'][i] - anchor_top) < line_threshold and ocr_data['text'][i].strip():
                    value_words.append(ocr_data['text'][i])
            return ' '.join(value_words) if value_words else None
        except Exception:
            return None
    
    def perform_ocr_extraction(self, image: np.ndarray) -> Dict[str, Any]:
        """Perform OCR and extract certificate data."""
        custom_config = r'--oem 3 --psm 3'
        ocr_data = pytesseract.image_to_data(
            image, 
            config=custom_config, 
            output_type=pytesseract.Output.DICT
        )
        full_text = pytesseract.image_to_string(image, config=custom_config)

        extracted = {}
        
        # Extract Certificate Number
        match = re.search(r'BSc-\d+', full_text, re.IGNORECASE)
        extracted['Certificate Number'] = match.group(0) if match else None

        # Extract other fields
        extracted['Faculty Name'] = self.find_value_based_on_anchor(
            ocr_data, ['Faculty', 'of']
        )
        extracted['Degree Name'] = self.find_full_line_below_anchor(
            ocr_data, 
            ['Faculty', 'of', 'Health', 'Sciences', 'and', 'Medical', 'Research']
        )
        extracted['Student Name'] = self.find_full_line_below_anchor(
            ocr_data, ['WE', 'HEREBY', 'CERTIFY', 'THAT']
        )
        extracted['Degree Classification'] = self.find_full_line_below_anchor(
            ocr_data, ['Degree', 'Classification:']
        )
        
        # Clean date field
        raw_date = self.find_value_based_on_anchor(ocr_data, ['Date:'])
        cleaned_date = raw_date
        cert_num = extracted.get('Certificate Number')
        if cleaned_date and cert_num and cert_num in cleaned_date:
            cleaned_date = cleaned_date.replace(cert_num, '').strip()
        extracted['Date'] = cleaned_date
        
        return extracted
    
    async def extract_certificate_data(self, image_path: str) -> Dict[str, Any]:
        """Extract certificate data using OCR with fallback to enhanced preprocessing."""
        print("[INFO] Attempting OCR extraction...")
        
        # Try simple OCR first
        try:
            simple_gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if simple_gray is None:
                raise FileNotFoundError(f"Image not found at path: {image_path}")
            
            data = self.perform_ocr_extraction(simple_gray)
            
            # Check if we got meaningful results
            if (data.get('Student Name') and data.get('Certificate Number') and 
                data.get('Degree Name')):
                print("[SUCCESS] OCR extraction successful with simple preprocessing.")
                return data
        except Exception as e:
            print(f"[WARNING] Simple OCR failed: {e}")
        
        # Fallback to enhanced preprocessing
        try:
            print("[INFO] Applying enhanced preprocessing...")
            enhanced_image = self.preprocess_image_enhanced(image_path)
            data = self.perform_ocr_extraction(enhanced_image)
            print("[INFO] Enhanced OCR complete.")
            return data
        except Exception as e:
            print(f"[ERROR] Enhanced OCR failed: {e}")
            return {}

# Global service instance
ocr_service = OCRService()