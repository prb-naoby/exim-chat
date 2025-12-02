"""
Test script for INSW document ingestion
Tests vectorization and search functionality without OneDrive/Qdrant
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from ingestion.vectorizer import Vectorizer

def test_local_ingestion():
    """Test ingestion with local JSON file"""
    
    print("=" * 60)
    print("INSW Document Ingestion Test")
    print("=" * 60)
    
    # Load sample document
    sample_file = Path(__file__).parent.parent / "ingestion" / "sample_data" / "02023000.json"
    
    if not sample_file.exists():
        print(f"❌ Sample file not found: {sample_file}")
        return
    
    with open(sample_file, 'r', encoding='utf-8') as f:
        document = json.load(f)
    
    print(f"\n✓ Loaded document: {sample_file.name}")
    print(f"  HS Code: {document.get('hs_code')}")
    print(f"  Description: {document.get('deskripsi')}")
    
    # Initialize vectorizer
    print("\n📊 Initializing vectorizer...")
    vectorizer = Vectorizer()
    print("✓ Vectorizer loaded")
    
    # Vectorize document
    print("\n🔄 Vectorizing document...")
    vectorized_doc = vectorizer.vectorize_document(document)
    
    print(f"✓ Document vectorized")
    print(f"  Search text: {vectorized_doc['search_text']}")
    print(f"  Embedding size: {len(vectorized_doc['embedding'])} dimensions")
    print(f"  Embedding sample: {vectorized_doc['embedding'][:5]}...")
    
    # Test search queries
    print("\n🔍 Testing search queries...")
    test_queries = [
        "daging sapi beku",
        "frozen beef meat",
        "02023000",
        "karantina hewan",
        "import regulation"
    ]
    
    for query in test_queries:
        query_embedding = vectorizer.vectorize_query(query)
        similarity = vectorizer.cosine_similarity(
            query_embedding, 
            vectorized_doc['embedding']
        )
        print(f"  Query: '{query}' -> Similarity: {similarity:.4f}")
    
    print("\n✅ Test completed successfully!")


if __name__ == "__main__":
    test_local_ingestion()
