# Running with Docker & Docker Compose

Tilora is published as multi-architecture container images (`linux/amd64` and `linux/arm64`) to the GitHub Container Registry (GHCR) on every release. You can also build directly from source using the bundled Compose files.

---

## Option 1: Pull Pre-Built Images (Recommended)

Use `docker-compose.prod.yml` to run the official pre-built images:

```bash
# 1. Download production docker compose file
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/docker-compose.prod.yml -o docker-compose.prod.yml

# 2. Setup configuration files
mkdir -p backend/config
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/backend/.env.example -o backend/.env
curl -fsSL https://raw.githubusercontent.com/AndyG-0/tilora/main/backend/config/dashboard.example.yaml -o backend/config/dashboard.yaml

# 3. Start containers
docker compose -f docker-compose.prod.yml up -d
```

Access the dashboard at `http://<host-ip>:3000`.

---

## Option 2: Build From Source

If developing locally or building custom images:

```bash
# 1. Clone the repository
git clone https://github.com/AndyG-0/tilora.git
cd tilora

# 2. Create environment and config files
cp backend/.env.example backend/.env
cp backend/config/dashboard.example.yaml backend/config/dashboard.yaml

# 3. Start with docker compose
PUBLIC_API_BASE_URL=http://<host-ip>:8000 CORS_ORIGIN=http://<host-ip>:3000 docker compose up --build -d
```

---

## Key Environment Variables

| Variable | Service | Description | Default |
|---|---|---|---|
| `PUBLIC_API_BASE_URL` | Frontend | The backend API URL accessible by the *user's browser* (e.g. `http://192.168.1.50:8000`) | `http://localhost:8000` |
| `CORS_ORIGIN` | Backend | Comma-separated list of allowed frontend origins | `http://localhost:3000,http://localhost:5173` |
| `DB_PATH` | Backend | Path to SQLite database file | `data/storage.db` |
| `DASHBOARD_CONFIG_PATH`| Backend | Path to YAML layout file | `config/dashboard.yaml` |

> [!TIP]
> `PUBLIC_API_BASE_URL` is evaluated dynamically in the user's browser, not baked in at image build time. If you move Tilora to a new host or change ports, update the environment variable in your `docker-compose.yml` and restart the container (`docker compose up -d`).

---

## Persistent Storage & Volumes

- **`backend-storage`**: Named volume storing `storage.db` (user profiles, sessions, network integrations, AI history, cache).
- **`./backend/config/dashboard.yaml`**: Bind-mounted into the backend container for custom widget declarations.
- **`./backend/.env`**: Bind-mounted for API keys and environment configuration.

---

## Upgrading Docker Deployments

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```
