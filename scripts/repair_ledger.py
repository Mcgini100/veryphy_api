#!/usr/bin/env python3
"""
Quick repair script to fix enum serialization issues in existing ledger.
"""

import json
import os
import sys
from datetime import datetime

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


def repair_ledger():
    """Repair existing ledger file with enum serialization issues."""
    ledger_path = os.path.join(settings.database_dir, "certificate_ledger.json")
    
    if not os.path.exists(ledger_path):
        print(f"❌ Ledger file not found: {ledger_path}")
        return False
    
    print(f"🔧 Repairing ledger file: {ledger_path}")
    
    try:
        # Create backup first
        backup_path = f"{ledger_path}.repair_backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with open(ledger_path, 'r') as f:
            backup_data = f.read()
        with open(backup_path, 'w') as f:
            f.write(backup_data)
        print(f"✅ Backup created: {backup_path}")
        
        # Load and fix the data
        with open(ledger_path, 'r') as f:
            raw_data = json.load(f)
        
        print(f"📊 Found {len(raw_data)} entries to repair")
        
        # Fix transaction_type enum serialization issues
        fixed_data = []
        fixed_count = 0
        
        for entry_data in raw_data:
            if 'transaction_type' in entry_data:
                tx_type = entry_data['transaction_type']
                if isinstance(tx_type, str) and tx_type.startswith("TransactionType."):
                    # Fix the enum format
                    entry_data['transaction_type'] = tx_type.split(".")[-1]
                    fixed_count += 1
            fixed_data.append(entry_data)
        
        # Save repaired data
        with open(ledger_path, 'w') as f:
            json.dump(fixed_data, f, indent=2, default=str)
        
        print(f"✅ Ledger repaired successfully!")
        print(f"   - Fixed {fixed_count} transaction type entries")
        print(f"   - Total entries: {len(fixed_data)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error repairing ledger: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Starting ledger repair...")
    success = repair_ledger()
    
    if success:
        print("\n🎉 Repair completed successfully!")
        print("You can now run the migration script again.")
    else:
        print("\n❌ Repair failed. Please check the error messages above.")