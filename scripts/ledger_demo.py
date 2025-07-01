#!/usr/bin/env python3
"""
Example usage of the Immutable Ledger for certificate management.

This script demonstrates the key features and benefits of the new immutable ledger
compared to the traditional JSON storage approach.
"""

import asyncio
import json
from datetime import datetime
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import CertificateDatabase, ImmutableLedger


async def demonstrate_ledger_features():
    """Demonstrate key features of the immutable ledger."""
    
    print("🔐 Immutable Ledger Certificate Management Demo")
    print("=" * 50)
    
    # Initialize the database (uses immutable ledger under the hood)
    db = CertificateDatabase()
    
    print("\n1. 📝 Adding a new certificate...")
    
    # Add a certificate
    cert_data = {
        "file_path": "/uploads/cert_001.pdf",
        "file_hash": "a1b2c3d4e5f6...",
        "original_filename": "graduation_certificate.pdf",
        "file_size": 1024567,
        "ocr_data": {
            "text": "Certificate of Graduation\nJohn Doe\nComputer Science\n2024",
            "confidence": 0.95
        },
        "verification_result": {
            "is_valid": True,
            "hash_verified": True,
            "confidence_score": 0.98
        }
    }
    
    result = await db.add_certificate("CERT-2024-001", cert_data)
    print(f"✅ Certificate added:")
    print(f"   Transaction ID: {result['transaction_id']}")
    print(f"   Block Number: {result['block_number']}")
    print(f"   Hash: {result['hash'][:16]}...")
    
    print("\n2. 🔍 Retrieving the certificate...")
    retrieved = await db.get_certificate("CERT-2024-001")
    print(f"✅ Certificate retrieved:")
    print(f"   Created: {retrieved['created_at']}")
    print(f"   Version: {retrieved['version']}")
    print(f"   Deleted: {retrieved['deleted']}")
    
    print("\n3. ✏️  Updating the certificate...")
    
    # Update the certificate
    updated_data = cert_data.copy()
    updated_data["verification_result"]["confidence_score"] = 0.99
    updated_data["notes"] = "Updated after manual review"
    
    update_result = await db.update_certificate("CERT-2024-001", updated_data)
    print(f"✅ Certificate updated:")
    print(f"   New Transaction ID: {update_result['transaction_id']}")
    print(f"   New Block Number: {update_result['block_number']}")
    print(f"   New Version: {update_result['data']['version']}")
    
    print("\n4. 📚 Viewing certificate history...")
    
    # Get complete history
    history = await db.get_certificate_history("CERT-2024-001")
    print(f"✅ Certificate has {len(history)} transactions:")
    for i, transaction in enumerate(history, 1):
        print(f"   {i}. {transaction['transaction_type']} at block {transaction['block_number']}")
        print(f"      Time: {transaction['timestamp']}")
        print(f"      Hash: {transaction['hash'][:16]}...")
    
    print("\n5. ✅ Recording a verification attempt...")
    
    # Record verification
    verification_data = {
        "verified_by": "inspector_123",
        "verification_method": "hash_comparison",
        "result": "valid",
        "confidence": 0.97,
        "notes": "Automated verification passed"
    }
    
    verify_result = await db.verify_certificate("CERT-2024-001", verification_data)
    print(f"✅ Verification recorded:")
    print(f"   Transaction ID: {verify_result['transaction_id']}")
    print(f"   Block Number: {verify_result['block_number']}")
    
    print("\n6. 🗑️  Soft deleting the certificate...")
    
    # Delete (soft delete - maintains history)
    delete_result = await db.delete_certificate("CERT-2024-001")
    print(f"✅ Certificate soft deleted:")
    print(f"   Transaction ID: {delete_result['transaction_id']}")
    print(f"   Block Number: {delete_result['block_number']}")
    
    # Try to retrieve deleted certificate
    deleted_cert = await db.get_certificate("CERT-2024-001")
    print(f"   Retrieved after deletion: {deleted_cert is None}")
    
    print("\n7. 📊 Checking ledger integrity...")
    
    # Validate entire ledger
    integrity = await db.validate_integrity()
    print(f"✅ Ledger integrity check:")
    print(f"   Valid: {integrity['is_valid']}")
    print(f"   Total entries: {integrity['total_entries']}")
    print(f"   Unique certificates: {integrity['unique_certificates']}")
    print(f"   Transaction types: {integrity['transaction_types']}")
    
    print("\n8. 📋 Listing all certificates...")
    
    # List certificates (including deleted for demo)
    all_certs = await db.ledger.list_certificates(limit=10, include_deleted=True)
    print(f"✅ Found {all_certs['total_count']} certificates:")
    for cert in all_certs['certificates']:
        status = "DELETED" if cert['data'].get('deleted') else "ACTIVE"
        print(f"   - {cert['certificate_number']} [{status}] at block {cert['block_number']}")


async def demonstrate_immutability():
    """Demonstrate the immutability and tamper-detection features."""
    
    print("\n" + "=" * 50)
    print("🛡️  Immutability and Tamper Detection Demo")
    print("=" * 50)
    
    # Get direct access to the ledger
    ledger = ImmutableLedger()
    
    print("\n1. 🔗 Checking chain integrity...")
    
    # Load all entries and validate chain
    entries = await ledger._load_ledger()
    is_valid = await ledger._validate_chain(entries)
    
    print(f"✅ Chain validation: {is_valid}")
    print(f"   Total blocks: {len(entries)}")
    
    if entries:
        print(f"   Genesis hash: {ledger._genesis_hash[:16]}...")
        print(f"   Latest hash: {entries[-1].current_hash[:16]}...")
        
        # Show chain structure
        print(f"\n2. 🧱 Block chain structure:")
        for i, entry in enumerate(entries[-3:]):  # Show last 3 blocks
            print(f"   Block {entry.block_number}:")
            print(f"     Previous: {entry.previous_hash[:16]}...")
            print(f"     Current:  {entry.current_hash[:16]}...")
            print(f"     Type: {entry.transaction_type.value}")
    
    print(f"\n3. 🔍 Demonstrating tamper detection...")
    
    # This would be detected if someone tried to modify the ledger file
    print("   ✅ Any modification to historical entries would:")
    print("      - Break the hash chain")
    print("      - Fail integrity validation")
    print("      - Be immediately detectable")
    print("      - Preserve audit trail")


async def compare_with_json_storage():
    """Compare benefits of immutable ledger vs JSON storage."""
    
    print("\n" + "=" * 50)
    print("📊 Immutable Ledger vs JSON Storage Comparison")
    print("=" * 50)
    
    comparison = {
        "Feature": [
            "Data Integrity",
            "Audit Trail",
            "Tamper Detection",
            "Historical Versions",
            "Concurrent Access",
            "Data Recovery",
            "Verification Logging",
            "Compliance Ready",
            "Rollback Protection",
            "Chain of Custody"
        ],
        "JSON Storage": [
            "❌ No protection",
            "❌ Not maintained",
            "❌ No detection",
            "❌ Overwrites data",
            "⚠️  Basic locking",
            "⚠️  Backup dependent",
            "❌ Not supported",
            "❌ Limited",
            "❌ No protection",
            "❌ Not tracked"
        ],
        "Immutable Ledger": [
            "✅ Cryptographic hashes",
            "✅ Complete history",
            "✅ Automatic detection",
            "✅ All versions preserved",
            "✅ Thread-safe operations",
            "✅ Point-in-time recovery",
            "✅ Built-in verification log",
            "✅ Audit-ready format",
            "✅ Cryptographic protection",
            "✅ Full chain of custody"
        ]
    }
    
    # Print comparison table
    for i, feature in enumerate(comparison["Feature"]):
        print(f"\n{feature}:")
        print(f"  JSON:   {comparison['JSON Storage'][i]}")
        print(f"  Ledger: {comparison['Immutable Ledger'][i]}")
    
    print(f"\n💡 Key Benefits of Immutable Ledger:")
    print(f"   🔐 Cryptographic integrity protection")
    print(f"   📚 Complete audit trail for compliance")
    print(f"   🕵️ Automatic tamper detection")
    print(f"   🔄 Point-in-time recovery capabilities")
    print(f"   ⚡ Thread-safe concurrent operations")
    print(f"   📋 Built-in verification logging")
    print(f"   🛡️  Protection against data corruption")
    print(f"   📊 Rich metadata and statistics")


async def main():
    """Run all demonstrations."""
    try:
        await demonstrate_ledger_features()
        await demonstrate_immutability()
        await compare_with_json_storage()
        
        print(f"\n" + "=" * 50)
        print("🎉 Demo completed successfully!")
        print("=" * 50)
        print("The immutable ledger provides enterprise-grade")
        print("certificate management with full audit trails,")
        print("tamper detection, and compliance-ready logging.")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())