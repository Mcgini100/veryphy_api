import json
import os
from typing import Dict, Optional, List, Any
from datetime import datetime
import asyncio
from pathlib import Path

from app.config import settings

class CertificateDatabase:
    """Thread-safe JSON-based certificate database with async support."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(
            settings.database_dir, 
            settings.database_file
        )
        self._lock = asyncio.Lock()
        self._ensure_database()
    
    def _ensure_database(self):
        """Ensure database file exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w') as f:
                json.dump({}, f)
    
    async def _load_database(self) -> Dict[str, Any]:
        """Load database from JSON file."""
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    async def _save_database(self, data: Dict[str, Any]):
        """Save database to JSON file."""
        # Create backup before saving
        backup_path = f"{self.db_path}.backup"
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                backup_data = f.read()
            with open(backup_path, 'w') as f:
                f.write(backup_data)
        
        # Save new data
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    async def add_certificate(
        self, 
        cert_number: str, 
        cert_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add or update certificate in database."""
        async with self._lock:
            db = await self._load_database()
            
            # Preserve existing data if updating
            existing = db.get(cert_number, {})
            verification_history = existing.get('verification_history', [])
            
            # Update certificate data
            db[cert_number] = {
                **cert_data,
                'last_updated': datetime.now().isoformat(),
                'created_at': existing.get('created_at', datetime.now().isoformat()),
                'verification_history': verification_history
            }
            
            await self._save_database(db)
            return db[cert_number]
    
    async def get_certificate(self, cert_number: str) -> Optional[Dict[str, Any]]:
        """Retrieve certificate from database."""
        async with self._lock:
            db = await self._load_database()
            return db.get(cert_number)
    
    async def get_all_certificates(
        self, 
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Retrieve all certificates with pagination."""
        async with self._lock:
            db = await self._load_database()
            cert_list = [
                {'certificate_number': k, **v} 
                for k, v in db.items()
            ]
            
            # Sort by last_updated descending
            cert_list.sort(
                key=lambda x: x.get('last_updated', ''), 
                reverse=True
            )
            
            # Apply pagination
            if limit:
                return cert_list[offset:offset + limit]
            return cert_list[offset:]
    
    async def search_certificates(
        self, 
        query: str,
        fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search certificates by query string."""
        async with self._lock:
            db = await self._load_database()
            results = []
            
            search_fields = fields or [
                'student_name', 'certificate_number', 
                'degree_name', 'faculty_name'
            ]
            
            query_lower = query.lower()
            for cert_num, cert_data in db.items():
                for field in search_fields:
                    value = cert_data.get(field, '')
                    if isinstance(value, str) and query_lower in value.lower():
                        results.append({
                            'certificate_number': cert_num,
                            **cert_data
                        })
                        break
            
            return results
    
    async def verify_certificate_hash(
        self, 
        cert_number: str, 
        provided_hash: str
    ) -> bool:
        """Verify certificate hash against stored hash."""
        cert = await self.get_certificate(cert_number)
        if cert and 'hash' in cert:
            return cert['hash'] == provided_hash
        return False
    
    async def add_verification_record(
        self, 
        cert_number: str, 
        verification_result: Dict[str, Any]
    ):
        """Add verification record to certificate history."""
        async with self._lock:
            db = await self._load_database()
            
            if cert_number in db:
                if 'verification_history' not in db[cert_number]:
                    db[cert_number]['verification_history'] = []
                
                db[cert_number]['verification_history'].append({
                    'timestamp': datetime.now().isoformat(),
                    **verification_result
                })
                
                # Keep only last 100 verification records
                db[cert_number]['verification_history'] = \
                    db[cert_number]['verification_history'][-100:]
                
                db[cert_number]['last_verified'] = datetime.now().isoformat()
                await self._save_database(db)
    
    async def get_verification_history(
        self, 
        cert_number: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get verification history for a certificate."""
        cert = await self.get_certificate(cert_number)
        if cert and 'verification_history' in cert:
            history = cert['verification_history']
            if limit:
                return history[-limit:]
            return history
        return []
    
    async def delete_certificate(self, cert_number: str) -> bool:
        """Delete a certificate from the database."""
        async with self._lock:
            db = await self._load_database()
            if cert_number in db:
                del db[cert_number]
                await self._save_database(db)
                return True
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        async with self._lock:
            db = await self._load_database()
            
            total_certificates = len(db)
            total_verifications = sum(
                len(cert.get('verification_history', [])) 
                for cert in db.values()
            )
            
            # Count by verification status
            status_counts = {}
            for cert in db.values():
                status = cert.get('verification_status', 'UNKNOWN')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                'total_certificates': total_certificates,
                'total_verifications': total_verifications,
                'status_distribution': status_counts,
                'database_size_bytes': os.path.getsize(self.db_path),
                'last_updated': datetime.now().isoformat()
            }

# Global database instance
db = CertificateDatabase()