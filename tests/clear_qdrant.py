"""Clear Qdrant collection to start fresh"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.qdrant_store import QdrantStore
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("CLEAR QDRANT COLLECTION")
print("="*80)

qdrant = QdrantStore(
    url=os.getenv('INSW_QDRANT_URL'),
    api_key=os.getenv('INSW_QDRANT_API_KEY'),
    collection_name=os.getenv('INSW_QDRANT_COLLECTION_NAME'),
    vector_size=int(os.getenv('VECTOR_SIZE'))
)

# Get current stats
stats = qdrant.get_collection_stats()
print(f"\nCurrent collection: {stats['collection_name']}")
print(f"Current points: {stats['points_count']}")

# Ask for confirmation
response = input(f"\nAre you sure you want to DELETE all {stats['points_count']} points? (yes/no): ")

if response.lower() == 'yes':
    print("\nDeleting collection...")
    try:
        qdrant.client.delete_collection(collection_name=stats['collection_name'])
        print("✓ Collection deleted")
        
        print("\nRecreating collection...")
        qdrant.create_collection()
        print("✓ Collection recreated (empty)")
        
        # Verify
        new_stats = qdrant.get_collection_stats()
        print(f"\nNew collection points: {new_stats['points_count']}")
        print("\nCollection is now empty and ready for fresh ingestion!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
else:
    print("\nCancelled. Collection unchanged.")
