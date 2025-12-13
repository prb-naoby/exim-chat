# EXIM Chat

A production-ready intelligent chatbot system for Export-Import procedures, Standard Operating Procedures (SOP), HS Code verification, and general EXIM knowledge. Powered by Google Gemini AI, Qdrant Vector Database, and Next.js.

## Features

- **SOP Assistant** - Search and query Standard Operating Procedures with hybrid vector + keyword search
- **HS Code Assistant** - Intelligent HS Code lookup and INSW regulation checking  
- **General Assistant** - General EXIM knowledge and internal document queries
- **Cases Q&A** - Historical case-based question answering
- **Automatic Data Sync** - Scheduled ingestion from OneDrive every 30 minutes
- **Admin Dashboard** - User management, ingestion logs, and system monitoring

## Architecture

```
├── api/                # FastAPI Routes
├── frontend/           # Next.js Application (App Router)
│   ├── app/            # Pages and layouts
│   ├── components/     # React Components (Shadcn UI)
│   └── utils/          # Frontend utilities
├── ingestion/          # Data ingestion pipelines
│   ├── cases/          # Cases Q&A ingestion
│   ├── sop/            # SOP document ingestion
│   ├── others/         # General documents ingestion
│   └── insw/           # INSW regulation ingestion
├── modules/            # Python modules
│   ├── scheduler.py    # APScheduler for auto-ingestion
│   ├── sop_chatbot.py  # SOP search logic
│   ├── insw_chatbot.py # HS Code logic
│   └── database.py     # SQLite database manager
├── scripts/            # Manual ingestion scripts
└── main.py             # FastAPI application entry point
```

## Quick Start with Docker

### Prerequisites
- Docker and Docker Compose
- Qdrant instance (local or cloud)
- Google Gemini API Key
- Microsoft Azure App Registration (for OneDrive sync)

### 1. Pull and Run

```bash
# Using the production docker-compose
docker-compose -f docker-compose.dev.yml up -d
```

### 2. Environment Variables

Create a `.env` file with the following variables:

```env
# API Keys
GEMINI_API_KEY=your_gemini_api_key
APP_PASSWORD=your_app_password

# Redis (for session caching)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Qdrant Configuration
INSW_QDRANT_URL=https://your-qdrant-url
INSW_QDRANT_API_KEY=your_qdrant_api_key
INSW_QDRANT_COLLECTION_NAME=insw_regulations
SOP_QDRANT_URL=https://your-qdrant-url
SOP_QDRANT_API_KEY=your_qdrant_api_key
SOP_QDRANT_COLLECTION_NAME=sop_documents
CASES_QDRANT_URL=https://your-qdrant-url
CASES_QDRANT_API_KEY=your_qdrant_api_key
CASES_QDRANT_COLLECTION_NAME=cases_qna
GENERAL_QDRANT_COLLECTION_NAME=general_documents

# LLM Configuration
LLM_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=models/text-embedding-004
VECTOR_SIZE=768
CONFIDENCE_THRESHOLD=0.6

# OneDrive Configuration (for document sync)
ONEDRIVE_DRIVE_ID=your_drive_id
MS_TENANT_ID=your_tenant_id
MS_CLIENT_ID=your_client_id
MS_CLIENT_SECRET=your_client_secret

# Folder Paths (OneDrive paths)
SOP_FOLDER_PATH=AI/SOP
INSW_FOLDER_PATH=AI/INSW
CASES_FOLDER_PATH=AI/Cases
GENERAL_FOLDER_PATH=AI/Others

# Security
JWT_SECRET_KEY=your_jwt_secret
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:3333
- **API Docs**: http://localhost:3333/docs

## Automatic Ingestion (Cron Scheduling)

The application automatically syncs documents from OneDrive every **30 minutes**. Four pipelines run:

| Pipeline | Description | Collection |
|----------|-------------|------------|
| SOP | Standard Operating Procedures (PDF) | `sop_documents` |
| INSW | HS Code Regulations | `insw_regulations` |
| Cases | Historical Q&A from Excel | `cases_qna` |
| General | General EXIM documents | `general_documents` |

### Skip-if-Running Logic
Each pipeline has a lock to prevent overlapping runs. If a pipeline is still running from a previous schedule, the new run is skipped.

### Admin Dashboard
View ingestion logs and trigger manual runs via the admin API:
- `GET /admin/ingestion/logs` - View ingestion history
- `GET /admin/ingestion/status` - Current scheduler status
- `POST /admin/ingestion/run/{pipeline}` - Manually trigger ingestion

## Manual Ingestion

To run ingestion manually (outside Docker):

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Run specific pipeline
python scripts/run_sop_ingestion.py
python scripts/run_insw_ingestion.py
python scripts/run_cases_ingestion.py
python scripts/run_others_ingestion.py
```

## Development Setup

### Backend (Python/FastAPI)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 3333
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

## Default Credentials

On first startup, a default admin user is created:
- **Username**: `admin`
- **Password**: `admin123`

> ⚠️ **Change this immediately in production!**

## API Documentation

Full API documentation is available at `/docs` (Swagger UI) when the backend is running.

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/token` | POST | Login and get JWT token |
| `/chat/sop` | POST | Chat with SOP Assistant |
| `/chat/insw` | POST | Chat with HS Code Assistant |
| `/chat/others` | POST | Chat with General Assistant |
| `/admin/users` | GET | List all users (admin) |
| `/admin/ingestion/logs` | GET | View ingestion history (admin) |

## License

Proprietary - Internal Use Only
