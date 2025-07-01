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
        # Create deterministic string representation
        hash_data = {
            "transaction_id": entry_data["transaction_id"],
            "timestamp": entry_data["timestamp"],
            "transaction_type": entry_data["transaction_type"],
            "certificate_number": entry_data["certificate_number"],
            "data": entry_data["data"],
            "previous_hash": entry_data["previous_hash"],
            "block_number": entry_data["block_number"]
        }
        
        # Ensure transaction_type is a string for consistent hashing
        if hasattr(hash_data["transaction_type"], 'value'):
            hash_data["transaction_type"] = hash_data["transaction_type"].value
        
        hash_string = json.dumps(hash_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    async def _load_ledger(self) -> List[LedgerEntry]:
        """Load all entries from the ledger."""
        try:
            with open(self.ledger_path, 'r') as f:
                raw_entries = json.load(f)
            
            entries = []
            for entry_data in raw_entries:
                entries.append(LedgerEntry(**entry_data))
            
            return entries
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    async def _save_ledger(self, entries: List[LedgerEntry]):
        """Save all entries to the ledger."""
        # Create backup before saving
        backup_path = f"{self.ledger_path}.backup"
        if os.path.exists(self.ledger_path):
            with open(self.ledger_path, 'r') as f:
                backup_data = f.read()
            with open(backup_path, 'w') as f:
                f.write(backup_data)
        
        # Convert entries to dict format for JSON serialization
        entries_data = []
        for entry in entries:
            entry_dict = asdict(entry)
            # Ensure transaction_type is stored as string value, not enum representation
            if isinstance(entry_dict['transaction_type'], TransactionType):
                entry_dict['transaction_type'] = entry_dict['transaction_type'].value
            elif hasattr(entry_dict['transaction_type'], 'value'):
                entry_dict['transaction_type'] = entry_dict['transaction_type'].value
            entries_data.append(entry_dict)
        
        # Save new data
        with open(self.ledger_path, 'w') as f:
            json.dump(entries_data, f, indent=2, default=str)
    
    async def _get_last_entry(self) -> Optional[LedgerEntry]:
        """Get the last entry in the ledger."""
        entries = await self._load_ledger()
        return entries[-1] if entries else None
    
    async def _validate_chain(self, entries: List[LedgerEntry]) -> bool:
        """Validate the integrity of the entire ledger chain."""
        if not entries:
            return True
        
        # Check genesis block
        first_entry = entries[0]
        if first_entry.previous_hash != self._genesis_hash:
            return False
        
        # Validate each subsequent entry
        for i in range(1, len(entries)):
            current_entry = entries[i]
            previous_entry = entries[i - 1]
            
            # Check if previous hash matches
            if current_entry.previous_hash != previous_entry.current_hash:
                return False
            
            # Check if block numbers are sequential
            if current_entry.block_number != previous_entry.block_number + 1:
                return False
            
            # Verify hash integrity
            entry_dict = asdict(current_entry)
            expected_hash = self._calculate_hash(entry_dict)
            if current_entry.current_hash != expected_hash:
                return False
        
        return True
    
    async def _create_entry(
        self,
        transaction_type: TransactionType,
        certificate_number: str,
        data: Dict[str, Any]
    ) -> LedgerEntry:
        """Create a new ledger entry."""
        last_entry = await self._get_last_entry()
        
        # Determine previous hash and block number
        if last_entry:
            previous_hash = last_entry.current_hash
            block_number = last_entry.block_number + 1
        else:
            previous_hash = self._genesis_hash
            block_number = 0
        
        # Create entry without hash first
        entry_data = {
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transaction_type": transaction_type.value,
            "certificate_number": certificate_number,
            "data": data,
            "previous_hash": previous_hash,
            "block_number": block_number
        }
        
        # Calculate hash
        current_hash = self._calculate_hash(entry_data)
        entry_data["current_hash"] = current_hash
        
        return LedgerEntry(**entry_data)
    
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
        
        # Find the latest non-deleted entry for this certificate
        latest_entry = None
        for entry in reversed(entries):
            if entry.certificate_number == cert_number:
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
            # Get current certificate
            current = await self.get_certificate(cert_number)
            if not current:
                raise ValueError(f"Certificate {cert_number} not found")
            
            # Increment version and update metadata
            cert_data.update({
                "created_at": current["created_at"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "deleted": False,
                "version": current.get("version", 1) + 1
            })
            
            # Create ledger entry
            entry = await self._create_entry(
                TransactionType.UPDATE,
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
    
    async def delete_certificate(self, cert_number: str) -> Dict[str, Any]:
        """Mark a certificate as deleted (soft delete)."""
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
        
        # Build current state of all certificates
        certificates = {}
        for entry in entries:
            cert_num = entry.certificate_number
            if cert_num not in certificates or entry.block_number > certificates[cert_num]["block_number"]:
                certificates[cert_num] = {
                    "certificate_number": cert_num,
                    "data": entry.data,
                    "block_number": entry.block_number,
                    "transaction_id": entry.transaction_id,
                    "hash": entry.current_hash
                }
        
        # Filter out deleted certificates if needed
        if not include_deleted:
            certificates = {
                k: v for k, v in certificates.items() 
                if not v["data"].get("deleted", False)
            }
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            filtered_certs = {}
            for cert_num, cert_info in certificates.items():
                # Search in certificate number and data
                searchable_text = f"{cert_num} {json.dumps(cert_info['data'])}".lower()
                if search_lower in searchable_text:
                    filtered_certs[cert_num] = cert_info
            certificates = filtered_certs
        
        # Sort by block number (newest first)
        sorted_certs = sorted(
            certificates.values(),
            key=lambda x: x["block_number"],
            reverse=True
        )
        
        # Apply pagination
        total_count = len(sorted_certs)
        paginated_certs = sorted_certs[offset:offset + limit]
        
        return {
            "certificates": paginated_certs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
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
        
        return sorted(history, key=lambda x: x["block_number"])
    
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


# Create a global database instance for backward compatibility
db = CertificateDatabase()