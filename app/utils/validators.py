from fastapi import UploadFile
import os
from typing import Optional

from app.config import settings

def validate_file(file: UploadFile) -> Optional[str]:
    """Validate uploaded file."""
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > settings.max_file_size:
        return f"File size exceeds maximum allowed size of {settings.max_file_size / 1024 / 1024}MB"
    
    # Check file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.allowed_extensions:
        return f"File type {ext} not allowed. Allowed types: {', '.join(settings.allowed_extensions)}"
    
    # Check if filename is safe
    if not file.filename or ".." in file.filename or "/" in file.filename or "\\" in file.filename:
        return "Invalid filename"
    
    return None

def validate_hash(hash_string: str) -> Optional[str]:
    """Validate hash string format."""
    if not hash_string:
        return "Hash cannot be empty"
    
    if len(hash_string) != 64:
        return "Hash must be 64 characters long"
    
    try:
        int(hash_string, 16)
    except ValueError:
        return "Hash must be a valid hexadecimal string"
    
    return None

def validate_certificate_number(cert_number: str) -> Optional[str]:
    """Validate certificate number format."""
    if not cert_number:
        return "Certificate number cannot be empty"
    
    # Add specific validation rules for your certificate format
    # For example, BSc-12700 format
    import re
    if not re.match(r'^[A-Za-z]+-\d+$', cert_number):
        return "Invalid certificate number format"
    
    return None