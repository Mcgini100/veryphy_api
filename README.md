# Certificate Verification API

A robust REST API for certificate verification using hash embedding and OCR extraction with fallback mechanisms.

## Features

- **Dual Verification**: Hash-based cryptographic verification with OCR fallback
- **Hash Embedding**: Embed SHA-256 hashes with error correction into certificates
- **Enhanced Extraction**: Multiple strategies for hash extraction from degraded images
- **Watermarking**: Add visible watermarks and security patterns
- **Batch Processing**: Verify multiple certificates simultaneously
- **Database Storage**: JSON-based persistence with verification history
- **Confidence Scoring**: Reliability metrics for verification results
- **REST API**: Full-featured API with comprehensive endpoints

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd certificate-verification-api

# Copy environment variables
cp .env.example .env

# Build and run with Docker Compose
docker-compose up -d

# Check API health
curl http://localhost:8000/api/v1/health
```

### Manual Installation

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install tesseract-ocr python3-pip

# Install Python dependencies
pip install -r requirements.txt

# Run the API
uvicorn app.main:app --reload
```

## API Endpoints

### Health Check
```bash
GET /api/v1/health
```

### Certificate Management

#### Upload Certificate
```bash
POST /api/v1/certificates/upload
Content-Type: multipart/form-data

Parameters:
- file: Certificate image file
- embed_hash: bool (default: true)
- add_watermark: bool (default: false)
- watermark_text: string (optional)
```

#### List Certificates
```bash
GET /api/v1/certificates?limit=10&offset=0&search=query
```

#### Get Certificate
```bash
GET /api/v1/certificates/{certificate_number}
```

#### Delete Certificate
```bash
DELETE /api/v1/certificates/{certificate_number}
```

### Verification

#### Verify Certificate
```bash
POST /api/v1/verify/
Content-Type: multipart/form-data

Parameters:
- file: Certificate image file
- expected_hash: string (optional)
- use_enhanced_extraction: bool (default: true)
- check_database: bool (default: true)
```

#### Batch Verification
```bash
POST /api/v1/verify/batch
Content-Type: multipart/form-data

Parameters:
- files: Multiple certificate images
- expected_hashes: JSON object mapping filenames to hashes
```

#### Extract Hash
```bash
POST /api/v1/verify/extract-hash
Content-Type: multipart/form-data

Parameters:
- file: Certificate image file
- use_enhanced: bool (default: true)
```

### Additional Features

#### Embed Hash in Certificate
```bash
POST /api/v1/certificates/{certificate_number}/embed-hash
Content-Type: application/json

{
    "hash_value": "optional_hash",
    "use_checksum": true,
    "generate_if_missing": true
}
```

#### Add Watermark
```bash
POST /api/v1/certificates/{certificate_number}/watermark
Content-Type: application/json

{
    "text": "VERIFIED",
    "opacity": 40,
    "font_size": 20,
    "pattern": "diagonal"
}
```

## Testing

Run the comprehensive test suite:

```bash
python test_api.py
```

This will:
1. Create test certificates
2. Test all API endpoints
3. Verify hash embedding and extraction
4. Test batch operations
5. Check database operations

## Configuration

Key settings in `.env`:

```env
# Processing Settings
HASH_BLOCK_SIZE=12          # Size of hash embedding blocks
USE_CHECKSUM=true           # Add error correction to hashes
MIN_ENTROPY_THRESHOLD=10    # Minimum unique characters for valid hash
DATA_MATCH_THRESHOLD=0.8    # Required field match for data verification

# File Limits
MAX_FILE_SIZE=10485760      # 10MB
ALLOWED_EXTENSIONS=.png,.jpg,.jpeg,.pdf
```

## Verification Status Codes

- **VERIFIED**: Hash matches exactly
- **VERIFIED_BY_DATA**: Hash failed but OCR data matches database
- **FAILED**: Hash mismatch
- **CORRUPTED_HASH**: Low entropy detected in hash
- **NO_HASH**: No embedded hash found
- **UNKNOWN**: Verification not performed

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   REST API      │────▶│  Verification   │────▶│   Database      │
│   (FastAPI)     │     │   Service       │     │   (JSON)        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ├─────────────────┐
                               ▼                 ▼
                        ┌─────────────┐   ┌─────────────┐
                        │ Hash Service│   │ OCR Service │
                        └─────────────┘   └─────────────┘
```

## Docker Deployment

The included `Dockerfile` and `docker-compose.yml` provide:
- Automated Tesseract OCR installation
- Volume mapping for data persistence
- Health checks
- Automatic restart on failure

## Security Considerations

1. **Change Secret Key**: Update `SECRET_KEY` in production
2. **CORS Settings**: Configure allowed origins appropriately
3. **File Validation**: Strict file type and size limits
4. **Hash Verification**: Cryptographic proof of authenticity
5. **Audit Trail**: Complete verification history

## Performance Tips

1. Use enhanced extraction only when needed
2. Enable batch processing for multiple certificates
3. Configure appropriate file size limits
4. Use Docker for consistent environment

## License

[Your License Here]

## Support

For issues or questions, please open an issue on the repository.