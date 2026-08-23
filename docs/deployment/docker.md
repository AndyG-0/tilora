# Docker Deployment Reference

This reference covers multi-container Compose setups, network configuration, and volume mounts.

---

## Production Docker Compose (`docker-compose.prod.yml`)

```yaml
services:
  backend:
    image: ghcr.io/andyg-0/tilora-backend:latest
    container_name: tilora-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - CORS_ORIGIN=http://localhost:3000,http://localhost:5173
      - DB_PATH=/app/backend/data/storage.db
      - DASHBOARD_CONFIG_PATH=/app/backend/config/dashboard.yaml
    volumes:
      - backend-storage:/app/backend/data
      - ./backend/config/dashboard.yaml:/app/backend/config/dashboard.yaml:ro
      - ./backend/.env:/app/backend/.env:ro

  frontend:
    image: ghcr.io/andyg-0/tilora-frontend:latest
    container_name: tilora-frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - PORT=3000
      - PUBLIC_API_BASE_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  backend-storage:
```

---

## Multi-Device Host Networking

If accessing Tilora across your home network:

1. In `docker-compose.prod.yml`, set:
   ```yaml
   PUBLIC_API_BASE_URL: http://192.168.1.100:8000
   ```
2. Set `CORS_ORIGIN` on the backend:
   ```yaml
   CORS_ORIGIN: http://192.168.1.100:3000,http://localhost:3000
   ```
3. Restart containers:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
