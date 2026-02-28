#!/usr/bin/env python
"""
Database backup and restore utility.
Use this before running tests to protect production data.
"""
import os
import shutil
from datetime import datetime

DB_FILE = 'db.sqlite3'
BACKUP_DIR = 'backups'

def ensure_backup_dir():
    """Create backups directory if it doesn't exist."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"Created {BACKUP_DIR} directory")

def backup():
    """Create a timestamped backup of the database."""
    if not os.path.exists(DB_FILE):
        print(f"Error: {DB_FILE} not found")
        return False
    
    ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f'db_backup_{timestamp}.sqlite3')
    
    try:
        shutil.copy2(DB_FILE, backup_file)
        print(f"✓ Backup created: {backup_file}")
        return True
    except Exception as e:
        print(f"✗ Backup failed: {e}")
        return False

def list_backups():
    """List all available backups."""
    ensure_backup_dir()
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('db_backup_')])
    
    if not backups:
        print("No backups found")
        return
    
    print(f"Available backups ({len(backups)}):")
    for i, backup in enumerate(backups, 1):
        backup_path = os.path.join(BACKUP_DIR, backup)
        size = os.path.getsize(backup_path) / 1024  # KB
        print(f"  {i}. {backup} ({size:.1f} KB)")

def restore(backup_num=0):
    """Restore from the most recent backup, or by number."""
    ensure_backup_dir()
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('db_backup_')])
    
    if not backups:
        print("No backups found")
        return False
    
    # Use most recent if no number specified
    if backup_num == 0:
        backup_file = backups[-1]
    else:
        if backup_num > len(backups) or backup_num < 1:
            print(f"Invalid backup number. Choose 1-{len(backups)}")
            return False
        backup_file = backups[backup_num - 1]
    
    backup_path = os.path.join(BACKUP_DIR, backup_file)
    
    try:
        # Create a safety backup of current DB first
        if os.path.exists(DB_FILE):
            shutil.copy2(DB_FILE, os.path.join(BACKUP_DIR, f'pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sqlite3'))
        
        shutil.copy2(backup_path, DB_FILE)
        print(f"✓ Database restored from: {backup_file}")
        return True
    except Exception as e:
        print(f"✗ Restore failed: {e}")
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python backup_db.py backup         - Create backup")
        print("  python backup_db.py list           - List all backups")
        print("  python backup_db.py restore [num]  - Restore from backup (num optional)")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'backup':
        backup()
    elif command == 'list':
        list_backups()
    elif command == 'restore':
        backup_num = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        restore(backup_num)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
