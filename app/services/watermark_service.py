from PIL import Image, ImageDraw, ImageFont
from typing import Optional
import os

from app.config import settings

class WatermarkService:
    """Service for adding watermarks to certificates."""
    
    def __init__(self):
        self.default_font_size = 20
        self.default_opacity = 40
        
    async def add_visible_watermark(
        self,
        image_path: str,
        output_path: str,
        watermark_text: str,
        pattern: str = "diagonal",
        opacity: int = 40,
        font_size: int = 20
    ) -> str:
        """Add a visible watermark pattern to certificate."""
        img = Image.open(image_path).convert("RGBA")
        
        # Create watermark layer
        watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)
        
        # Try to load font
        font = None
        try:
            # Try different font paths
            font_paths = [
                "arial.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:\\Windows\\Fonts\\arial.ttf"
            ]
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                    break
        except:
            font = ImageFont.load_default()
        
        # Apply watermark based on pattern
        if pattern == "diagonal":
            # Add diagonal lines pattern
            for i in range(0, img.width + img.height, 50):
                draw.line([(0, i), (i, 0)], fill=(200, 200, 200, 30), width=1)
            
            # Repeat text diagonally
            for x in range(100, img.width - 100, 200):
                for y in range(100, img.height - 100, 200):
                    draw.text(
                        (x, y), 
                        watermark_text, 
                        fill=(200, 200, 200, opacity), 
                        font=font
                    )
        
        elif pattern == "grid":
            # Grid pattern with text
            spacing = 150
            for x in range(50, img.width, spacing):
                for y in range(50, img.height, spacing):
                    draw.text(
                        (x, y), 
                        watermark_text, 
                        fill=(200, 200, 200, opacity), 
                        font=font
                    )
        
        elif pattern == "corner":
            # Corner watermarks
            positions = [
                (50, 50),  # Top-left
                (img.width - 200, 50),  # Top-right
                (50, img.height - 100),  # Bottom-left
                (img.width - 200, img.height - 100)  # Bottom-right
            ]
            for pos in positions:
                draw.text(
                    pos, 
                    watermark_text, 
                    fill=(200, 200, 200, opacity), 
                    font=font
                )
        
        # Composite the watermark
        watermarked = Image.alpha_composite(img, watermark)
        
        # Convert back to RGB for saving as PNG/JPEG
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            watermarked = watermarked.convert('RGB')
        
        watermarked.save(output_path)
        return output_path
    
    async def add_security_pattern(
        self,
        image_path: str,
        output_path: str,
        certificate_number: str
    ) -> str:
        """Add a security pattern with certificate number."""
        img = Image.open(image_path).convert("RGBA")
        
        # Create security layer
        security = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(security)
        
        # Add micro-text pattern
        micro_text = f"{certificate_number} • "
        micro_font = None
        try:
            micro_font = ImageFont.truetype("arial.ttf", 8)
        except:
            micro_font = ImageFont.load_default()
        
        # Create a dense pattern of micro-text
        for y in range(0, img.height, 20):
            text_line = micro_text * (img.width // (len(micro_text) * 6))
            draw.text(
                (0, y), 
                text_line, 
                fill=(220, 220, 220, 20), 
                font=micro_font
            )
        
        # Add border pattern
        border_width = 30
        # Top border
        for x in range(0, img.width, 50):
            draw.text(
                (x, 10), 
                certificate_number, 
                fill=(200, 200, 200, 30), 
                font=micro_font
            )
        # Bottom border
        for x in range(0, img.width, 50):
            draw.text(
                (x, img.height - 20), 
                certificate_number, 
                fill=(200, 200, 200, 30), 
                font=micro_font
            )
        
        # Composite the security pattern
        secured = Image.alpha_composite(img, security)
        
        # Convert back to RGB if needed
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            secured = secured.convert('RGB')
        
        secured.save(output_path)
        return output_path

# Global service instance
watermark_service = WatermarkService()