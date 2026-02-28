# Database Backup & Recovery Guide

## Problem Solved
Your database can now be protected from accidental loss when running tests or making changes.

## Quick Start

### 🛡️ Before Running Tests
Always backup first:
```powershell
python backup_db.py backup
```

Then run tests safely:
```powershell
python run_safe_tests.py [test_path]
```

## Commands

### Create a Backup
```powershell
python backup_db.py backup
```
Creates a timestamped backup in `backups/` directory.

### List All Backups
```powershell
python backup_db.py list
```
Shows all available backups with file sizes.

### Restore from Backup
```powershell
# Restore from most recent backup
python backup_db.py restore

# Restore from specific backup (by number)
python backup_db.py restore 2
```

### Run Tests Safely (Recommended)
```powershell
# Automatically backs up, then runs tests
python run_safe_tests.py

# Run specific test
python run_safe_tests.py core.tests.DashboardViewTests

# Run with options
python run_safe_tests.py core.tests -v 2
```

## How It Works

1. **backup_db.py** — Manages database backups and restoration
   - Stores backups in `backups/` folder with timestamps
   - Creates safety snapshot before restore operations

2. **run_safe_tests.py** — Safe test runner
   - Automatically backs up before running any tests
   - Uses `--keepdb` flag to preserve test database between runs
   - Shows clear warnings if anything fails

## Best Practices

✅ **DO:**
- Run `python run_safe_tests.py` instead of `manage.py test`
- Backup before making major database changes
- List backups periodically to ensure data safety

❌ **DON'T:**
- Run tests after deleting the backup folder without first backing up
- Run `manage.py test` directly (use safe runner instead)
- Delete backups without reviewing them first

## Current Status
- Last backup: See `backups/` directory
- Users in system: admin1, user1, u
- All data is protected going forward

## Restore Example
If your database gets wiped again:
```powershell
python backup_db.py list       # See available backups
python backup_db.py restore 1  # Restore backup #1
```

Done! Your data will be restored.
