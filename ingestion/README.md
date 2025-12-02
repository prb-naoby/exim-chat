# Ingestion Module

The ingestion module handles INSW and SOP document synchronization, vectorization, and storage for semantic search.

**Important:** This module does NOT use text splitting. Each document is treated as a single vector point:
- **INSW**: One JSON file = One vector (identified by HS code)
- **SOP**: One PDF file = One vector (identified by document ID)

## Architecture

### INSW Workflow
1. Sync updated JSON documents from OneDrive (checks `lastModifiedDateTime`)
2. Extract HS code from filename or document field
3. Vectorize using concat of `hs_parent_uraian` + `hs_code`
4. Compare with current Qdrant store by HS code
5. Upsert new/updated documents to Qdrant

### SOP Workflow
1. Check OneDrive for updated PDF files
2. Send updated PDFs to OCR service for text extraction
3. Vectorize OCR extracted text
4. Store in Qdrant with document link metadata
5. Use document ID (filename without extension) as unique identifier

## Components

### Shared Components

#### 1. Vectorizer (`vectorizer.py`)
Convert documents to embeddings using Google Gemini:

**Model**: models/text-embedding-004 (768 dimensions)

**INSW**: Vectorizes `hs_parent_uraian` + `hs_code` concatenation  
**SOP**: Vectorizes full OCR extracted text

**Features**:
  - Vectorize individual documents
  - Batch vectorization
  - Query vectorization
  - Cosine similarity calculation

**Usage**:
```python
from ingestion.vectorizer import Vectorizer

vectorizer = Vectorizer(
    model_name='models/text-embedding-004',
    api_key='your_google_ai_studio_api_key'
)

doc_with_embedding = vectorizer.vectorize_document(document)
query_embedding = vectorizer.vectorize_query("search term")
```

#### 2. QdrantStore (`qdrant_store.py`)
Vector database for storing and searching documents:
- **Features**:
  - Create/manage collections
  - Upsert documents by unique ID
  - Semantic search
  - Check document existence
  - Collection statistics

**Usage**:
```python
from ingestion.qdrant_store import QdrantStore

store = QdrantStore(url="http://localhost:6333", api_key="your_key")
store.create_collection(vector_size=384)
store.upsert_document(doc_id, embedding, document)
results = store.search_similar(embedding, top_k=5)
```

### INSW Components (`ingestion/insw/`)

#### 1. OneDriveSync (`insw/onedrive_sync.py`)
Synchronize INSW JSON documents from OneDrive:
- **Features**:
  - List JSON files with metadata
  - Download files only if modified today
  - Extract HS code from filename or document
  - Create search text from `hs_parent_uraian` list

**Usage**:
```python
from ingestion.insw.onedrive_sync import OneDriveSync

sync = OneDriveSync(access_token, folder_id)
documents = sync.sync_documents()  # Get files modified today
```

#### 2. IngestionPipeline (`insw/ingestion_pipeline.py`)
Orchestrates the INSW workflow:
- Coordinates OneDrive sync, vectorization, and Qdrant storage
- Intelligent upsert (only updates changed documents)
- Semantic search interface

**Usage**:
```python
from ingestion.insw.ingestion_pipeline import IngestionPipeline
import os

pipeline = IngestionPipeline(
    tenant_id=os.getenv('MS_TENANT_ID'),
    client_id=os.getenv('MS_CLIENT_ID'),
    client_secret=os.getenv('MS_CLIENT_SECRET'),
    drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
    folder_path=os.getenv('INSW_FOLDER_PATH', 'AI/INSW'),
    qdrant_url=os.getenv('INSW_QDRANT_URL'),
    qdrant_api_key=os.getenv('INSW_QDRANT_API_KEY'),
    embedding_model=os.getenv('EMBEDDING_MODEL', 'models/text-embedding-004'),
    gemini_api_key=os.getenv('GEMINI_API_KEY'),
    vector_size=int(os.getenv('VECTOR_SIZE', '768'))
)

# Sync and upsert
summary = pipeline.sync_and_upsert()

# Dry run - preview what would be updated without making changes
dry_run_summary = pipeline.sync_and_upsert(dry_run=True)
print(f"Dry run: Would upsert {len(dry_run_summary['upserted'])} documents")

# Search
results = pipeline.search("export regulations", top_k=5)
```

### SOP Components (`ingestion/sop/`)

#### 1. SOPOneDriveSync (`sop/onedrive_sync.py`)
Synchronize SOP PDF documents from OneDrive with OCR:
- **Features**:
  - List PDF files with metadata and web URLs
  - Download PDF files as bytes
  - Send to OCR service for text extraction
  - Track lastModifiedDateTime for updates

**Usage**:
```python
from ingestion.sop.onedrive_sync import SOPOneDriveSync

sync = SOPOneDriveSync(
    access_token, 
    folder_id,
    ocr_service_url="http://localhost:5000/ocr",
    ocr_api_key="..."
)
documents = sync.sync_documents()  # Get PDFs modified today with OCR
```

#### 2. SOPIngestionPipeline (`sop/ingestion_pipeline.py`)
Orchestrates the SOP workflow:
- Coordinates OneDrive sync, OCR processing, vectorization, and Qdrant storage
- Uses document link as metadata
- Semantic search for SOP documents

**Usage**:
```python
from ingestion.sop.ingestion_pipeline import SOPIngestionPipeline
import os

pipeline = SOPIngestionPipeline(
    tenant_id=os.getenv('MS_TENANT_ID'),
    client_id=os.getenv('MS_CLIENT_ID'),
    client_secret=os.getenv('MS_CLIENT_SECRET'),
    drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
    folder_path=os.getenv('SOP_FOLDER_PATH', 'AI/SOP'),
    ocr_service_url=os.getenv('OCR_SERVICE_URL'),
    ocr_api_key=os.getenv('OCR_API_KEY'),
    qdrant_url=os.getenv('SOP_QDRANT_URL'),
    qdrant_api_key=os.getenv('SOP_QDRANT_API_KEY'),
    collection_name=os.getenv('SOP_QDRANT_COLLECTION_NAME', 'sop_documents'),
    embedding_model=os.getenv('EMBEDDING_MODEL', 'models/text-embedding-004'),
    gemini_api_key=os.getenv('GEMINI_API_KEY'),
    vector_size=int(os.getenv('VECTOR_SIZE', '768'))
)

# Sync and upsert
summary = pipeline.sync_and_upsert()

# Dry run - preview what would be updated without making changes
dry_run_summary = pipeline.sync_and_upsert(dry_run=True)
print(f"Dry run: Would upsert {len(dry_run_summary['upserted'])} documents")

# Search
results = pipeline.search("customs procedures", top_k=5)
```

pipeline = SOPIngestionPipeline(
    onedrive_access_token="...",
    onedrive_folder_id="...",
    ocr_service_url="http://localhost:5000/ocr",
    ocr_api_key="...",
    qdrant_url="http://localhost:6333",
    qdrant_api_key="..."
)

# Sync and upsert
summary = pipeline.sync_and_upsert()

# Search
results = pipeline.search("approval process", top_k=5)
```

## Installation

Required dependencies:
```bash
pip install sentence-transformers
pip install qdrant-client
pip install requests
pip install python-dotenv
```

## Environment Configuration

Set variables in `.env`:
```bash
# INSW Configuration
INSW_ONEDRIVE_ACCESS_TOKEN=...
INSW_ONEDRIVE_FOLDER_ID=...
INSW_QDRANT_URL=http://localhost:6333
INSW_QDRANT_API_KEY=...
INSW_QDRANT_COLLECTION_NAME=insw_regulations

# SOP Configuration
SOP_ONEDRIVE_ACCESS_TOKEN=...
SOP_ONEDRIVE_FOLDER_ID=...
SOP_QDRANT_URL=http://localhost:6333
SOP_QDRANT_API_KEY=...
SOP_QDRANT_COLLECTION_NAME=sop_documents

# OCR Service
OCR_SERVICE_URL=http://localhost:5000/ocr
OCR_API_KEY=...

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
VECTOR_SIZE=384
```

## Document Structures

### INSW Document (JSON)
```json
{
  "hs_code": "02023000",
  "hs_parent_uraian": [
    "Daging binatang jenis lembu, beku.",
    "- Daging tanpa tulang"
  ],
  "deskripsi": "...",
  "regulations": {...},
  "ref_satuan": [...]
}
```

**Vector ID**: HS code (e.g., "02023000")  
**Search text**: `"Daging binatang jenis lembu, beku. - Daging tanpa tulang 02023000"`

### SOP Document (PDF + OCR)
```json
{
  "filename": "SOP_Export_Process.pdf",
  "file_id": "onedrive_file_id",
  "document_link": "https://...",
  "ocr_text": "Full extracted text...",
  "lastModifiedDateTime": "2025-11-24T10:30:00Z"
}
```

**Vector ID**: Document ID (filename without .pdf)  
**Search text**: Full OCR extracted text

## OCR Service Integration

The SOP pipeline integrates with an external OCR service to extract text from PDF documents.

### OCR Endpoint Specification

**Endpoint**: `POST /ocr`

**Request Format**: `multipart/form-data`

**Parameters**:
- `file` (required): PDF or image file (binary)
- `lang` (optional): Language code, default: `"en"`
- `page_range` (optional): Page range to process, default: `"all"`
- `dpi` (optional): DPI for image conversion, default: `300`
- `min_confidence` (optional): Minimum OCR confidence, default: `0.5`
- `detect_headings` (optional): Detect headings in text, default: `true`
- `force_ocr` (optional): Force OCR even if text layer exists, default: `true`

**Authentication**: 
- Header: `X-API-Key: your_ocr_api_key`

**Response Format**:
```json
{
  "text": "Extracted text content from the PDF...",
  "metadata": {
    "page_count": 5,
    "confidence": 0.95,
    "language": "en"
  }
}
```

**Example Request**:
```bash
POST https://prb-ocr.naoby.me/ocr
Content-Type: multipart/form-data
X-API-Key: your_api_key

file: document.pdf (binary)
lang: en
page_range: all
dpi: 300
min_confidence: 0.5
detect_headings: true
force_ocr: true
```

## Usage Examples

### INSW Search Integration
```python
from ingestion.insw.ingestion_pipeline import IngestionPipeline
import os

pipeline = IngestionPipeline(
    onedrive_access_token=os.getenv("INSW_ONEDRIVE_ACCESS_TOKEN"),
    onedrive_folder_id=os.getenv("INSW_ONEDRIVE_FOLDER_ID"),
    qdrant_url=os.getenv("INSW_QDRANT_URL"),
    qdrant_api_key=os.getenv("INSW_QDRANT_API_KEY")
)

# In chatbot
def search_insw_regulation(user_input):
    results = pipeline.search(user_input, top_k=5)
    
    response = "Found relevant INSW regulations:\n\n"
    for result in results:
        response += f"**HS Code {result['hs_code']}**: "
        response += f"{result['document']['hs_parent_uraian']}\n"
    
    return response
```

### SOP Search Integration
```python
from ingestion.sop.ingestion_pipeline import SOPIngestionPipeline
import os

pipeline = SOPIngestionPipeline(
    onedrive_access_token=os.getenv("SOP_ONEDRIVE_ACCESS_TOKEN"),
    onedrive_folder_id=os.getenv("SOP_ONEDRIVE_FOLDER_ID"),
    ocr_service_url=os.getenv("OCR_SERVICE_URL"),
    ocr_api_key=os.getenv("OCR_API_KEY"),
    qdrant_url=os.getenv("SOP_QDRANT_URL"),
    qdrant_api_key=os.getenv("SOP_QDRANT_API_KEY")
)

# In chatbot
def search_sop_exim(user_input):
    results = pipeline.search(user_input, top_k=5)
    
    response = "Found relevant SOPs:\n\n"
    for result in results:
        doc = result['document']
        response += f"**{doc['filename']}**: "
        response += f"[View Document]({doc['document_link']})\n"
        response += f"Preview: {doc['ocr_text'][:200]}...\n\n"
    
    return response
```

## Performance Considerations

- **No text splitting**: Each document = 1 vector point for fast retrieval
- **OneDrive sync**: Only checks files modified today
- **Vectorization**: Batch processing with configurable batch size
- **Search**: Uses Qdrant's optimized cosine similarity
- **Storage**: Unique IDs prevent duplicates
- **Comparison**: Only upserts if content changed

## Future Enhancements

- [ ] Incremental sync (store last sync timestamp)
- [ ] Batch sync optimization
- [ ] Webhook integration for real-time updates
- [ ] Metadata filtering in search
- [ ] Document versioning
- [ ] Multi-language OCR support
- [ ] Admin dashboard for sync status
