# Detailed Setup Guide

> **ALERT-ONLY** -- This guide sets up the monitoring and alerting system. No trade execution is configured.

## Prerequisites

Ensure you have the following installed:

| Requirement | Version | Check Command |
|------------|---------|---------------|
| Python | 3.11+ | `python --version` |
| pip | Latest | `pip --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| MongoDB | 7.0 | `mongosh --version` |
| Chrome | Latest | `google-chrome --version` |
| Docker (optional) | 24+ | `docker --version` |

## Step 1: Environment Configuration

```bash
cd quotex-alert-monitoring
cp .env.example .env
```

Edit `.env` with your values:

```env
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=quotex_monitoring
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","chrome-extension://*"]
API_KEY=your-secret-api-key-here
LOG_LEVEL=INFO
```

## Step 2: MongoDB Setup

### Option A: Local MongoDB

```bash
# macOS (Homebrew)
brew install mongodb-community@7.0
brew services start mongodb-community@7.0

# Ubuntu/Debian
sudo systemctl start mongod

# Verify
mongosh --eval "db.adminCommand('ping')"
```

### Option B: Docker MongoDB

```bash
docker-compose up -d mongodb
```

### Initialize Database

```bash
python scripts/init_indexes.py
python scripts/seed_settings.py
```

## Step 3: Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: Open `http://localhost:8000/health` -- should return `{"status": "ok"}`.

API documentation: `http://localhost:8000/docs` (Swagger UI).

## Step 4: Dashboard Setup

```bash
cd dashboard
npm install
npm run dev
```

Opens at `http://localhost:3000` or `http://localhost:5173` depending on the framework.

## Step 5: Chrome Extension Setup

### Build the Extension

```bash
cd extension
npm install
npm run build
```

### Load in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `extension/dist/` directory
5. The "Quotex Alert Monitor" extension should appear

### Verify Extension

1. Click the extension icon in Chrome toolbar
2. The popup should show "Status: Idle" and "Backend: checking"
3. If the backend is running, it should show "Backend: online"

## Step 6: Sound Files (Optional)

Place MP3 alert sounds in `backend/static/sounds/`:

```bash
# Example: generate simple tones with ffmpeg
ffmpeg -f lavfi -i "sine=frequency=800:duration=0.3" -af "afade=t=out:st=0.1:d=0.2" backend/static/sounds/alert-up.mp3
ffmpeg -f lavfi -i "sine=frequency=500:duration=0.3" -af "afade=t=out:st=0.1:d=0.2" backend/static/sounds/alert-down.mp3
ffmpeg -f lavfi -i "sine=frequency=650:duration=0.3" -af "afade=t=out:st=0.1:d=0.2" backend/static/sounds/alert-generic.mp3
```

Without these files, the extension uses synthesized Web Audio API tones.

## Step 7: Start Monitoring

1. Navigate to Quotex in Chrome (`https://quotex.io/` or `https://qxbroker.com/`)
2. Click the extension icon
3. Press the **Start** button to enable monitoring
4. The chart overlay should appear showing "Monitoring" status

## All-in-One Development

Use the Makefile:

```bash
make install      # Install all dependencies
make setup-db     # Init indexes + seed settings
make run-backend  # Start backend (terminal 1)
make run-dashboard  # Start dashboard (terminal 2)
make dev-extension  # Build extension in watch mode (terminal 3)
```

Or the dev script:

```bash
./scripts/dev_run.sh
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend won't start | Check MongoDB is running: `mongosh --eval "db.adminCommand('ping')"` |
| Extension not loading | Ensure `extension/dist/` exists (run `npm run build`) |
| "Backend: offline" in popup | Verify backend is running on port 8000 |
| No chart detected | Quotex may have changed DOM structure; check `QUOTEX_CHART_SELECTORS` in constants |
| No sound playing | Place MP3 files in `backend/static/sounds/` or check browser audio permissions |
| WebSocket disconnecting | Check CORS settings include `chrome-extension://*` |
