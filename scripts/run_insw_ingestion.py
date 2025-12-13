"""Run INSW ingestion pipeline with logging"""
from ingestion.ingestion_pipeline import IngestionPipeline
import os
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo
import json

load_dotenv()

print("="*80)
print("INSW REGULATION INGESTION")
print("="*80)
print(f"Started at: {datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Configuration
print("Configuration:")
print(f"  Folder: {os.getenv('INSW_FOLDER_PATH')}")
print(f"  Qdrant URL: {os.getenv('INSW_QDRANT_URL')}")
print(f"  Collection: {os.getenv('INSW_QDRANT_COLLECTION_NAME')}")
print(f"  Embedding Model: {os.getenv('EMBEDDING_MODEL')}")
print(f"  Vector Size: {os.getenv('VECTOR_SIZE')}")
print()

# Create pipeline
print("Initializing pipeline...")
try:
    pipeline = IngestionPipeline(
        tenant_id=os.getenv('MS_TENANT_ID'),
        client_id=os.getenv('MS_CLIENT_ID'),
        client_secret=os.getenv('MS_CLIENT_SECRET'),
        drive_id=os.getenv('ONEDRIVE_DRIVE_ID'),
        folder_path=os.getenv('INSW_FOLDER_PATH'),
        qdrant_url=os.getenv('INSW_QDRANT_URL'),
        qdrant_api_key=os.getenv('INSW_QDRANT_API_KEY'),
        embedding_model=os.getenv('EMBEDDING_MODEL'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        vector_size=int(os.getenv('VECTOR_SIZE')),
        skip_qdrant_init=False  # Connect to Qdrant
    )
    print("✓ Pipeline initialized successfully")
    print()
except Exception as e:
    print(f"✗ Failed to initialize pipeline: {e}")
    exit(1)

# Run ingestion
print("Starting ingestion...")
print("Syncing files from OneDrive...")
print()

try:
    # Use old date to sync all files (batch size from .env)
    old_date = datetime(2020, 1, 1, tzinfo=ZoneInfo('UTC'))
    summary = pipeline.sync_and_upsert(last_sync_date=old_date, dry_run=False)  # batch_size from env
    
    print()
    print("="*80)
    print("INGESTION SUMMARY")
    print("="*80)
    print(f"Completed at: {datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print(f"Total synced from OneDrive: {summary.get('synced_count', 0)} documents")
    print(f"Successfully upserted: {len(summary.get('upserted', []))} documents")
    print(f"Skipped (no changes): {len(summary.get('skipped', []))} documents")
    print(f"Errors: {len(summary.get('errors', []))} documents")
    print()
    
    if summary.get('upserted'):
        print("Upserted documents:")
        for i, doc in enumerate(summary['upserted'][:10], 1):  # Show first 10
            status = "NEW" if doc.get('is_new') else "UPDATED"
            print(f"  {i}. HS Code: {doc.get('hs_code')} [{status}]")
            print(f"     Search text: {doc.get('search_text', '')[:80]}...")
        
        if len(summary['upserted']) > 10:
            print(f"  ... and {len(summary['upserted']) - 10} more")
        print()
    
    if summary.get('skipped'):
        print(f"Skipped {len(summary['skipped'])} documents (no changes)")
        print()
    
    if summary.get('errors'):
        print("Errors encountered:")
        for i, error in enumerate(summary['errors'][:5], 1):  # Show first 5
            print(f"  {i}. Document: {error.get('document', 'unknown')}")
            print(f"     Error: {error.get('error', 'unknown')}")
        
        if len(summary['errors']) > 5:
            print(f"  ... and {len(summary['errors']) - 5} more errors")
        print()
    
    # If summary is simple
    log_filename = f"ingestion_log_insw_{datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_filename, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"Detailed log saved to: {log_filename}")
    print()
    
    # Get collection stats
    print("="*80)
    print("QDRANT COLLECTION STATS")
    print("="*80)
    try:
        stats = pipeline.get_stats()
        print(f"Total points in collection: {stats.get('points_count', 0)}")
        print(f"Collection status: {stats.get('status', 'unknown')}")
    except Exception as e:
        print(f"Could not retrieve stats: {e}")
    
    print()
    print("="*80)
    print("INGESTION COMPLETE")
    print("="*80)
    
except Exception as e:
    print()
    print(f"✗ Ingestion failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
