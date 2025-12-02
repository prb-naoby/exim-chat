"""
Qdrant store for INSW documents with hybrid search (dense + sparse vectors)
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    SparseVectorParams, SparseIndexParams,
    NamedVector, NamedSparseVector,
    Prefetch, FusionQuery, SparseVector
)
from typing import List, Dict, Any, Optional
import json
import hashlib


class INSWQdrantStore:
    """Qdrant vector store for INSW documents with hybrid search"""
    
    def __init__(self, url: str, api_key: str, collection_name: str = "insw_documents"):
        """
        Initialize Qdrant store for INSW documents
        
        Args:
            url: Qdrant server URL
            api_key: Qdrant API key
            collection_name: Collection name
        """
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
    
    def create_collection(self, vector_size: int = 3072):
        """
        Create collection with hybrid vectors (dense + sparse)
        
        Args:
            vector_size: Dense vector size (3072 for gemini-embedding-001)
        """
        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if exists:
            info = self.client.get_collection(self.collection_name)
            print(f"Collection '{self.collection_name}' already exists with {info.points_count} points")
            return
        
        # Create collection with named vectors
        self.client.create_collection(
            collection_name=self.collection_name,
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
        print(f"Created collection '{self.collection_name}' with hybrid vectors")
    
    def _create_sparse_vector(self, text: str) -> Dict[str, Any]:
        """
        Create BM25-like sparse vector from text
        Simple implementation: word frequencies as indices
        
        Args:
            text: Text to vectorize
            
        Returns:
            Sparse vector dict with indices and values
        """
        # Tokenize and count words
        words = text.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 2:  # Skip short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Convert to sparse format (use hash of word as index)
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
    
    def upsert_document(self, doc_id: int, text: str, dense_vector: List[float], metadata: Dict[str, Any]):
        """
        Upsert INSW document with hybrid vectors
        
        Args:
            doc_id: Unique document ID (integer)
            text: Document text content
            dense_vector: Dense embedding vector
            metadata: Document metadata (title, source, etc)
        """
        # Create sparse vector
        sparse_data = self._create_sparse_vector(text)
        sparse_vector = SparseVector(
            indices=sparse_data["indices"],
            values=sparse_data["values"]
        )
        
        # Create point with both vectors
        point = PointStruct(
            id=doc_id,
            vector=NamedVector(
                name="dense",
                vector=dense_vector
            ),
            payload={
                "text": text,
                "metadata": metadata
            }
        )
        
        # Add sparse vector to point
        point.vector = {
            "dense": dense_vector
        }
        
        # Upsert point
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        # Upsert sparse vector separately
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=NamedSparseVector(
                        name="bm25",
                        vector=sparse_vector
                    ),
                    payload={
                        "text": text,
                        "metadata": metadata
                    }
                )
            ]
        )
    
    def search_hybrid(self, query_text: str, dense_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Hybrid search using both dense and sparse vectors with RRF fusion
        
        Args:
            query_text: Query text
            dense_vector: Dense query embedding
            limit: Number of results to return
            
        Returns:
            List of search results with scores and full payload
        """
        # Create sparse query vector
        sparse_data = self._create_sparse_vector(query_text)
        sparse_vector = SparseVector(
            indices=sparse_data["indices"],
            values=sparse_data["values"]
        )
        
        try:
            # Perform hybrid search with RRF fusion
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=FusionQuery(
                    fusion="rrf"
                ),
                prefetch=[
                    Prefetch(
                        query=dense_vector,
                        using="dense",
                        limit=limit * 2
                    ),
                    Prefetch(
                        query=sparse_vector,
                        using="bm25",
                        limit=limit * 2
                    )
                ],
                limit=limit
            )
            
            # Format results - return full payload for INSW data
            search_results = []
            for point in results.points:
                search_results.append({
                    "id": point.id,
                    "payload": point.payload,  # Return full payload
                    "score": point.score
                })
            
            return search_results
            
        except Exception as e:
            print(f"Hybrid search failed: {e}")
            # Fallback to dense-only search
            try:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=dense_vector,
                    limit=limit
                )
                
                search_results = []
                for point in results:
                    search_results.append({
                        "id": point.id,
                        "payload": point.payload,
                        "score": point.score
                    })
                
                return search_results
            except Exception as e2:
                print(f"Dense search also failed: {e2}")
                return []
