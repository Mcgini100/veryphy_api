import json
import hashlib
import os
from typing import Dict, Optional, List, Any, Union
from datetime import datetime, timezone
import asyncio
from pathlib import Path
import uuid
from dataclasses import dataclass, asdict
from enum import Enum

from app.config import settings


class TransactionType(Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VERIFY = "VERIFY"


@dataclass
class LedgerEntry:
    """Immutable ledger entry representing a single transaction."""
    transaction_id: str
    timestamp: str
    transaction_type: TransactionType
    certificate_number: str
    data: Dict[str, Any]
    previous_hash: str
    current_hash: str
    block_number: int
    
    def __post_init__(self):
        if isinstance(self.transaction_type, str):
            # Handle both "CREATE" and "TransactionType.CREATE" formats
            if self.transaction_type.startswith("TransactionType."):
                enum_value = self.transaction_type.split(".")[-1]
            else:
                enum_value = self.transaction_type
            self.transaction_type = TransactionType(enum_value)


class ImmutableLedger:
    """
    Mock implementation of an immutable ledger for certificate storage.
    
    Features:
    - Immutable entries with cryptographic hashing
    - Chain validation
    - Audit trails
    - Point-in-time recovery
    - Tamper detection
    """
    
    def __init__(self, ledger_path: Optional[str] = None):
        self.ledger_path = ledger_path or os.path.join(
            settings.database_dir, 
            "certificate_ledger.json"
        )
        self.ledger_dir = settings.database_dir
        self._lock = asyncio.Lock()
        self._ensure_ledger()
        self._genesis_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    
    def _ensure_ledger(self):
        """Ensure ledger file and directory exists."""
        Path(self.ledger_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.ledger_dir).mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.ledger_path):
            with open(self.ledger_path, 'w') as f:
                json.dump([], f)
    
    def _calculate_hash(self, entry_data: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of entry data."""
        serialized = json.dumps(entry_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    async def _load_ledger(self) -> List[LedgerEntry]:
        """Load all ledger entries from file."""
        try:
            with open(self.ledger_path, 'r') as f:
                entries_data = json.load(f)
            
            entries = []
            for entry_data in entries_data:
                try:
                    # Handle both old and new formats
                    if isinstance(entry_data.get('transaction_type'), str):
                        entry_data['transaction_type'] = TransactionType(entry_data['transaction_type'])
                    
                    entries.append(LedgerEntry(**entry_data))
                except (TypeError, ValueError) as e:
                    print(f"Warning: Skipping invalid ledger entry: {e}")
                    continue
            
            return entries
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    async def _save_ledger(self, entries: List[LedgerEntry]):
        """Save all ledger entries to file."""
        entries_data = []
        for entry in entries:
            entry_dict = asdict(entry)
            # Ensure transaction_type is serialized as string
            entry_dict['transaction_type'] = entry.transaction_type.value
            entries_data.append(entry_dict)
        
        with open(self.ledger_path, 'w') as f:
            json.dump(entries_data, f, indent=2, default=str)
    
    async def _create_entry(
        self, 
        transaction_type: TransactionType,
        cert_number: str,
        data: Dict[str, Any]
    ) -> LedgerEntry:
        """Create a new ledger entry."""
        entries = await self._load_ledger()
        
        # Calculate previous hash
        previous_hash = entries[-1].current_hash if entries else self._genesis_hash
        
        # Create entry data for hashing
        entry_data = {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transaction_type": transaction_type.value,
            "certificate_number": cert_number,
            "data": data,
            "previous_hash": previous_hash,
            "block_number": len(entries)
        }
        
        # Calculate current hash
        current_hash = self._calculate_hash(entry_data)
        entry_data["current_hash"] = current_hash
        
        return LedgerEntry(**entry_data)
    
    async def _validate_chain(self, entries: List[LedgerEntry]) -> bool:
        """Validate the integrity of the ledger chain."""
        if not entries:
            return True
        
        # Check genesis
        if entries[0].previous_hash != self._genesis_hash:
            return False
        
        # Validate each entry
        for i, entry in enumerate(entries):
            # Check block number sequence
            if entry.block_number != i:
                return False
            
            # Check hash chain
            if i > 0:
                if entry.previous_hash != entries[i-1].current_hash:
                    return False
            
            # Recalculate and verify current hash
            entry_data = {
                "transaction_id": entry.transaction_id,
                "timestamp": entry.timestamp,
                "transaction_type": entry.transaction_type.value,
                "certificate_number": entry.certificate_number,
                "data": entry.data,
                "previous_hash": entry.previous_hash,
                "block_number": entry.block_number
            }
            
            expected_hash = self._calculate_hash(entry_data)
            if entry.current_hash != expected_hash:
                return False
        
        return True
    
    async def add_certificate(
        self, 
        cert_number: str, 
        cert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a new certificate to the ledger."""
        
        async with self._lock:
            # Check if certificate already exists
            existing = await self.get_certificate(cert_number)
            if existing and not existing.get("deleted", False):
                raise ValueError(f"Certificate {cert_number} already exists")
            
            # Add metadata
            cert_data.update({
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "deleted": False,
                "version": 1
            })
            
            # Create ledger entry
            entry = await self._create_entry(
                TransactionType.CREATE,
                cert_number,
                cert_data
            )
            
            # Load existing entries and append new one
            entries = await self._load_ledger()
            entries.append(entry)
            
            # Validate chain before saving
            if not await self._validate_chain(entries):
                raise ValueError("Ledger chain validation failed")
            
            # Save updated ledger
            await self._save_ledger(entries)
            
            return {
                "transaction_id": entry.transaction_id,
                "certificate_number": cert_number,
                "block_number": entry.block_number,
                "hash": entry.current_hash,
                "data": cert_data
            }
    
    async def get_certificate(self, cert_number: str) -> Optional[Dict[str, Any]]:
        """Get the latest version of a certificate."""
        entries = await self._load_ledger()
        
        # ✅ FIX: Find the latest CREATE or UPDATE entry for this certificate (not VERIFY)
        latest_entry = None
        for entry in reversed(entries):
            if (entry.certificate_number == cert_number and 
                entry.transaction_type in [TransactionType.CREATE, TransactionType.UPDATE]):
                latest_entry = entry
                break
        
        if not latest_entry or latest_entry.data.get("deleted", False):
            return None
        
        return latest_entry.data
    
    async def update_certificate(
        self, 
        cert_number: str, 
        cert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing certificate."""
        
        async with self._lock:
            # Get current certificate data
            current = await self.get_certificate(cert_number)
            if not current:
                raise ValueError(f"Certificate {cert_number} not found")
            
            # ✅ FIX: Preserve original created_at and increment version
            updated_data = cert_data.copy()
            updated_data.update({
                "created_at": current.get("created_at", datetime.now(timezone.utc).isoformat()),  # Preserve original
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "deleted": False,
                "version": current.get("version", 1) + 1
            })
            
            # Create ledger entry
            entry = await self._create_entry(
                TransactionType.UPDATE,
                cert_number,
                updated_data
            )
            
            # Load existing entries and append new one
            entries = await self._load_ledger()
            entries.append(entry)
            
            # Validate chain before saving
            if not await self._validate_chain(entries):
                raise ValueError("Ledger chain validation failed")
            
            # Save updated ledger
            await self._save_ledger(entries)
            
            return {
                "transaction_id": entry.transaction_id,
                "certificate_number": cert_number,
                "block_number": entry.block_number,
                "hash": entry.current_hash,
                "data": updated_data
            }
    
    async def delete_certificate(self, cert_number: str) -> Dict[str, Any]:
        """Soft delete a certificate (maintains history)."""
        
        async with self._lock:
            # Get current certificate
            current = await self.get_certificate(cert_number)
            if not current:
                raise ValueError(f"Certificate {cert_number} not found")
            
            # Mark as deleted
            delete_data = current.copy()
            delete_data.update({
                "deleted": True,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "version": current.get("version", 1) + 1
            })
            
            # Create ledger entry
            entry = await self._create_entry(
                TransactionType.DELETE,
                cert_number,
                delete_data
            )
            
            # Load existing entries and append new one
            entries = await self._load_ledger()
            entries.append(entry)
            
            # Validate chain before saving
            if not await self._validate_chain(entries):
                raise ValueError("Ledger chain validation failed")
            
            # Save updated ledger
            await self._save_ledger(entries)
            
            return {
                "transaction_id": entry.transaction_id,
                "certificate_number": cert_number,
                "block_number": entry.block_number,
                "hash": entry.current_hash,
                "deleted": True
            }
    
    async def list_certificates(
        self, 
        limit: int = 10, 
        offset: int = 0, 
        search: Optional[str] = None,
        include_deleted: bool = False
    ) -> Dict[str, Any]:
        """List certificates with pagination and search."""
        entries = await self._load_ledger()
        
        # Get latest version of each certificate
        certificates = {}
        for entry in entries:
            if entry.transaction_type in [TransactionType.CREATE, TransactionType.UPDATE, TransactionType.DELETE]:
                certificates[entry.certificate_number] = {
                    "certificate_number": entry.certificate_number,
                    "data": entry.data,
                    "block_number": entry.block_number,
                    "transaction_id": entry.transaction_id,
                    "timestamp": entry.timestamp
                }
        
        # Filter certificates
        filtered_certs = []
        for cert in certificates.values():
            # Skip deleted unless specifically requested
            if not include_deleted and cert["data"].get("deleted", False):
                continue
            
            # Apply search filter
            if search:
                search_text = json.dumps(cert["data"], default=str).lower()
                if search.lower() not in search_text:
                    continue
            
            filtered_certs.append(cert)
        
        # Sort by timestamp (newest first)
        filtered_certs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Apply pagination
        total_count = len(filtered_certs)
        paginated_certs = filtered_certs[offset:offset + limit]
        
        return {
            "certificates": paginated_certs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
    
    async def get_certificate_history(self, cert_number: str) -> List[Dict[str, Any]]:
        """Get complete transaction history for a certificate."""
        entries = await self._load_ledger()
        
        history = []
        for entry in entries:
            if entry.certificate_number == cert_number:
                history.append({
                    "transaction_id": entry.transaction_id,
                    "timestamp": entry.timestamp,
                    "transaction_type": entry.transaction_type.value,
                    "block_number": entry.block_number,
                    "hash": entry.current_hash,
                    "data": entry.data
                })
        
        return history
    
    async def add_verification_record(
        self, 
        cert_number: str, 
        verification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a verification record for an existing certificate."""
        
        async with self._lock:
            # Check if certificate exists (using the fixed get_certificate method)
            existing_cert = await self.get_certificate(cert_number)
            if not existing_cert:
                raise ValueError(f"Certificate {cert_number} not found")
            
            # Create verification entry
            verify_data = {
                "verification_timestamp": datetime.now(timezone.utc).isoformat(),
                "verification_result": verification_data,
                "verified_by": verification_data.get("verified_by", "system")
            }
            
            entry = await self._create_entry(
                TransactionType.VERIFY,
                cert_number,
                verify_data
            )
            
            # Load existing entries and append new one
            entries = await self._load_ledger()
            entries.append(entry)
            
            # Validate chain before saving
            if not await self._validate_chain(entries):
                raise ValueError("Ledger chain validation failed")
            
            # Save updated ledger
            await self._save_ledger(entries)
            
            return {
                "transaction_id": entry.transaction_id,
                "certificate_number": cert_number,
                "block_number": entry.block_number,
                "hash": entry.current_hash,
                "verification_data": verify_data
            }
    
    async def verify_certificate(
        self, 
        cert_number: str, 
        verification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record a certificate verification attempt."""
        
        async with self._lock:
            # Create verification entry
            verify_data = {
                "verification_timestamp": datetime.now(timezone.utc).isoformat(),
                "verification_result": verification_data,
                "verified_by": verification_data.get("verified_by", "system")
            }
            
            entry = await self._create_entry(
                TransactionType.VERIFY,
                cert_number,
                verify_data
            )
            
            # Load existing entries and append new one
            entries = await self._load_ledger()
            entries.append(entry)
            
            # Validate chain before saving
            if not await self._validate_chain(entries):
                raise ValueError("Ledger chain validation failed")
            
            # Save updated ledger
            await self._save_ledger(entries)
            
            return {
                "transaction_id": entry.transaction_id,
                "certificate_number": cert_number,
                "block_number": entry.block_number,
                "hash": entry.current_hash,
                "verification_data": verify_data
            }
    
    async def validate_ledger_integrity(self) -> Dict[str, Any]:
        """Validate the entire ledger chain integrity."""
        entries = await self._load_ledger()
        
        is_valid = await self._validate_chain(entries)
        
        # Additional statistics
        total_entries = len(entries)
        certificate_count = len(set(entry.certificate_number for entry in entries))
        transaction_types = {}
        
        for entry in entries:
            tx_type = entry.transaction_type.value
            transaction_types[tx_type] = transaction_types.get(tx_type, 0) + 1
        
        return {
            "is_valid": is_valid,
            "total_entries": total_entries,
            "unique_certificates": certificate_count,
            "transaction_types": transaction_types,
            "last_block_number": entries[-1].block_number if entries else -1,
            "last_hash": entries[-1].current_hash if entries else self._genesis_hash
        }


# Compatibility wrapper to match the original CertificateDatabase interface
class CertificateDatabase:
    """Wrapper to maintain compatibility with existing code."""
    
    def __init__(self, db_path: Optional[str] = None):
        # Initialize the immutable ledger instead of JSON database
        self.ledger = ImmutableLedger(db_path)
    
    async def add_certificate(
        self, 
        cert_number: str, 
        cert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add or update certificate in the ledger."""
        try:
            # Try to add as new certificate
            return await self.ledger.add_certificate(cert_number, cert_data)
        except ValueError as e:
            if "already exists" in str(e):
                # Update existing certificate
                return await self.ledger.update_certificate(cert_number, cert_data)
            raise
    
    async def get_certificate(self, cert_number: str) -> Optional[Dict[str, Any]]:
        """Get certificate from the ledger."""
        return await self.ledger.get_certificate(cert_number)
    
    async def update_certificate(
        self, 
        cert_number: str, 
        cert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update certificate in the ledger."""
        return await self.ledger.update_certificate(cert_number, cert_data)
    
    async def delete_certificate(self, cert_number: str) -> Dict[str, Any]:
        """Delete certificate from the ledger."""
        return await self.ledger.delete_certificate(cert_number)
    
    async def list_certificates(
        self, 
        limit: int = 10, 
        offset: int = 0, 
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """List certificates from the ledger."""
        return await self.ledger.list_certificates(limit, offset, search)
    
    # ✅ FIX: Add the missing add_verification_record method
    async def add_verification_record(
        self, 
        cert_number: str, 
        verification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a verification record for an existing certificate."""
        return await self.ledger.add_verification_record(cert_number, verification_data)
    
    # Additional methods specific to the ledger
    async def get_certificate_history(self, cert_number: str) -> List[Dict[str, Any]]:
        """Get complete transaction history for a certificate."""
        return await self.ledger.get_certificate_history(cert_number)
    
    async def verify_certificate(
        self, 
        cert_number: str, 
        verification_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record a certificate verification attempt."""
        return await self.ledger.verify_certificate(cert_number, verification_data)
    
    async def validate_integrity(self) -> Dict[str, Any]:
        """Validate the entire ledger integrity."""
        return await self.ledger.validate_ledger_integrity()
    
    # Additional methods for backward compatibility with existing routes
    async def get_all_certificates(
        self, 
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all certificates with pagination."""
        result = await self.ledger.list_certificates(
            limit=limit or 100, 
            offset=offset
        )
        return [cert['data'] for cert in result['certificates']]
    
    async def search_certificates(self, search_term: str) -> List[Dict[str, Any]]:
        """Search certificates by term."""
        result = await self.ledger.list_certificates(
            limit=1000, 
            search=search_term
        )
        return [cert['data'] for cert in result['certificates']]
    
    async def get_verification_history(
        self, 
        cert_number: str, 
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get verification history for a certificate."""
        history = await self.ledger.get_certificate_history(cert_number)
        
        # Filter only verification transactions and format for compatibility
        verification_history = []
        for entry in history:
            if entry['transaction_type'] == 'VERIFY':
                verification_history.append({
                    'timestamp': entry['timestamp'],
                    'verification_data': entry['data'],
                    'transaction_id': entry['transaction_id']
                })
        
        if limit:
            verification_history = verification_history[:limit]
        
        return verification_history

    # ✅ FIX: Additional helper methods for better compatibility
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            integrity = await self.validate_integrity()
            
            # Get all certificates to calculate status distribution
            all_certs = await self.get_all_certificates(limit=1000)
            
            status_distribution = {}
            for cert in all_certs:
                status = cert.get('verification_status', 'UNKNOWN')
                status_distribution[status] = status_distribution.get(status, 0) + 1
            
            return {
                'total_certificates': len(all_certs),
                'total_verifications': integrity.get('total_entries', 0),
                'status_distribution': status_distribution,
                'database_size_bytes': 0,  # Placeholder for compatibility
                'unique_certificates': integrity.get('unique_certificates', 0)
            }
        except Exception as e:
            return {
                'total_certificates': 0,
                'total_verifications': 0,
                'status_distribution': {},
                'database_size_bytes': 0,
                'error': str(e)
            }


# Create a global database instance for backward compatibility
db = CertificateDatabase()