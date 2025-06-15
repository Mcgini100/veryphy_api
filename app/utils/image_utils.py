import random
from PIL import Image, ImageFilter
import os

def simulate_print_scan_cycle(image_path: str, output_dir: str = None) -> str:
    """Simulate print/scan degradation on an image."""
    img = Image.open(image_path)
    img = img.convert("L")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.7))
    pixels = img.load()
    width, height = img.size
    
    # Add random noise
    for _ in range(int(width * height * 0.001)):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        pixels[x, y] = random.choice([0, 255])
    
    # Save to output directory
    if output_dir is None:
        output_dir = os.path.dirname(image_path)
    
    output_filename = f"scanned_{os.path.basename(image_path)}"
    output_path = os.path.join(output_dir, output_filename)
    img.save(output_path, "JPEG", quality=90)
    return output_path

def resize_image(image_path: str, max_width: int = 1920, max_height: int = 1080) -> str:
    """Resize image if it exceeds maximum dimensions."""
    img = Image.open(image_path)
    
    if img.width <= max_width and img.height <= max_height:
        return image_path
    
    # Calculate new dimensions maintaining aspect ratio
    ratio = min(max_width / img.width, max_height / img.height)
    new_width = int(img.width * ratio)
    new_height = int(img.height * ratio)
    
    # Resize image
    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Save resized image
    output_path = f"resized_{os.path.basename(image_path)}"
    img.save(output_path)
    return output_path

def convert_to_format(image_path: str, output_format: str) -> str:
    """Convert image to specified format."""
    img = Image.open(image_path)
    
    # Handle transparency for JPEG
    if output_format.lower() in ['jpg', 'jpeg'] and img.mode in ('RGBA', 'LA'):
        # Create white background
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img, mask=img.split()[1])
        img = background
    
    # Generate output filename
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_filename = f"{base_name}.{output_format.lower()}"
    
    img.save(output_filename, format=output_format.upper())
    return output_filename