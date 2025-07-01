# Certificate Verification API

A robust REST API for certificate verification using hash embedding and OCR extraction with **enterprise-grade immutable ledger storage**.

## 🆕 **Latest Updates**

### **Immutable Ledger Implementation (v2.0)**
- **🔐 Cryptographic Integrity**: Each certificate transaction is cryptographically linked
- **📚 Complete Audit Trail**: Full history of all certificate operations
- **🛡️ Tamper Detection**: Automatic detection of any data modification attempts
- **⚡ Chain Validation**: Real-time integrity verification of the entire ledger
- **🔄 Point-in-Time Recovery**: Access any historical state of certificates
- **📋 Verification Logging**: Built-in audit logging for compliance

## Features

### **Core Verification**
- **Dual Verification**: Hash-based cryptographic verification with OCR fallback
- **Hash Embedding**: Embed SHA-256 hashes with error correction into certificates
- **Enhanced Extraction**: Multiple strategies for hash extraction from degraded images
- **Watermarking**: Add visible watermarks and security patterns
- **Batch Processing**: Verify multiple certificates simultaneously

### **Enterprise Storage**
- **🔐 Immutable Ledger**: Blockchain-inspired certificate storage
- **📊 Audit Trails**: Complete transaction history for compliance
- **🔍 Integrity Validation**: Cryptographic proof of data authenticity
- **⚡ Real-time Monitoring**: Live ledger health and statistics
- **🛡️ Tamper Protection**: Automatic detection of unauthorized changes

### **API Features**
- **Confidence Scoring**: Reliability metrics for verification results
- **REST API**: Full-featured API with comprehensive endpoints
- **Real-time Health**: Advanced health monitoring with ledger status
- **Statistics**: Detailed analytics and reporting

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

# Check API health (now includes ledger status)
curl http://localhost:8000/api/v1/health

# Check ledger integrity
curl http://localhost:8000/api/v1/ledger/integrity
```

### Manual Installation

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install tesseract-ocr python3-pip

# Install Python dependencies
pip install -r requirements.txt

# Run migration (if upgrading from JSON storage)
python scripts/migrate_to_ledger.py --backup

# Run the API
uvicorn app.main:app --reload
```

## API Endpoints

### Health & Monitoring
```bash
# Basic health check
GET /api/v1/health

# Ledger integrity check
GET /api/v1/ledger/integrity

# Detailed ledger statistics
GET /api/v1/ledger/stats

# Validate entire ledger chain
GET /api/v1/ledger/validate
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

#### Get Certificate History (🆕 New)
```bash
GET /api/v1/ledger/history/{certificate_number}
```

#### Delete Certificate (Soft Delete)
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

#### Record Verification (🆕 New)
```bash
POST /api/v1/ledger/verify/{certificate_number}
Content-Type: application/json

{
  "verified_by": "inspector_123",
  "verification_method": "hash_comparison",
  "result": "valid",
  "confidence": 0.97
}
```

#### Batch Verification
```bash
POST /api/v1/verify/batch
Content-Type: multipart/form-data

Parameters:
- files: Multiple certificate images
- expected_hashes: JSON object mapping filenames to hashes
```

### Ledger Operations (🆕 New)

#### List Ledger Entries
```bash
GET /api/v1/ledger/entries?limit=10&offset=0&transaction_type=CREATE
```

#### Validate Chain Integrity
```bash
GET /api/v1/ledger/validate
```

## Testing Your Implementation

### PowerShell Commands (Windows)
```powershell
# Test basic health
curl http://localhost:8000/api/v1/health

# Check ledger integrity
curl http://localhost:8000/api/v1/ledger/integrity

# Get ledger statistics
curl http://localhost:8000/api/v1/ledger/stats

# List certificates
curl http://localhost:8000/api/v1/certificates

# Get certificate history
curl http://localhost:8000/api/v1/ledger/history/BSc-12700
```

### Bash Commands (Linux/Mac)
```bash
# Run comprehensive test
python test_api.py

# Quick health check
curl http://localhost:8000/api/v1/health | jq .

# Check ledger integrity
curl http://localhost:8000/api/v1/ledger/integrity | jq .
```

## Migration from JSON Storage

If upgrading from the previous JSON-based storage:

```bash
# Backup and migrate existing data
python scripts/migrate_to_ledger.py --backup

# Clear ledger and start fresh (if needed)
python scripts/clear_ledger.py

# Run demo to test functionality
python scripts/ledger_demo.py
```

## Configuration

Key settings in `.env`:

```env
# API Configuration
APP_NAME="Certificate Verification API"
APP_VERSION="2.0.0"
DEBUG=false

# Ledger Configuration (🆕 New)
LEDGER_FILE="certificate_ledger.json"
ENABLE_INTEGRITY_CHECKS=true
AUTO_BACKUP_LEDGER=true
MAX_LEDGER_SIZE_MB=100

# Processing Settings
HASH_BLOCK_SIZE=12
USE_CHECKSUM=true
MIN_ENTROPY_THRESHOLD=10
DATA_MATCH_THRESHOLD=0.8

# File Limits
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=.png,.jpg,.jpeg,.pdf
```

## Verification Status Codes

- **VERIFIED**: Hash matches exactly
- **VERIFIED_BY_DATA**: Hash failed but OCR data matches database
- **FAILED**: Hash mismatch
- **CORRUPTED_HASH**: Low entropy detected in hash
- **NO_HASH**: No embedded hash found
- **UNKNOWN**: Verification not performed

## Architecture (Updated)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   REST API      │────▶│  Verification   │────▶│ Immutable       │
│   (FastAPI)     │     │   Service       │     │ Ledger          │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                         │
                               ├─────────────────┐       │
                               ▼                 ▼       ▼
                        ┌─────────────┐   ┌─────────────┐ ┌─────────────┐
                        │ Hash Service│   │ OCR Service │ │ Chain       │
                        └─────────────┘   └─────────────┘ │ Validation  │
                                                          └─────────────┘
```

## Immutable Ledger Benefits

| Feature | JSON Storage | Immutable Ledger |
|---------|-------------|------------------|
| **Data Protection** | ❌ No protection | ✅ Cryptographic hashing |
| **Audit Trail** | ❌ Not maintained | ✅ Complete history |
| **Tamper Detection** | ❌ No detection | ✅ Automatic detection |
| **Compliance Ready** | ⚠️ Limited | ✅ Enterprise-grade |
| **Version Control** | ❌ Overwrites data | ✅ All versions preserved |
| **Chain of Custody** | ❌ Not tracked | ✅ Full chain tracked |
| **Rollback Protection** | ❌ No protection | ✅ Immutable entries |
| **Concurrent Access** | ⚠️ Basic locking | ✅ Thread-safe operations |

## Docker Deployment

The included `Dockerfile` and `docker-compose.yml` provide:
- Automated Tesseract OCR installation
- Volume mapping for data persistence
- Health checks with ledger validation
- Automatic restart on failure
- Ledger backup automation

## Security & Compliance

### Enhanced Security Features
1. **Immutable Storage**: Once written, data cannot be modified
2. **Cryptographic Integrity**: SHA-256 hashing of all transactions
3. **Chain Validation**: Real-time verification of data integrity
4. **Audit Logging**: Complete trail for compliance requirements
5. **Tamper Detection**: Immediate notification of unauthorized changes

### Production Checklist
- [ ] Change `SECRET_KEY` in production
- [ ] Configure CORS allowed origins
- [ ] Set up automated ledger backups
- [ ] Enable integrity monitoring
- [ ] Configure log retention policies
- [ ] Set up automated alerts for integrity failures

## Monitoring & Maintenance

### Health Monitoring
```bash
# Check overall system health
curl http://localhost:8000/api/v1/health

# Monitor ledger integrity
curl http://localhost:8000/api/v1/ledger/integrity

# Get performance statistics
curl http://localhost:8000/api/v1/ledger/stats
```

### Maintenance Scripts
```bash
# Validate entire ledger
python scripts/validate_ledger.py

# Create ledger backup
python scripts/backup_ledger.py

# Repair corrupted ledger (if needed)
python scripts/repair_ledger.py
```

## Troubleshooting

### Common Issues

#### Migration Problems
```bash
# If migration fails
python scripts/repair_ledger.py
python scripts/migrate_to_ledger.py --clear-ledger --backup
```

#### Integrity Validation Failures
```bash
# Check ledger integrity
curl http://localhost:8000/api/v1/ledger/validate

# Repair if needed
python scripts/repair_ledger.py
```

#### Performance Issues
- Monitor ledger size: Target < 100MB for optimal performance
- Regular backups: Automated backup every 24 hours
- Chain validation: Runs automatically on startup

### Getting Help

1. Check the logs: `tail -f logs/app.log`
2. Validate ledger: `curl http://localhost:8000/api/v1/ledger/validate`
3. Run diagnostics: `python scripts/ledger_demo.py`

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

---

**🎉 Your certificates are now secured with enterprise-grade immutable storage!**

For detailed implementation examples, see `scripts/ledger_demo.py`