#!/usr/bin/env python3
"""
Migration script to convert existing JSON database to immutable ledger format.

Usage:
    python migrate_to_ledger.py [--backup] [--old-db-path path/to/old.json]
"""

import json
import os
import sys
import argparse
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.database import CertificateDatabase, ImmutableLedger


class DatabaseMigrator:
    """Handles migration from JSON database to immutable ledger."""
    
    def __init__(self, old_db_path: str, backup: bool = True):
        self.old_db_path = old_db_path
        self.backup = backup
        self.new_ledger = ImmutableLedger()
    
    def load_old_database(self) -> Dict[str, Any]:
        """Load the old JSON database."""
        try:
            with open(self.old_db_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Old database file not found: {self.old_db_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Error reading old database: {e}")
            return {}
    
    def create_backup(self, old_data: Dict[str, Any]):
        """Create a backup of the old database."""
        if not self.backup:
            return
        
        backup_path = f"{self.old_db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            with open(backup_path, 'w') as f:
                json.dump(old_data, f, indent=2, default=str)
            print(f"✅ Backup created: {backup_path}")
        except Exception as e:
            print(f"⚠️  Warning: Could not create backup: {e}")
    
    async def migrate_certificates(self, old_data: Dict[str, Any], force_update: bool = False) -> Dict[str, Any]:
        """Migrate certificates from old format to new ledger."""
        migration_stats = {
            "total_certificates": len(old_data),
            "migrated": 0,
            "updated": 0,
            "failed": 0,
            "errors": []
        }
        
        print(f"🔄 Migrating {len(old_data)} certificates...")
        
        for cert_number, cert_data in old_data.items():
            try:
                # Prepare certificate data for migration
                migrated_data = self.prepare_certificate_data(cert_data)
                
                # Check if certificate already exists
                existing = await self.new_ledger.get_certificate(cert_number)
                
                if existing and not force_update:
                    print(f"⏭️  Skipped certificate: {cert_number} (already exists)")
                    continue
                elif existing and force_update:
                    # Update existing certificate
                    result = await self.new_ledger.update_certificate(cert_number, migrated_data)
                    migration_stats["updated"] += 1
                    print(f"🔄 Updated certificate: {cert_number} (Block: {result['block_number']})")
                else:
                    # Add new certificate
                    result = await self.new_ledger.add_certificate(cert_number, migrated_data)
                    migration_stats["migrated"] += 1
                    print(f"✅ Migrated certificate: {cert_number} (Block: {result['block_number']})")
                
            except Exception as e:
                migration_stats["failed"] += 1
                error_msg = f"Failed to migrate {cert_number}: {str(e)}"
                migration_stats["errors"].append(error_msg)
                print(f"❌ {error_msg}")
        
        return migration_stats
    
    def prepare_certificate_data(self, cert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare certificate data for the new ledger format."""
        # Create a copy to avoid modifying original
        prepared_data = cert_data.copy()
        
        # Ensure required fields exist
        current_time = datetime.now(timezone.utc).isoformat()
        
        if "created_at" not in prepared_data:
            prepared_data["created_at"] = current_time
        
        if "updated_at" not in prepared_data:
            prepared_data["updated_at"] = current_time
        
        if "deleted" not in prepared_data:
            prepared_data["deleted"] = False
        
        if "version" not in prepared_data:
            prepared_data["version"] = 1
        
        # Add migration metadata
        prepared_data["migrated_from_json"] = True
        prepared_data["migration_timestamp"] = current_time
        
        return prepared_data
    
    async def verify_migration(self, old_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that migration was successful."""
        verification_stats = {
            "total_old": len(old_data),
            "total_new": 0,
            "matching": 0,
            "missing": [],
            "mismatched": []
        }
        
        print("🔍 Verifying migration...")
        
        # Get all certificates from new ledger
        new_certificates = await self.new_ledger.list_certificates(limit=10000)
        verification_stats["total_new"] = len(new_certificates["certificates"])
        
        # Create lookup for new certificates
        new_cert_lookup = {
            cert["certificate_number"]: cert["data"] 
            for cert in new_certificates["certificates"]
        }
        
        # Check each old certificate
        for cert_number, old_cert_data in old_data.items():
            if cert_number in new_cert_lookup:
                new_cert_data = new_cert_lookup[cert_number]
                
                # Check key fields (ignoring migration metadata)
                key_fields = ["file_path", "file_hash", "ocr_data", "verification_result"]
                matches = True
                
                for field in key_fields:
                    if field in old_cert_data:
                        if old_cert_data[field] != new_cert_data.get(field):
                            matches = False
                            break
                
                if matches:
                    verification_stats["matching"] += 1
                else:
                    verification_stats["mismatched"].append(cert_number)
            else:
                verification_stats["missing"].append(cert_number)
        
        return verification_stats
    
    async def repair_existing_ledger(self):
        """Repair existing ledger file that might have enum serialization issues."""
        try:
            if not os.path.exists(self.new_ledger.ledger_path):
                return
            
            print("🔧 Checking and repairing existing ledger...")
            
            with open(self.new_ledger.ledger_path, 'r') as f:
                raw_data = json.load(f)
            
            # Fix transaction_type enum serialization issues
            fixed_data = []
            for entry_data in raw_data:
                if 'transaction_type' in entry_data:
                    tx_type = entry_data['transaction_type']
                    if isinstance(tx_type, str) and tx_type.startswith("TransactionType."):
                        entry_data['transaction_type'] = tx_type.split(".")[-1]
                fixed_data.append(entry_data)
            
            # Save repaired data
            with open(self.new_ledger.ledger_path, 'w') as f:
                json.dump(fixed_data, f, indent=2, default=str)
            
            print("✅ Ledger repaired successfully")
            
        except Exception as e:
            print(f"⚠️  Could not repair ledger: {e}")

    async def run_migration(self) -> bool:
        """Run the complete migration process."""
        print("🚀 Starting migration from JSON database to immutable ledger...")
        print(f"📁 Old database: {self.old_db_path}")
        print(f"📁 New ledger: {self.new_ledger.ledger_path}")
        print()
        
        # Load old database
        old_data = self.load_old_database()
        if not old_data:
            print("❌ No data to migrate or failed to load old database")
            return False
        
        # Create backup
        self.create_backup(old_data)
        
        # Repair existing ledger if it exists
        await self.repair_existing_ledger()
        
        # Check if ledger already has data
        existing_integrity = await self.new_ledger.validate_ledger_integrity()
        force_update = False
        
        if existing_integrity["total_entries"] > 0:
            print(f"⚠️  Warning: Ledger already contains {existing_integrity['total_entries']} entries")
            print("Options:")
            print("  y - Add new certificates only (skip existing)")
            print("  u - Update existing certificates with new data")
            print("  n - Cancel migration")
            response = input("Choose option (y/u/N): ").lower()
            
            if response == 'n' or response == '':
                print("❌ Migration cancelled")
                return False
            elif response == 'u':
                force_update = True
                print("🔄 Will update existing certificates")
            else:
                print("➕ Will add new certificates only")
        
        # Migrate certificates
        migration_stats = await self.migrate_certificates(old_data, force_update)
        
        # Verify migration
        verification_stats = await self.verify_migration(old_data)
        
        # Print results
        print("\n" + "="*50)
        print("📊 MIGRATION SUMMARY")
        print("="*50)
        print(f"Total certificates in old DB: {migration_stats['total_certificates']}")
        print(f"Successfully migrated: {migration_stats['migrated']}")
        print(f"Successfully updated: {migration_stats['updated']}")
        print(f"Failed migrations: {migration_stats['failed']}")
        
        if migration_stats['errors']:
            print(f"\n❌ Errors encountered:")
            for error in migration_stats['errors'][:5]:  # Show first 5 errors
                print(f"   - {error}")
            if len(migration_stats['errors']) > 5:
                print(f"   ... and {len(migration_stats['errors']) - 5} more errors")
        
        print(f"\n🔍 VERIFICATION RESULTS:")
        print(f"Old database certificates: {verification_stats['total_old']}")
        print(f"New ledger certificates: {verification_stats['total_new']}")
        print(f"Matching certificates: {verification_stats['matching']}")
        
        if verification_stats['missing']:
            print(f"Missing certificates: {len(verification_stats['missing'])}")
            
        if verification_stats['mismatched']:
            print(f"Mismatched certificates: {len(verification_stats['mismatched'])}")
        
        # Final ledger integrity check
        final_integrity = await self.new_ledger.validate_ledger_integrity()
        print(f"\n🔐 LEDGER INTEGRITY:")
        print(f"Ledger is valid: {final_integrity['is_valid']}")
        print(f"Total entries: {final_integrity['total_entries']}")
        print(f"Unique certificates: {final_integrity['unique_certificates']}")
        print(f"Transaction types: {final_integrity['transaction_types']}")
        
        success = (
            migration_stats['failed'] == 0 and
            final_integrity['is_valid'] and
            verification_stats['matching'] == verification_stats['total_old']
        )
        
        if success:
            print("\n✅ Migration completed successfully!")
        else:
            print("\n⚠️  Migration completed with issues. Please review the results above.")
        
        return success


async def main():
    """Main function to run the migration."""
    parser = argparse.ArgumentParser(description="Migrate JSON database to immutable ledger")
    parser.add_argument(
        "--old-db-path", 
        default=os.path.join(settings.database_dir, settings.database_file),
        help="Path to the old JSON database file"
    )
    parser.add_argument(
        "--backup", 
        action="store_true", 
        default=True,
        help="Create backup of old database (default: True)"
    )
    parser.add_argument(
        "--no-backup", 
        action="store_false", 
        dest="backup",
        help="Skip creating backup of old database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually doing it"
    )
    parser.add_argument(
        "--clear-ledger",
        action="store_true",
        help="Clear existing ledger before migration"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print(f"📁 Would migrate from: {args.old_db_path}")
        
        # Load and analyze old database
        try:
            with open(args.old_db_path, 'r') as f:
                old_data = json.load(f)
            
            print(f"📊 Found {len(old_data)} certificates to migrate:")
            for i, (cert_num, cert_data) in enumerate(old_data.items()):
                if i < 5:  # Show first 5
                    print(f"   - {cert_num}: {list(cert_data.keys())}")
                elif i == 5:
                    print(f"   ... and {len(old_data) - 5} more certificates")
                    break
                    
        except Exception as e:
            print(f"❌ Error reading old database: {e}")
        
        return
    
    # Confirm migration
    print("⚠️  This will migrate your JSON database to an immutable ledger format.")
    print("   The old database will be backed up but the new format is different.")
    print("   Make sure you understand the implications before proceeding.")
    print()
    
    if not os.path.exists(args.old_db_path):
        print(f"❌ Old database file not found: {args.old_db_path}")
        return
    
    # Clear ledger if requested
    if args.clear_ledger:
        migrator = DatabaseMigrator(args.old_db_path, args.backup)
        if os.path.exists(migrator.new_ledger.ledger_path):
            backup_path = f"{migrator.new_ledger.ledger_path}.cleared_backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(migrator.new_ledger.ledger_path, backup_path)
            print(f"🗑️  Cleared existing ledger (backed up to: {backup_path})")
    
    response = input("Continue with migration? (y/N): ")
    if response.lower() != 'y':
        print("❌ Migration cancelled")
        return
    
    # Run migration
    migrator = DatabaseMigrator(args.old_db_path, args.backup)
    success = await migrator.run_migration()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("   Your certificates are now stored in an immutable ledger.")
        print("   You can verify the integrity anytime using the /ledger/integrity endpoint.")
    else:
        print("\n❌ Migration failed or completed with errors.")
        print("   Please review the output above and fix any issues.")
    
    return success


if __name__ == "__main__":
    # Run the migration
    success = asyncio.run(main())