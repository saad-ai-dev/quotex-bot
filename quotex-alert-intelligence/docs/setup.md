# Detailed Setup Guide

## Prerequisites

Before beginning, ensure you have the following installed:

- **Python 3.11+**: [python.org/downloads](https://www.python.org/downloads/)
- **Node.js 18+**: [nodejs.org](https://nodejs.org/)
- **MongoDB 7**: Either local install or via Docker
- **Docker** (optional): [docker.com](https://www.docker.com/)
- **Git**: For cloning the repository

## Backend Setup

### 1. Create a Virtual Environment

```bash
cd backend
python -m venv .venv
```

Activate it:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# From the project root
cp .env.example .env
```

Edit `.env` with your configuration:

```
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=quotex_alerts
CORS_ORIGINS=["http://localhost:3000","chrome-extension://*"]
API_KEY=your-secret-api-key-here
LOG_LEVEL=INFO
```

Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB connection string | `mongodb://localhost:27017` |
| `MONGODB_DB_NAME` | Database name | `quotex_alerts` |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["http://localhost:3000"]` |
| `API_KEY` | API authentication key (leave empty to disable) | empty |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

### 4. Start the Backend

```bash
# Development mode with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify it is running:

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{"status": "ok", "database": "connected", "version": "1.0.0"}
```

API documentation is available at `http://localhost:8000/docs` (Swagger UI).

## Chrome Extension Setup

### 1. Install Dependencies

```bash
cd extension
npm install
```

### 2. Build the Extension

```bash
npm run build
```

This produces the built extension in `extension/dist/`.

### 3. Load in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in the top-right corner)
3. Click "Load unpacked"
4. Select the `extension/dist/` directory
5. The extension icon should appear in your toolbar

### 4. Configure the Extension

1. Click the extension icon to open the popup
2. Go to Settings
3. Verify the backend URL is `http://localhost:8000`
4. Select your preferred market type (LIVE or OTC)
5. Select your preferred expiry profile (1m, 2m, or 3m)

### 5. Development Mode

For extension development with hot reload:

```bash
cd extension
npm run dev
```

This watches for file changes and rebuilds automatically. You will still need to click the refresh button on the extension card in `chrome://extensions/` after each rebuild.

## MongoDB Setup

### Option A: Docker (Recommended)

```bash
# From the project root
docker compose up -d mongodb
```

This starts MongoDB 7 on port 27017 with a persistent volume.

### Option B: Local Installation

Follow the [MongoDB installation guide](https://www.mongodb.com/docs/manual/installation/) for your platform. Ensure the `mongod` service is running on port 27017.

### Option C: MongoDB Atlas (Cloud)

1. Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas)
2. Get your connection string
3. Update `MONGODB_URL` in your `.env` file

### Database Initialization

After MongoDB is running, initialize indexes and seed default settings:

```bash
# From the project root
python scripts/init_indexes.py
python scripts/seed_settings.py
```

Or using Make:

```bash
make init-db
make seed-settings
```

Verify the database:

```bash
# Using mongosh
mongosh quotex_alerts --eval "db.getCollectionNames()"
```

Expected output should include: `signals`, `signal_history`, `settings`, `analytics`.

## Full Stack with Docker Compose

For a complete containerized setup:

```bash
cp .env.example .env
# Edit .env as needed
docker compose up -d
```

This starts both MongoDB and the backend. The backend will be available at `http://localhost:8000`.

To view logs:

```bash
docker compose logs -f backend
```

To stop everything:

```bash
docker compose down
```

To stop and remove volumes (deletes all data):

```bash
docker compose down -v
```

## All-in-One Development Script

The `scripts/dev_run.sh` script handles the full development startup:

```bash
bash scripts/dev_run.sh
```

This will:
1. Check MongoDB connectivity
2. Initialize database indexes
3. Seed default settings (if not already present)
4. Start the FastAPI backend with auto-reload

## Troubleshooting

### MongoDB connection refused

- Ensure MongoDB is running: `systemctl status mongod` or `docker ps`
- Check the port is not in use: `lsof -i :27017`
- Verify `MONGODB_URL` in your `.env` file

### Extension not connecting to backend

- Verify the backend is running: `curl http://localhost:8000/api/v1/health`
- Check CORS origins include `chrome-extension://*` in your `.env`
- Open the extension's service worker console (from `chrome://extensions/`) for error messages

### Python import errors

- Ensure your virtual environment is activated
- Run `pip install -r requirements.txt` again
- Check Python version: `python --version` (must be 3.11+)

### Extension build failures

- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Check Node.js version: `node --version` (must be 18+)
