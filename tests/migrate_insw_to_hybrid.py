"""
Migration script to create new INSW collection with hybrid vectors (dense + sparse)
Copies data from existing collection and adds BM25 sparse vectors
Original collection remains unchanged

NOTE: This is a one-time migration script. Run from project root:
    python tests/migrate_insw_to_hybrid.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, NamedVector, NamedSparseVector,
    SparseVectorParams, SparseIndexParams, SparseVector
)
import json

load_dotenv()

# Configuration
qdrant_url = os.getenv("INSW_QDRANT_URL", "http://localhost:6333")
qdrant_api_key = os.getenv("INSW_QDRANT_API_KEY", "")
insw_collection_name = os.getenv("INSW_QDRANT_COLLECTION_NAME", "insw_regulations")
insw_hybrid_collection_name = f"{insw_collection_name}_hybrid"

# Initialize Qdrant client
client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)


def _create_sparse_vector(text: str):
    """Create BM25-like sparse vector from text"""
    words = text.lower().split()
    word_freq = {}
    for word in words:
        if len(word) > 2:  # Skip short words
            word_freq[word] = word_freq.get(word, 0) + 1
    
    indices = []
    values = []
    for word, freq in word_freq.items():
        idx = abs(hash(word)) % (10**6)  # Use hash as index
        indices.append(idx)
        values.append(freq)
    
    return {
        "indices": indices,
        "values": values
    }


def _extract_search_text(payload: dict) -> str:
    """Return the best available text field for sparse vectorization."""
    if not payload:
        return ""

    candidates = [
        payload.get("search_text"),
        payload.get("text"),
        payload.get("content"),
        payload.get("description")
    ]

    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value

    return ""


def create_hybrid_collection(vector_size: int = 3072):
    """Create new collection with hybrid vectors (dense + sparse)"""
    try:
        # Check if collection already exists
        collections = client.get_collections().collections
        exists = any(c.name == insw_hybrid_collection_name for c in collections)
        
        if exists:
            print(f"⚠️ Collection '{insw_hybrid_collection_name}' already exists")
            response = input("Delete and recreate? (y/n): ").lower()
            if response == 'y':
                client.delete_collection(insw_hybrid_collection_name)
                print(f"Deleted '{insw_hybrid_collection_name}'")
            else:
                print("Skipping collection creation")
                return
        
        # Create new collection with hybrid vectors
        client.create_collection(
            collection_name=insw_hybrid_collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            },
            sparse_vectors_config={
                "bm25": SparseVectorParams(
                    index=SparseIndexParams()
                )
            }
        )
        print(f"✓ Created collection '{insw_hybrid_collection_name}' with hybrid vectors")
    
    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        raise


def migrate_to_hybrid():
    """
    Migrate data from existing INSW collection to new hybrid collection
    Original collection remains unchanged
    """
    try:
        # Get original collection info
        print("Fetching collection info...")
        collection_info = client.get_collection(insw_collection_name)
        total_points = collection_info.points_count
        print(f"📊 Found {total_points} points in '{insw_collection_name}'\n")
        
        if total_points == 0:
            print("⚠️ Source collection is empty, nothing to migrate")
            return
        
        # Create new hybrid collection
        create_hybrid_collection()
        
        # Fetch and copy all points with added sparse vectors
        batch_size = 100
        copied_count = 0
        point_id_offset = None  # For scroll pagination
        
        while True:
            if point_id_offset is None:
                print(f"Fetching first batch...")
            else:
                print(f"Fetching next batch after point {point_id_offset}...")
            
            # Scroll through points from original collection with vectors
            points, next_point_id = client.scroll(
                collection_name=insw_collection_name,
                limit=batch_size,
                offset=point_id_offset,
                with_vectors=True
            )
            
            if not points:
                print("No more points to fetch")
                break
            
            print(f"  Got {len(points)} points, creating sparse vectors...")
            # Prepare points for new collection
            new_points = []
            
            for point in points:
                # Extract text from payload
                text = _extract_search_text(point.payload)
                
                if not text:
                    print(f"⚠️ Point {point.id} has no text, skipping")
                    continue
                
                # Extract dense vector from original point
                # point.vector can be: list (direct), dict (named vectors), or NamedVector
                dense_vector = None
                
                if isinstance(point.vector, dict):
                    # If vector is a dict of named vectors, get the first/main vector
                    if "dense" in point.vector:
                        dense_vector = point.vector["dense"]
                    elif "vector" in point.vector:
                        dense_vector = point.vector["vector"]
                    else:
                        # Take the first vector value
                        dense_vector = next(iter(point.vector.values()), None)
                else:
                    # Assume it's a list or direct vector
                    dense_vector = point.vector
                
                # Validate vector
                if not dense_vector:
                    print(f"⚠️ Point {point.id}: dense_vector is None/empty")
                    print(f"   point.vector type: {type(point.vector)}, value: {str(point.vector)[:100]}")
                    continue
                
                if isinstance(dense_vector, list) and len(dense_vector) == 0:
                    print(f"⚠️ Point {point.id} has empty dense vector list, skipping")
                    continue
                
                # Log successful extraction for first few points
                if copied_count < 3:
                    print(f"   ✓ Point {point.id}: vector extracted ({len(dense_vector) if isinstance(dense_vector, list) else 'unknown'} dims)")
                
                # Create sparse vector
                sparse_data = _create_sparse_vector(text)
                sparse_vector = SparseVector(
                    indices=sparse_data["indices"],
                    values=sparse_data["values"]
                )
                
                # Create new point with both vectors
                new_point = PointStruct(
                    id=point.id,
                    vector={
                        "dense": dense_vector,
                        "bm25": sparse_vector
                    },
                    payload=point.payload
                )
                
                new_points.append(new_point)
                copied_count += 1
            
            # Batch upsert to new collection
            if new_points:
                print(f"  Upserting {len(new_points)} points to new collection...")
                try:
                    client.upsert(
                        collection_name=insw_hybrid_collection_name,
                        points=new_points
                    )
                except Exception as e:
                    print(f"⚠️ Error upserting batch: {e}")
            
            print(f"✓ Processed {copied_count}/{total_points} points\n")
            
            # Update offset for next iteration
            point_id_offset = next_point_id
            
            # Break if we got fewer points than batch_size (reached end)
            if len(points) < batch_size:
                break
        
        print(f"\n✅ Migration complete!")
        print(f"   Original collection: '{insw_collection_name}' ({total_points} points) - UNCHANGED")
        print(f"   New hybrid collection: '{insw_hybrid_collection_name}' ({copied_count} points)")
        print(f"   New collection supports hybrid search (dense + sparse BM25)")
        print(f"\n💡 Update your .env to use: INSW_COLLECTION_NAME={insw_hybrid_collection_name}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    print(f"🔄 Starting migration: '{insw_collection_name}' → '{insw_hybrid_collection_name}'...\n")
    
    try:
        print(f"Connecting to Qdrant at {qdrant_url}...")
        
        # Test connection
        collections_list = client.get_collections()
        print(f"✓ Connected! Found {len(collections_list.collections)} collections\n")
        
        # Check if source collection exists
        collection_names = [c.name for c in collections_list.collections]
        if insw_collection_name not in collection_names:
            print(f"❌ Source collection '{insw_collection_name}' not found")
            print(f"Available collections: {collection_names}")
            exit(1)
        
        print(f"✓ Found source collection '{insw_collection_name}'\n")
        
        # Start migration
        migrate_to_hybrid()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
