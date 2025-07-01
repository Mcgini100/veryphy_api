#!/usr/bin/env python3
"""
Simple script to clear the existing ledger and start fresh.
"""

import os
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def clear_ledger():
    """Clear the existing ledger file."""
    ledger_path = os.path.join(settings.database_dir, "certificate_ledger.json")
    
    if not os.path.exists(ledger_path):
        print(f"📁 No existing ledger found at: {ledger_path}")
        return True
    
    print(f"🗑️  Found existing ledger: {ledger_path}")
    
    # Confirm deletion
    response = input("Are you sure you want to clear the ledger? This cannot be undone! (y/N): ")
    if response.lower() != 'y':
        print("❌ Ledger clearing cancelled")
        return False
    
    try:
        # Create backup before clearing
        backup_path = f"{ledger_path}.cleared_backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.rename(ledger_path, backup_path)
        
        print(f"✅ Ledger cleared successfully!")
        print(f"📦 Backup saved to: {backup_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error clearing ledger: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Ledger clearing utility")
    print("=" * 30)
    
    success = clear_ledger()
    
    if success:
        print("\n🎉 Ready for fresh migration!")
        print("Run: python scripts/migrate_to_ledger.py --backup")
    else:
        print("\n❌ Ledger clearing failed.")