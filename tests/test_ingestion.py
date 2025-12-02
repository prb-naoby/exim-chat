"""Test INSW ingestion pipeline"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.ingestion_pipeline import IngestionPipeline
from ingestion.onedrive_sync import OneDriveSync
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# Patch OneDriveSync to limit to 1 file
original_get_files = OneDriveSync.get_files_metadata
def limited_get_files(self):
    files = original_get_files(self)
    print(f"Limiting to 1 file (found {len(files)} total)")
    return files[:1]
OneDriveSync.get_files_metadata = limited_get_files

# Create pipeline with Qdrant enabled
print("Creating pipeline with Qdrant connection...")
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
    skip_qdrant_init=False  # Enable Qdrant
)

# Run actual ingestion (not dry run)
print("\nRunning INSW ingestion (1 file, REAL UPSERT)...")
old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
summary = pipeline.sync_and_upsert(last_sync_date=old_date, dry_run=False)
print(f"\nIngestion Summary:")
print(f"- Synced: {summary.get('synced_count', 0)} documents")
print(f"- Upserted: {len(summary.get('upserted', []))} documents")
print(f"- Skipped: {len(summary.get('skipped', []))} documents")
print(f"- Errors: {len(summary.get('errors', []))}")

if summary.get('upserted'):
    print(f"\nUpserted documents:")
    for doc in summary['upserted']:
        status = "NEW" if doc.get('is_new') else "UPDATED"
        print(f"  - HS Code: {doc.get('hs_code')} [{status}]")

if summary.get('errors'):
    print(f"\nFirst error:")
    print(f"  {summary['errors'][0]}")

# Check collection stats
print("\n" + "="*60)
print("Checking Qdrant collection...")
try:
    stats = pipeline.get_stats()
    print(f"Collection: {os.getenv('INSW_QDRANT_COLLECTION_NAME')}")
    print(f"Total points: {stats.get('points_count', 0)}")
    print(f"Total vectors: {stats.get('vectors_count', 0)}")
except Exception as e:
    print(f"Error getting stats: {e}")
