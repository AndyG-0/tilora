# Updates, Backups & Maintenance

This guide explains how to perform software updates, backup and restore your configuration and database, and manage Tilora services.

---

## In-App One-Click Update

Native systemd installations support one-click updates directly from the dashboard:

1. Navigate to **Settings → Software update**.
2. Tap **Check for updates** to compare your current version against GitHub releases.
3. If an update is available, tap **Update now**.
4. The backend runs the fast-forward update script, rebuilds the frontend, restarts both services, and the dashboard automatically reconnects when ready.

---

## Standalone CLI Update

You can also run updates from an SSH shell:

```bash
bash ~/tilora/deploy/update.sh
```

---

## Backup & Restore

### What to Back Up
Tilora stores all persistent state in two directories:
- **`backend/data/storage.db`** (or `backend/storage.db`): SQLite database containing users, sessions, personal widget settings, and cached indexes.
- **`backend/config/dashboard.yaml`**: Your custom widget definitions.
- **`backend/.env`**: Secret keys and environment configuration.

### Creating a Snapshot
```bash
# Create a timestamped backup archive
tar -czvf ~/tilora-backup-$(date +%Y%m%d).tar.gz \
  -C ~/tilora backend/config/dashboard.yaml backend/.env backend/data/storage.db
```

### Restoring a Snapshot
```bash
sudo systemctl stop tilora-backend tilora-frontend
tar -xzvf tilora-backup-YYYYMMDD.tar.gz -C ~/tilora/
sudo systemctl start tilora-backend tilora-frontend
```
