from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.database import CertificateDatabase
from app.models import ResponseModel

router = APIRouter()

# Dependency to get database instance
async def get_database():
    return CertificateDatabase()

@router.get("/integrity")
async def check_ledger_integrity(db: CertificateDatabase = Depends(get_database)):
    """Check the integrity of the immutable ledger."""
    try:
        integrity_result = await db.validate_integrity()
        return {
            "status": "success",
            "integrity": integrity_result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/stats")
async def get_ledger_stats(db: CertificateDatabase = Depends(get_database)):
    """Get statistics about the immutable ledger."""
    try:
        integrity_result = await db.validate_integrity()
        
        # Get additional stats
        certificates = await db.list_certificates(limit=1000)
        
        active_count = 0
        deleted_count = 0
        
        for cert in certificates['certificates']:
            if cert['data'].get('deleted', False):
                deleted_count += 1
            else:
                active_count += 1
        
        return {
            "status": "success",
            "stats": {
                "total_entries": integrity_result['total_entries'],
                "unique_certificates": integrity_result['unique_certificates'],
                "active_certificates": active_count,
                "deleted_certificates": deleted_count,
                "transaction_types": integrity_result['transaction_types'],
                "last_block_number": integrity_result['last_block_number'],
                "last_hash": integrity_result['last_hash']
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/history/{certificate_number}")
async def get_certificate_history(
    certificate_number: str,
    db: CertificateDatabase = Depends(get_database)
):
    """Get complete transaction history for a certificate."""
    try:
        history = await db.get_certificate_history(certificate_number)
        
        if not history:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        return {
            "status": "success",
            "certificate_number": certificate_number,
            "history": history,
            "total_transactions": len(history)
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.post("/verify/{certificate_number}")
async def record_verification(
    certificate_number: str,
    verification_data: Dict[str, Any],
    db: CertificateDatabase = Depends(get_database)
):
    """Record a verification attempt."""
    try:
        # Check if certificate exists
        existing_cert = await db.get_certificate(certificate_number)
        if not existing_cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        
        # Record the verification
        result = await db.verify_certificate(certificate_number, verification_data)
        
        return {
            "status": "success",
            "message": "Verification recorded successfully",
            "transaction_id": result['transaction_id'],
            "block_number": result['block_number'],
            "verification_data": result['verification_data']
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/entries")
async def list_ledger_entries(
    limit: int = 10,
    offset: int = 0,
    transaction_type: Optional[str] = None,
    db: CertificateDatabase = Depends(get_database)
):
    """List ledger entries with optional filtering."""
    try:
        # Get all entries from the ledger
        entries = await db.ledger._load_ledger()
        
        # Filter by transaction type if specified
        if transaction_type:
            entries = [e for e in entries if e.transaction_type.value == transaction_type.upper()]
        
        # Apply pagination
        total_count = len(entries)
        paginated_entries = entries[offset:offset + limit]
        
        # Convert to dict format for JSON response
        entries_data = []
        for entry in paginated_entries:
            entry_dict = {
                "transaction_id": entry.transaction_id,
                "timestamp": entry.timestamp,
                "transaction_type": entry.transaction_type.value,
                "certificate_number": entry.certificate_number,
                "block_number": entry.block_number,
                "current_hash": entry.current_hash,
                "previous_hash": entry.previous_hash
            }
            entries_data.append(entry_dict)
        
        return {
            "status": "success",
            "entries": entries_data,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@router.get("/validate")
async def validate_ledger_chain(db: CertificateDatabase = Depends(get_database)):
    """Validate the entire ledger chain for integrity."""
    try:
        entries = await db.ledger._load_ledger()
        is_valid = await db.ledger._validate_chain(entries)
        
        validation_details = {
            "is_valid": is_valid,
            "total_entries": len(entries),
            "genesis_hash": db.ledger._genesis_hash,
            "last_hash": entries[-1].current_hash if entries else db.ledger._genesis_hash,
            "validation_timestamp": datetime.now().isoformat()
        }
        
        if not is_valid:
            # Find where the chain breaks
            broken_links = []
            for i in range(1, len(entries)):
                current = entries[i]
                previous = entries[i-1]
                if current.previous_hash != previous.current_hash:
                    broken_links.append({
                        "block_number": current.block_number,
                        "expected_previous": previous.current_hash,
                        "actual_previous": current.previous_hash
                    })
            validation_details["broken_links"] = broken_links
        
        return {
            "status": "success",
            "validation": validation_details
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }