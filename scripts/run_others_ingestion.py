
"""Run Others (AI/Others) ingestion pipeline"""
from ingestion.others.others_ingestion_pipeline import OthersIngestionPipeline
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json

load_dotenv()

print("="*80)
print("OTHERS INGESTION PIPELINE")
print("="*80)
print(f"Started at: {datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Configuration
folder = os.getenv('OTHERS_FOLDER_PATH', 'AI/Others')
collection = os.getenv('OTHERS_QDRANT_COLLECTION_NAME', 'others_documents')
print("Configuration:")
print(f"  Folder: {folder}")
print(f"  Collection: {collection}")
print(f"  Embedding Model: {os.getenv('EMBEDDING_MODEL')}")
print()

try:
    pipeline = OthersIngestionPipeline(
        tenant_id=os.getenv('MS_TENANT_ID'),
        client_id=os.getenv('MS_CLIENT_ID'),
        client_secret=os.getenv('MS_CLIENT_SECRET'),
        drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
        folder_path=folder,
        qdrant_url=os.getenv('SOP_QDRANT_URL'), # Use same Qdrant URL
        qdrant_api_key=os.getenv('SOP_QDRANT_API_KEY'),
        qdrant_collection_name=collection,
        embedding_model=os.getenv('EMBEDDING_MODEL'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        vector_size=int(os.getenv('VECTOR_SIZE')),
        skip_qdrant_init=False
    )
    
    # Collection init (ensure exists)
    if pipeline.qdrant_client:
         pipeline._init_collection(int(os.getenv('VECTOR_SIZE')))

    print("[OK] Pipeline initialized successfully")
    
    # Run ingestion
    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    summary = pipeline.sync_and_upsert(last_sync_date=old_date, dry_run=False)
    
    # Log summary
    print(json.dumps(summary, indent=2))
    
except Exception as e:
    print(f"[ERROR] Failed: {e}")
    import traceback
    traceback.print_exc()
